"""
Pruebas del circuito de formularios clínicos.

Nacieron en la fase 0 del plan de saneamiento como pruebas de caracterización:
fijaban el comportamiento de entonces —bugs incluidos— para poder distinguir
después un cambio deliberado de una regresión. A medida que las fases cierran
hallazgos, las pruebas correspondientes se invierten y pasan a afirmar el
comportamiento correcto.

Tres categorías:

  * CIRCUITO   — recorrido que debe seguir funcionando siempre. Si se pone en
                 rojo, algo se rompió.
  * F<n> abierto  — documenta un hallazgo vigente. Su docstring dice qué debe
                 afirmar una vez corregido.
  * F<n> cerrado  — ya invertida. Su docstring dice en qué paso se cerró y
                 queda como protección contra la regresión.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical import Target
from app.models.user import Profile, User

ADMIN = "/api/v1/admin"
CLIN = "/api/v1/clinical"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """La usuaria que deps.get_current_user devuelve por defecto."""
    u = User(firebase_uid="test_uid_123", email="test@alma.com", is_active=True)
    db_session.add(u)
    await db_session.flush()
    db_session.add(Profile(user_id=u.user_id, nickname="Test"))
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def otra_usuaria(db_session: AsyncSession) -> User:
    u = User(firebase_uid="otra_uid_456", email="otra@alma.com", is_active=True)
    db_session.add(u)
    await db_session.flush()
    db_session.add(Profile(user_id=u.user_id, nickname="Otra"))
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def usuaria_embarazada(db_session: AsyncSession, user, target_embarazadas):
    """
    Usuaria a la que la segmentación automática le asigna PREGNANT.

    No alcanza con vincular el segmento a mano: finalize_submission llama a
    sync_profile_tags, que recalcula los segmentos desde las fechas clínicas y
    reemplaza la colección. Hay que darle una fecha de última menstruación
    coherente para que la automatización lo deduzca.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import select

    perfil = await db_session.scalar(
        select(Profile).where(Profile.user_id == user.user_id)
    )
    perfil.last_period_date = datetime.utcnow() - timedelta(weeks=10)
    await db_session.commit()
    return user


@pytest.fixture
async def target_embarazadas(db_session: AsyncSession) -> Target:
    t = Target(code="PREGNANT", name="Embarazadas", is_active=True)
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


async def crear_formulario_iciq(client, *, code=None, target_ids=None, publicar=True):
    """
    Arma un formulario de dos preguntas con puntaje por opción y una regla que
    los suma, imitando la forma del ICIQ-SF. Devuelve (form_id, section_id).

    Publica por defecto: desde la fase 3 un formulario recién creado queda en
    borrador y no lo ve nadie hasta que alguien decide publicarlo.
    """
    code = code or f"TEST_{uuid.uuid4().hex[:8].upper()}"
    r = await client.post(
        f"{ADMIN}/forms",
        json={
            "code": code,
            "title_key": "form.test.title",
            "target_ids": [str(t) for t in (target_ids or [])],
            "frecuencia": "unica_vez",
            "disparador": "al_registro",
        },
    )
    assert r.status_code == 201, r.text
    form_id = r.json()["form_id"]

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/sections",
        json={"title_key": "sec.principal", "bloque": "URIN", "order_index": 0},
    )
    assert r.status_code == 201, r.text
    section_id = r.json()["section_id"]

    for data_key, opciones in (
        ("iciq_frecuencia", [("nunca", 0), ("semanal", 2), ("diario", 4)]),
        ("iciq_cantidad", [("poca", 0), ("moderada", 3), ("mucha", 6)]),
    ):
        await crear_pregunta(client, section_id, data_key, opciones)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "iciq_total",
            "formula": "iciq_frecuencia + iciq_cantidad",
            "order_index": 0,
        },
    )
    assert r.status_code == 201, r.text

    if publicar:
        r = await client.post(f"{ADMIN}/forms/{form_id}/publish")
        assert r.status_code == 200, r.text

    return form_id, section_id


async def crear_pregunta(client, section_id, data_key, opciones, *, order_index=0):
    """
    Crea pregunta y opciones en llamadas separadas.

    Es el camino que usa el editor del admin. Desde el paso 1a el camino en
    línea también funciona (ver F26), pero estas pruebas siguen ejercitando el
    que la aplicación real usa.
    """
    r = await client.post(
        f"{ADMIN}/sections/{section_id}/questions",
        json={
            "data_key": data_key,
            "text_key": f"q.{data_key}",
            "type": "single",
            "value_type": "string",
            "score_mode": "option_score",
            "is_required": True,
            "order_index": order_index,
        },
    )
    assert r.status_code == 201, r.text
    question_id = r.json()["question_id"]

    for i, opcion in enumerate(opciones):
        valor, puntaje = opcion[0], opcion[1]
        payload = {
            "value": valor,
            "label_key": f"opt.{valor}",
            "score": puntaje,
            "order_index": i,
        }
        if len(opcion) > 2:
            payload["context_rules"] = opcion[2]
        r = await client.post(f"{ADMIN}/questions/{question_id}/options", json=payload)
        assert r.status_code == 201, r.text

    return question_id


async def responder(client, form_id, respuestas: dict):
    """Recorre start → answers → finalize y devuelve la submission final."""
    r = await client.post(f"{CLIN}/submissions/start", json={"form_id": form_id})
    assert r.status_code == 200, r.text
    sub_id = r.json()["submission_id"]

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    preguntas = {
        q["data_key"]: q["question_id"]
        for s in r.json()["sections"]
        for q in s["questions"]
    }

    r = await client.put(
        f"{CLIN}/submissions/{sub_id}/answers",
        json={
            "answers": [
                {"question_id": preguntas[k], "value": v} for k, v in respuestas.items()
            ]
        },
    )
    assert r.status_code == 200, r.text

    r = await client.post(f"{CLIN}/submissions/{sub_id}/finalize")
    assert r.status_code == 200, r.text
    return sub_id, r.json()


# ─────────────────────────────────────────────────────────────────────────────
# CIRCUITO — debe seguir funcionando siempre
# ─────────────────────────────────────────────────────────────────────────────


async def test_circuito_completo_de_punta_a_punta(client, user):
    """Crear en el admin → listar en la app → responder → cerrar → puntaje."""
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{CLIN}/forms")
    assert r.status_code == 200
    assert form_id in [f["form_id"] for f in r.json()]

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )

    # 4 (diario) + 3 (moderada) = 7
    assert sub["calculated_values"]["iciq_total"] == 7
    assert sub["total_score"] == 7
    assert sub["completed_at"] is not None


async def test_el_esquema_del_formulario_llega_completo_a_la_app(client, user):
    """La app pide el esquema por código y recibe secciones, preguntas y opciones."""
    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    await crear_formulario_iciq(client, code=code)

    r = await client.get(f"{CLIN}/forms/{code}/schema")
    assert r.status_code == 200
    esquema = r.json()
    assert len(esquema["sections"]) == 1
    preguntas = esquema["sections"][0]["questions"]
    assert len(preguntas) == 2
    assert all(len(q["options"]) == 3 for q in preguntas)


async def test_el_historial_de_la_usuaria_registra_el_cierre(client, user):
    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{CLIN}/submissions/history")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ─────────────────────────────────────────────────────────────────────────────
# F1 · El segmento se descarta en el cable
# ─────────────────────────────────────────────────────────────────────────────


async def test_f1_el_backend_acepta_el_contrato_viejo_del_editor(
    client, user, target_embarazadas
):
    """
    CERRADO en el paso 1a. El editor todavía manda `target` como código en
    singular; el backend ahora lo resuelve en vez de descartarlo, así que el
    segmento deja de perderse sin que el admin tenga que cambiar todavía.

    Esta rama desaparece en el paso 1c, junto con extra="forbid".
    """
    r = await client.post(
        f"{ADMIN}/forms",
        json={
            "code": f"TEST_{uuid.uuid4().hex[:8].upper()}",
            "title_key": "t",
            "target": "PREGNANT",  # ← lo que realmente envía el editor hoy
            "frecuencia": "unica_vez",
            "disparador": "al_registro",
        },
    )
    assert r.status_code == 201
    assert [t["code"] for t in r.json()["targets"]] == ["PREGNANT"]


async def test_f27_crear_con_segmento_funciona(client, user, target_embarazadas):
    """
    Antes fallaba: en create_form, el `db.execute` que buscaba los targets
    disparaba un autoflush que persistía el formulario recién agregado, y el
    `form.targets = targets` siguiente intentaba cargar la colección existente
    con IO síncrono dentro del contexto async.

    F1 y F27 se tapaban mutuamente: como el admin mandaba el campo equivocado,
    este camino nunca se ejecutaba. Por eso fueron en el mismo cambio.

    CERRADO en el paso 1a: los segmentos se resuelven antes de que haya nada
    pendiente en la sesión, y se asignan en el constructor del formulario.
    """
    r = await client.post(
        f"{ADMIN}/forms",
        json={
            "code": f"TEST_{uuid.uuid4().hex[:8].upper()}",
            "title_key": "t",
            "target_ids": [str(target_embarazadas.target_id)],
        },
    )
    assert r.status_code == 201
    assert [t["code"] for t in r.json()["targets"]] == ["PREGNANT"]


async def test_f27_editar_con_segmento_si_funciona(client, user, target_embarazadas):
    """
    La edición sí asigna segmentos correctamente. Es el único camino que hoy
    funciona, y confirma que el problema de F27 es exclusivo de la creación.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.put(
        f"{ADMIN}/forms/{form_id}",
        json={"target_ids": [str(target_embarazadas.target_id)]},
    )
    assert r.status_code == 200
    assert [t["code"] for t in r.json()["targets"]] == ["PREGNANT"]


# ─────────────────────────────────────────────────────────────────────────────
# F2 / F3 · Visibilidad
# ─────────────────────────────────────────────────────────────────────────────


async def test_f2_un_borrador_no_llega_a_la_usuaria_hasta_publicarse(client, user):
    """
    CERRADO en la fase 3. create_form deja el formulario en borrador y la
    aplicación ahora filtra por estado, así que existe un acto de publicar.
    """
    form_id, _ = await crear_formulario_iciq(client, publicar=False)

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["status"] == "draft"

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]

    r = await client.post(f"{ADMIN}/forms/{form_id}/publish")
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    r = await client.get(f"{CLIN}/forms")
    assert form_id in [f["form_id"] for f in r.json()]


async def test_un_borrador_tampoco_se_abre_adivinando_su_codigo(client, user):
    """El esquema por código respeta el mismo criterio que el listado."""
    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    await crear_formulario_iciq(client, code=code, publicar=False)

    r = await client.get(f"{CLIN}/forms/{code}/schema")
    assert r.status_code == 404


async def test_despublicar_lo_retira_sin_tocar_lo_respondido(client, user):
    """Volver a borrador deja de ofrecerlo; el historial queda intacto."""
    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.post(f"{ADMIN}/forms/{form_id}/unpublish")
    assert r.status_code == 200

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]

    r = await client.get(f"{CLIN}/submissions/history")
    assert len(r.json()) == 1


async def test_no_se_publica_un_formulario_sin_preguntas(client, user):
    """Publicar un cuestionario vacío no le sirve a nadie."""
    r = await client.post(
        f"{ADMIN}/forms", json={"code": f"TEST_{uuid.uuid4().hex[:8].upper()}"}
    )
    form_id = r.json()["form_id"]

    r = await client.post(f"{ADMIN}/forms/{form_id}/publish")
    assert r.status_code == 400
    assert "no questions" in r.json()["detail"]


async def test_f3_un_formulario_sin_segmento_se_muestra_a_todas(client, user):
    """
    Al cerrar F3: un formulario sin segmento no debería alcanzar a todas por
    defecto. Con F1 y F2 ya cerrados el riesgo bajó mucho —ahora hay que
    publicarlo a propósito— pero la regla sigue en pie.
    """
    form_id, _ = await crear_formulario_iciq(client, target_ids=[])
    r = await client.get(f"{CLIN}/forms")
    assert form_id in [f["form_id"] for f in r.json()]


async def test_f9_un_formulario_archivado_se_puede_encontrar_y_restaurar(client, user):
    """
    CERRADO en la fase 3. Archivar seguía sacándolo de la aplicación, que es lo
    correcto, pero el listado del panel filtraba por is_active y el formulario
    quedaba inalcanzable: un borrado suave que se comportaba como definitivo.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.delete(f"{ADMIN}/forms/{form_id}")
    assert r.status_code == 204

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]

    # Fuera del listado por defecto del panel, pero alcanzable al pedir archivados
    r = await client.get(f"{ADMIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()["items"]]

    r = await client.get(f"{ADMIN}/forms", params={"status": "archived"})
    assert form_id in [f["form_id"] for f in r.json()["items"]]

    # Restaurar lo devuelve a borrador, no directo a la aplicación
    r = await client.post(f"{ADMIN}/forms/{form_id}/restore")
    assert r.status_code == 200
    assert r.json()["status"] == "draft"
    assert r.json()["is_active"] is True

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]


async def test_f10_el_filtro_de_archivados_devuelve_los_archivados(client, user):
    """
    CERRADO en la fase 3. El estado se combinaba con is_active mediante AND, y
    como archivar pone is_active en falso el filtro devolvía el conjunto vacío
    por construcción.
    """
    form_id, _ = await crear_formulario_iciq(client)
    otro_id, _ = await crear_formulario_iciq(client)
    await client.delete(f"{ADMIN}/forms/{form_id}")

    r = await client.get(f"{ADMIN}/forms", params={"status": "archived"})
    ids = [f["form_id"] for f in r.json()["items"]]
    assert form_id in ids
    assert otro_id not in ids


# ─────────────────────────────────────────────────────────────────────────────
# F5 · Periodicidad
# ─────────────────────────────────────────────────────────────────────────────


async def test_f5_un_formulario_de_unica_vez_queda_marcado_como_completado(
    client, user
):
    """
    CERRADO en la fase 6. La frecuencia no se leía en ninguna parte y el
    listado nunca consultaba las evaluaciones previas, así que un cuestionario
    de única vez se repetía para siempre.

    Sigue apareciendo en la lista a propósito —la app necesita poder mostrar lo
    ya hecho (F25)— pero marcado, y deja de ofrecerse para responder.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "disponible"

    await responder(
        client, form_id, {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "completado"
    assert entrada["last_completed_at"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# F6 · Endpoints de segmentos que no existen
# ─────────────────────────────────────────────────────────────────────────────


async def test_f6_editar_y_borrar_segmentos(client, user, target_embarazadas):
    """
    CERRADO en el paso 1a. El borrado es suave: desactiva en vez de destruir,
    para no romper los formularios y perfiles que ya referencian el segmento.
    """
    tid = target_embarazadas.target_id

    r = await client.put(f"{ADMIN}/targets/{tid}", json={"name": "Gestantes"})
    assert r.status_code == 200
    assert r.json()["name"] == "Gestantes"

    r = await client.delete(f"{ADMIN}/targets/{tid}")
    assert r.status_code == 204

    r = await client.get(f"{ADMIN}/targets")
    assert str(tid) not in [t["target_id"] for t in r.json()]


# ─────────────────────────────────────────────────────────────────────────────
# F14 / F15 / F16 · El motor de scoring
# ─────────────────────────────────────────────────────────────────────────────


async def test_f14_el_simulador_calcula_con_preguntas_de_puntaje_por_opcion(
    client, user
):
    """
    CERRADO en la fase 2. `engine` y `target_ids_str` se usaban diecisiete
    líneas antes de definirse, y el UnboundLocalError salía como 500 por el
    except genérico. Además resolve_answer_score devolvía un diccionario que
    iba tal cual al contexto de las fórmulas (F30), así que arreglar sólo el
    orden no habría alcanzado.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={"answers": {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}},
    )
    assert r.status_code == 200
    # 4 (diario) + 3 (moderada) = 7, el mismo número que calcula el cierre real
    assert r.json()["scores"]["iciq_total"] == 7
    assert r.json()["total_score"] == 7


async def test_f15_las_reglas_por_segmento_se_aplican_en_produccion(
    client, usuaria_embarazada, target_embarazadas, db_session
):
    """
    CERRADO en la fase 2. finalize_submission llamaba a process_rules sin
    user_target_ids, así que toda regla con target_id se descartaba con
    `continue` y el scoring contextual estaba muerto en producción.

    Ahora los segmentos del perfil entran al motor.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "riesgo_embarazo",
            "formula": "iciq_frecuencia * 10",
            "target_id": str(target_embarazadas.target_id),
            "order_index": 1,
        },
    )
    assert r.status_code == 201

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    assert sub["calculated_values"]["iciq_total"] == 4
    # 4 (diario) * 10 — la regla del segmento ahora sí corre
    assert sub["calculated_values"]["riesgo_embarazo"] == 40


async def test_f15_una_regla_de_segmento_no_aplica_a_quien_no_lo_tiene(
    client, user, target_embarazadas
):
    """El lado negativo: sin el segmento, la regla sigue sin correr."""
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "riesgo_embarazo",
            "formula": "iciq_frecuencia * 10",
            "target_id": str(target_embarazadas.target_id),
            "order_index": 1,
        },
    )
    assert r.status_code == 201

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )
    assert "riesgo_embarazo" not in sub["calculated_values"]


async def test_f16_las_reglas_por_opcion_afectan_el_puntaje_real(
    client, usuaria_embarazada, target_embarazadas
):
    """
    CERRADO en la fase 2. finalize_submission calculaba el puntaje en línea en
    vez de llamar a resolve_answer_score, así que las 371 líneas de la matriz
    de reglas contextuales del panel no tenían efecto alguno.
    """
    form_id, section_id = await crear_formulario_iciq(client)

    reglas = [
        {
            "conditions": {"targets": [str(target_embarazadas.target_id)]},
            "override_score": 99,
        }
    ]
    await crear_pregunta(
        client, section_id, "dolor", [("si", 1, reglas)], order_index=2
    )
    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={"variable_name": "dolor_efectivo", "formula": "dolor", "order_index": 2},
    )
    assert r.status_code == 201

    _, sub = await responder(
        client,
        form_id,
        {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca", "dolor": "si"},
    )

    # El override de 99 se aplica sobre la opción, no sobre el puntaje base 1.
    assert sub["calculated_values"]["dolor_efectivo"] == 99


async def test_f17_el_puntaje_total_solo_reconoce_los_nombres_de_iciq(client, user):
    """
    La heurística busca 'iciq_total' y 'total_score'. Cualquier otro nombre
    deja total_score en cero, en silencio.

    Al cerrar F17: el formulario debe poder declarar cuál es su variable total.
    Ver test_f17_el_formulario_declara_cual_es_su_puntaje_total.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]
    r = await client.put(
        f"{ADMIN}/rules/{rule_id}", json={"variable_name": "severidad_global"}
    )
    assert r.status_code == 200

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "mucha"}
    )

    assert sub["calculated_values"]["severidad_global"] == 10
    # Sin regla marcada ni nombre reconocible, el formulario no declara total.
    # Antes eso se informaba como cero, que clínicamente dice otra cosa.
    assert sub["total_score"] is None


# ─────────────────────────────────────────────────────────────────────────────
# F20 / F21 · Persistencia e integridad
# ─────────────────────────────────────────────────────────────────────────────


async def test_f20_corregir_una_respuesta_la_reemplaza(client, user, db_session):
    """
    CERRADO en la fase 4. save_answers insertaba una fila nueva cada vez, así
    que corregir una respuesta dejaba las dos versiones y el puntaje pasaba a
    depender del orden del iterado.

    La restricción única en la base impide además que vuelva a pasar por otro
    camino.
    """
    from sqlalchemy import func, select

    from app.models.clinical import SubmissionAnswer

    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(f"{CLIN}/submissions/start", json={"form_id": form_id})
    sub_id = r.json()["submission_id"]

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]

    for valor in ("nunca", "diario"):  # la usuaria corrige su respuesta
        r = await client.put(
            f"{CLIN}/submissions/{sub_id}/answers",
            json={"answers": [{"question_id": qid, "value": valor}]},
        )
        assert r.status_code == 200

    total = await db_session.scalar(
        select(func.count(SubmissionAnswer.answer_id)).where(
            SubmissionAnswer.submission_id == uuid.UUID(sub_id)
        )
    )
    assert total == 1

    guardada = await db_session.scalar(
        select(SubmissionAnswer).where(
            SubmissionAnswer.submission_id == uuid.UUID(sub_id)
        )
    )
    assert guardada.value == "diario"  # la corrección, no la primera


async def test_f21_no_se_puede_tocar_la_evaluacion_de_otra_usuaria(
    client, user, otra_usuaria
):
    """
    CERRADO en la fase 4. Con el identificador de una evaluación ajena se la
    podía completar y cerrar.

    Responde 404 y no 403 a propósito: un 403 confirmaría que esa evaluación
    existe.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{CLIN}/submissions/start",
        json={"form_id": form_id},
        headers={"Authorization": "Bearer otra_uid_456"},
    )
    sub_ajena = r.json()["submission_id"]

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]

    # test_uid_123 intenta escribir y cerrar la evaluación de otra_uid_456
    r = await client.put(
        f"{CLIN}/submissions/{sub_ajena}/answers",
        json={"answers": [{"question_id": qid, "value": "diario"}]},
    )
    assert r.status_code == 404

    r = await client.post(f"{CLIN}/submissions/{sub_ajena}/finalize")
    assert r.status_code == 404

    # Su dueña sí puede
    r = await client.put(
        f"{CLIN}/submissions/{sub_ajena}/answers",
        json={"answers": [{"question_id": qid, "value": "diario"}]},
        headers={"Authorization": "Bearer otra_uid_456"},
    )
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# F11 · Versionado
# ─────────────────────────────────────────────────────────────────────────────


async def test_f11_editar_un_formulario_respondido_no_crea_version_nueva(client, user):
    """
    version se fija en 1 al crear y no cambia nunca, así que editar reescribe
    el significado del histórico ya cerrado.

    Al cerrar F11: editar un formulario con respuestas debe generar v2.
    """
    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "mucha"}
    )

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["version"] == 1

    r = await client.put(f"{ADMIN}/forms/{form_id}", json={"title_key": "otro.titulo"})
    assert r.status_code == 200
    assert r.json()["version"] == 1  # sigue en 1 pese a tener respuestas cerradas


# ─────────────────────────────────────────────────────────────────────────────
# F26 · Crear una pregunta con opciones en línea (hallazgo de esta fase)
# ─────────────────────────────────────────────────────────────────────────────


async def test_f26_crear_pregunta_con_opciones_en_linea(client, user):
    """
    QuestionCreate acepta `options`, pero create_question arma la respuesta sin
    `context_rules` y OptionResponse lo declara obligatorio (Optional sin
    default es requerido en Pydantic v2). El ValidationError sale como 500.

    CERRADO en el paso 1a: el campo lleva default, la respuesta se construye
    desde el modelo y create_question persiste las context_rules recibidas.
    """
    _, section_id = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/sections/{section_id}/questions",
        json={
            "data_key": "en_linea",
            "text_key": "q.en_linea",
            "type": "single",
            "score_mode": "option_score",
            "order_index": 9,
            "options": [
                {
                    "value": "si",
                    "score": 1,
                    "order_index": 0,
                    "context_rules": [{"conditions": {}, "override_score": 7}],
                }
            ],
        },
    )
    assert r.status_code == 201
    opcion = r.json()["options"][0]
    assert opcion["value"] == "si"
    assert opcion["context_rules"] == [{"conditions": {}, "override_score": 7}]


async def test_f4_una_lista_vacia_limpia_los_segmentos(
    client, user, target_embarazadas
):
    """
    CERRADO en el paso 1a. Antes la guarda `if form_data.target_ids:` trataba
    la lista vacía como "no tocar", así que un formulario no podía volver a
    quedar sin segmento.

    Omitir el campo sigue significando "dejar como está": son dos intenciones
    distintas y ahora se distinguen.
    """
    form_id, _ = await crear_formulario_iciq(
        client, target_ids=[target_embarazadas.target_id]
    )
    assert len((await client.get(f"{ADMIN}/forms/{form_id}")).json()["targets"]) == 1

    # No mandar el campo no toca los segmentos
    r = await client.put(f"{ADMIN}/forms/{form_id}", json={"title_key": "otro"})
    assert len(r.json()["targets"]) == 1

    # Mandar una lista vacía sí los limpia
    r = await client.put(f"{ADMIN}/forms/{form_id}", json={"target_ids": []})
    assert r.status_code == 200
    assert r.json()["targets"] == []


async def test_un_segmento_inexistente_falla_en_vez_de_ignorarse(client, user):
    """
    Pedir un segmento que no existe y recibir un formulario sin segmento sería
    la misma falla silenciosa que F1. El contrato explícito rechaza.
    """
    inexistente = str(uuid.uuid4())
    r = await client.post(
        f"{ADMIN}/forms",
        json={"code": f"TEST_{uuid.uuid4().hex[:8].upper()}", "target_ids": [inexistente]},
    )
    assert r.status_code == 400
    assert inexistente in r.json()["detail"]


async def test_el_codigo_de_segmento_desconocido_no_tumba_al_editor(client, user):
    """
    La rama de compatibilidad es tolerante a propósito: el editor manda
    `target: "todas"` por defecto y ese segmento puede no estar cargado. Fallar
    ahí rompería el alta de formularios, que es justo lo que 1a evita.

    Esta asimetría desaparece en 1c, cuando se elimine el campo.
    """
    r = await client.post(
        f"{ADMIN}/forms",
        json={"code": f"TEST_{uuid.uuid4().hex[:8].upper()}", "target": "NO_EXISTE"},
    )
    assert r.status_code == 201
    assert r.json()["targets"] == []


async def test_recrear_un_formulario_archivado_lo_reactiva(
    client, user, target_embarazadas, db_session
):
    """
    Crear con el código de un formulario archivado lo revive en lugar de
    duplicarlo: conserva el form_id —y por lo tanto el histórico de
    respuestas—, vuelve a borrador y reemplaza los segmentos.

    El camino se reestructuró en 1a, así que conviene tenerlo cubierto.
    """
    otro = Target(code="POSTPARTUM", name="Post-parto", is_active=True)
    db_session.add(otro)
    await db_session.commit()

    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    r = await client.post(
        f"{ADMIN}/forms",
        json={"code": code, "target_ids": [str(target_embarazadas.target_id)]},
    )
    form_id = r.json()["form_id"]

    await client.delete(f"{ADMIN}/forms/{form_id}")

    r = await client.post(
        f"{ADMIN}/forms", json={"code": code, "target_ids": [str(otro.target_id)]}
    )
    assert r.status_code == 201
    assert r.json()["form_id"] == form_id
    assert r.json()["is_active"] is True
    assert r.json()["status"] == "draft"
    assert [t["code"] for t in r.json()["targets"]] == ["POSTPARTUM"]


async def test_un_codigo_activo_duplicado_sigue_siendo_rechazado(client, user):
    """La reestructuración de 1a no debe haber aflojado esta guarda."""
    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    r = await client.post(f"{ADMIN}/forms", json={"code": code})
    assert r.status_code == 201

    r = await client.post(f"{ADMIN}/forms", json={"code": code})
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# F33 · Una alerta sin tipo tumba el cierre de la evaluación
# ─────────────────────────────────────────────────────────────────────────────


async def test_f33_una_regla_con_alerta_sin_tipo_cierra_bien(client, user):
    """
    scoring.py hace `rule.alert_type or AlertType.INFO`, y ese miembro no
    existe en el enum: solo hay DERIVACION_CLINICA, ACTIVAR_PLAN y SEGUIMIENTO.

    El admin permite crear una regla con condición de alerta y sin tipo, así
    que en cuanto esa alerta se dispara el cierre de la evaluación explota con
    AttributeError. Es la funcionalidad central del motor clínico —generar
    derivaciones— y está caída.

    CERRADO en la fase 2: el valor por defecto pasa a ser un miembro real del
    enum, SEGUIMIENTO.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "alerta_sin_tipo",
            "formula": "iciq_frecuencia",
            "alert_condition": "alerta_sin_tipo >= 1",
            "order_index": 1,
        },
    )
    assert r.status_code == 201

    r = await client.post(f"{CLIN}/submissions/start", json={"form_id": form_id})
    sub_id = r.json()["submission_id"]

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    preguntas = {
        q["data_key"]: q["question_id"]
        for s in r.json()["sections"]
        for q in s["questions"]
    }
    await client.put(
        f"{CLIN}/submissions/{sub_id}/answers",
        json={"answers": [{"question_id": preguntas["iciq_frecuencia"], "value": "diario"}]},
    )

    r = await client.post(f"{CLIN}/submissions/{sub_id}/finalize")
    assert r.status_code == 200
    assert r.json()["completed_at"] is not None


async def test_una_alerta_con_tipo_explicito_si_cierra(client, user):
    """El mismo caso con tipo declarado funciona: aísla la causa a F33."""
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "alerta_con_tipo",
            "formula": "iciq_frecuencia",
            "alert_condition": "alerta_con_tipo >= 1",
            "alert_type": "derivacion_clinica",
            "order_index": 1,
        },
    )
    assert r.status_code == 201

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )
    assert sub["completed_at"] is not None
    assert sub["calculated_values"]["alerta_con_tipo"] == 4


# ─────────────────────────────────────────────────────────────────────────────
# El objetivo de la fase 2: un solo motor
# ─────────────────────────────────────────────────────────────────────────────


async def test_el_simulador_y_el_cierre_real_dan_el_mismo_resultado(
    client, usuaria_embarazada, target_embarazadas
):
    """
    La razón de ser de la fase 2.

    Antes eran dos implementaciones paralelas: el simulador aplicaba los
    segmentos y las reglas por opción, producción no. La clínica validaba en el
    panel una regla que no era la que después se le calculaba a la paciente.

    Esta prueba alimenta el mismo caso a los dos caminos y exige que coincidan.
    Si alguien vuelve a bifurcarlos, se pone en rojo.
    """
    form_id, section_id = await crear_formulario_iciq(client)

    reglas = [
        {
            "conditions": {"targets": [str(target_embarazadas.target_id)]},
            "override_score": 20,
        }
    ]
    await crear_pregunta(client, section_id, "dolor", [("si", 1, reglas)], order_index=2)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "global",
            "formula": "iciq_frecuencia + iciq_cantidad + dolor",
            "is_total": True,
            "order_index": 5,
        },
    )
    assert r.status_code == 201

    respuestas = {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada", "dolor": "si"}

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={
            "answers": respuestas,
            "target_ids": [str(target_embarazadas.target_id)],
        },
    )
    assert r.status_code == 200
    simulado = r.json()

    _, real = await responder(client, form_id, respuestas)

    # 4 (diario) + 3 (moderada) + 20 (dolor sobrescrito por el segmento) = 27
    assert simulado["scores"] == real["calculated_values"]
    assert simulado["total_score"] == real["total_score"] == 27


async def test_f17_el_formulario_declara_cual_es_su_puntaje_total(client, user):
    """
    CERRADO en la fase 2. La heurística buscaba 'iciq_total' y 'total_score'
    por nombre, así que cualquier cuestionario que no se llamara como el ICIQ
    quedaba en cero y sin aviso.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]
    r = await client.put(
        f"{ADMIN}/rules/{rule_id}",
        json={"variable_name": "severidad_global", "is_total": True},
    )
    assert r.status_code == 200

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "mucha"}
    )

    assert sub["calculated_values"]["severidad_global"] == 10
    assert sub["total_score"] == 10


async def test_f17_los_formularios_viejos_conservan_su_puntaje(client, user):
    """
    Ningún formulario ya cargado tiene una regla marcada, así que el respaldo
    por nombre se conserva a propósito: cambiarles el puntaje retroactivamente
    sería peor que el bug.
    """
    form_id, _ = await crear_formulario_iciq(client)
    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )
    assert sub["total_score"] == 7


async def test_f29_la_evaluacion_guarda_su_interpretacion_clinica(client, user):
    """
    CERRADO en la fase 2. Los rangos se persistían desde el panel y nunca se
    evaluaban, así que score_interpretation quedaba siempre nulo.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]
    await client.put(
        f"{ADMIN}/rules/{rule_id}",
        json={
            "is_total": True,
            "interpretation_ranges": {"0-5": "Leve", "6-9": "Moderado", ">=10": "Severo"},
        },
    )

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )
    assert sub["total_score"] == 7
    assert sub["score_interpretation"] == "Moderado"


async def test_f18_las_formulas_pueden_usar_el_valor_crudo_de_una_respuesta(
    client, user
):
    """
    CERRADO en la fase 2. El contexto sólo llevaba el puntaje, de modo que una
    pregunta sin score_mode entraba como cero y no se podía escribir una
    fórmula sobre lo que la usuaria efectivamente respondió.

    El data_key a secas sigue siendo el puntaje: cambiar su significado habría
    reescrito toda fórmula y toda regla de recomendación ya existente.
    """
    form_id, section_id = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/sections/{section_id}/questions",
        json={
            "data_key": "edad",
            "text_key": "q.edad",
            "type": "text",
            "score_mode": "none",
            "order_index": 3,
        },
    )
    assert r.status_code == 201

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "mayor_de_40",
            "formula": "1 if edad__valor > 40 else 0",
            "order_index": 4,
        },
    )
    assert r.status_code == 201

    _, sub = await responder(
        client,
        form_id,
        {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca", "edad": 52},
    )

    # calculated_values guarda solo las variables que calculan las reglas: es
    # el contexto que RecommendationService usa para asignar planes, y su forma
    # se conserva a propósito.
    assert "edad" not in sub["calculated_values"]
    assert sub["calculated_values"]["mayor_de_40"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# F35 / F37 · Lo que la fase 2 dejó sin alcanzar desde el panel
# ─────────────────────────────────────────────────────────────────────────────


async def test_f35_la_regla_total_viaja_de_ida_y_vuelta(client, user):
    """
    CERRADO en el repaso de la fase 2. El backend soportaba is_total pero el
    editor no lo enviaba, así que F17 quedaba inalcanzable desde el panel.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={"variable_name": "otro", "formula": "1", "is_total": True, "order_index": 9},
    )
    assert r.status_code == 201
    assert r.json()["is_total"] is True

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    reglas = {x["variable_name"]: x for x in r.json()["scoring_rules"]}
    assert reglas["otro"]["is_total"] is True
    assert reglas["iciq_total"]["is_total"] is False


async def test_f37_los_rangos_de_interpretacion_viajan_de_ida_y_vuelta(client, user):
    """
    CERRADO en el repaso de la fase 2. Ningún cliente enviaba
    interpretation_ranges, de modo que F29 funcionaba en el backend pero no se
    podía alimentar desde el panel.
    """
    form_id, _ = await crear_formulario_iciq(client)

    rangos = {"0-5": "Leve", "6-9": "Moderado", ">=10": "Severo"}
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]

    r = await client.put(
        f"{ADMIN}/rules/{rule_id}",
        json={"is_total": True, "interpretation_ranges": rangos},
    )
    assert r.status_code == 200
    assert r.json()["interpretation_ranges"] == rangos

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["scoring_rules"][0]["interpretation_ranges"] == rangos


async def test_desmarcar_la_regla_total_no_rompe_la_columna(client, user):
    """
    is_total es NOT NULL. El editor envía siempre un booleano, pero un null
    explícito en el cuerpo llegaría a la base y reventaría al commitear.
    """
    form_id, _ = await crear_formulario_iciq(client)
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]

    r = await client.put(f"{ADMIN}/rules/{rule_id}", json={"is_total": True})
    assert r.json()["is_total"] is True

    r = await client.put(f"{ADMIN}/rules/{rule_id}", json={"is_total": False})
    assert r.status_code == 200
    assert r.json()["is_total"] is False

    r = await client.put(f"{ADMIN}/rules/{rule_id}", json={"is_total": None})
    assert r.status_code == 200
    assert r.json()["is_total"] is False


# ─────────────────────────────────────────────────────────────────────────────
# F40 · Una respuesta faltante no puede leerse como "sin síntomas"
# ─────────────────────────────────────────────────────────────────────────────


async def test_f40_si_falta_una_respuesta_el_puntaje_es_nulo_y_no_cero(client, user):
    """
    Ninguna pregunta es obligatoria hoy, así que una mujer puede saltear un
    ítem. La fórmula entonces no resuelve, el motor se traga el error y la
    variable no se calcula.

    Informar eso como cero es lo peligroso: un cero se lee clínicamente como
    "sin síntomas", que puede ser exactamente lo contrario de lo que pasó. El
    puntaje tiene que ser nulo y hay que poder saber qué no se calculó.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(f"{ADMIN}/forms/{form_id}/rules")
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]
    await client.put(f"{ADMIN}/rules/{rule_id}", json={"is_total": True})

    # Sólo una de las dos preguntas que la fórmula necesita
    _, sub = await responder(client, form_id, {"iciq_frecuencia": "diario"})

    assert sub["total_score"] is None
    assert "iciq_total" not in sub["calculated_values"]


async def test_con_todas_las_respuestas_el_puntaje_si_sale(client, user):
    """El contraste, para aislar la causa."""
    form_id, _ = await crear_formulario_iciq(client)
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]
    await client.put(f"{ADMIN}/rules/{rule_id}", json={"is_total": True})

    _, sub = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )
    assert sub["total_score"] == 7


async def test_el_simulador_avisa_que_una_formula_no_se_pudo_calcular(client, user):
    """
    Quien diseña el cuestionario tiene que ver que su fórmula no resuelve, no
    un cero silencioso.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={"answers": {"iciq_frecuencia": "diario"}},
    )
    assert r.status_code == 200
    assert r.json()["total_score"] is None
    assert "iciq_total" in r.json()["uncomputed"]


# ─────────────────────────────────────────────────────────────────────────────
# Una interpretación sin validar se entrega señalada
# ─────────────────────────────────────────────────────────────────────────────


async def test_una_interpretacion_no_validada_viaja_marcada_como_provisoria(
    client, user
):
    """
    Los umbrales que traducen un puntaje a "Leve" o "Severo" son criterio
    médico. Mientras nadie los valide, la etiqueta se entrega igual —sirve para
    trabajar— pero señalada, para que no se confunda con criterio confirmado.
    """
    form_id, _ = await crear_formulario_iciq(client)
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    rule_id = r.json()["scoring_rules"][0]["rule_id"]

    await client.put(
        f"{ADMIN}/rules/{rule_id}",
        json={"is_total": True, "interpretation_ranges": {"0-5": "Leve", "6-20": "Alto"}},
    )

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={"answers": {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}},
    )
    assert r.json()["interpretation"] == "Alto"
    assert r.json()["interpretation_is_provisional"] is True

    await client.put(f"{ADMIN}/rules/{rule_id}", json={"interpretation_validated": True})

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={"answers": {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}},
    )
    assert r.json()["interpretation"] == "Alto"
    assert r.json()["interpretation_is_provisional"] is False


# ─────────────────────────────────────────────────────────────────────────────
# F7 / F8 · Archivar en vez de destruir evidencia clínica
# ─────────────────────────────────────────────────────────────────────────────


async def test_f7_borrar_una_pregunta_respondida_la_archiva(client, user, db_session):
    """
    CERRADO en la fase 4. El borrado era físico y la clave foránea de las
    respuestas no declara ondelete, así que eliminar una pregunta ya contestada
    rompía con una violación sin manejar.

    Una respuesta es evidencia clínica: la pregunta se archiva y deja de
    ofrecerse, pero no desaparece.
    """
    from sqlalchemy import func, select

    from app.models.clinical import FormQuestion, SubmissionAnswer

    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]

    r = await client.delete(f"{ADMIN}/questions/{qid}")
    assert r.status_code == 204

    # La pregunta sigue existiendo, archivada
    pregunta = await db_session.get(FormQuestion, uuid.UUID(qid))
    assert pregunta is not None
    assert pregunta.is_active is False

    # Y su respuesta también
    quedan = await db_session.scalar(
        select(func.count(SubmissionAnswer.answer_id)).where(
            SubmissionAnswer.question_id == uuid.UUID(qid)
        )
    )
    assert quedan == 1

    # Pero deja de ofrecerse, en la app y en el editor
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert qid not in [q["question_id"] for q in r.json()["sections"][0]["questions"]]


async def test_una_pregunta_sin_respuestas_si_se_borra(client, user, db_session):
    """Sin evidencia que preservar, el borrado es real."""
    from app.models.clinical import FormQuestion

    form_id, _ = await crear_formulario_iciq(client)
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]

    r = await client.delete(f"{ADMIN}/questions/{qid}")
    assert r.status_code == 204
    assert await db_session.get(FormQuestion, uuid.UUID(qid)) is None


async def test_archivar_una_pregunta_no_cambia_puntajes_ya_calculados(client, user):
    """
    Sutileza que importa: al recalcular una evaluación, lo que manda es qué
    respondió la mujer, no si la pregunta sigue vigente. Archivar después no
    puede reescribirle el puntaje.
    """
    form_id, _ = await crear_formulario_iciq(client)
    sub_id, antes = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )
    assert antes["total_score"] == 7

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]
    await client.delete(f"{ADMIN}/questions/{qid}")

    r = await client.post(f"{CLIN}/submissions/{sub_id}/finalize")
    assert r.json()["total_score"] == 7


async def test_f8_borrar_una_regla_que_disparo_alertas_la_archiva(client, user):
    """
    CERRADO en la fase 4. Mismo criterio: una alerta clínica registrada es
    evidencia y su regla no puede desaparecer.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/rules",
        json={
            "variable_name": "riesgo",
            "formula": "iciq_frecuencia",
            "alert_condition": "riesgo >= 1",
            "alert_type": "derivacion_clinica",
            "order_index": 1,
        },
    )
    rule_id = r.json()["rule_id"]

    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.delete(f"{ADMIN}/rules/{rule_id}")
    assert r.status_code == 204

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert rule_id not in [x["rule_id"] for x in r.json()["scoring_rules"]]


# ─────────────────────────────────────────────────────────────────────────────
# F11 · Hacer visible la deriva de versiones
# ─────────────────────────────────────────────────────────────────────────────


async def test_f11_la_evaluacion_registra_bajo_que_version_se_respondio(client, user):
    """
    CERRADO parcialmente en la fase 4. La columna existía para esto y nunca se
    escribía, así que no había forma de saber bajo qué definición se respondió.

    No preserva la definición anterior —eso exige otro diseño— pero deja la
    deriva a la vista en lugar de ocultarla.
    """
    from app.models.clinical import UserSubmission

    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(f"{CLIN}/submissions/start", json={"form_id": form_id})
    assert r.status_code == 200

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["version"] == 1


async def test_f11_republicar_con_respuestas_abre_una_version_nueva(client, user):
    """Republicar después de que alguien respondió distingue ambas épocas."""
    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["version"] == 1
    assert r.json()["submission_count"] == 1

    await client.post(f"{ADMIN}/forms/{form_id}/unpublish")
    r = await client.post(f"{ADMIN}/forms/{form_id}/publish")
    assert r.json()["version"] == 2


async def test_republicar_sin_respuestas_no_infla_la_version(client, user):
    """Mientras nadie respondió, editar y republicar no abre época nueva."""
    form_id, _ = await crear_formulario_iciq(client)

    await client.post(f"{ADMIN}/forms/{form_id}/unpublish")
    r = await client.post(f"{ADMIN}/forms/{form_id}/publish")
    assert r.json()["version"] == 1


async def test_no_se_escriben_respuestas_sobre_una_evaluacion_cerrada(client, user):
    """Una evaluación cerrada es histórico: no se le agregan respuestas."""
    form_id, _ = await crear_formulario_iciq(client)
    sub_id, _ = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    qid = r.json()["sections"][0]["questions"][0]["question_id"]

    r = await client.put(
        f"{CLIN}/submissions/{sub_id}/answers",
        json={"answers": [{"question_id": qid, "value": "nunca"}]},
    )
    assert r.status_code == 409


# ─────────────────────────────────────────────────────────────────────────────
# Periodicidad, de punta a punta
# ─────────────────────────────────────────────────────────────────────────────


async def test_un_cuestionario_mensual_espera_su_ventana(client, user):
    """Responder un mensual lo pone en espera hasta el mes siguiente."""
    form_id, _ = await crear_formulario_iciq(client)
    r = await client.put(f"{ADMIN}/forms/{form_id}", json={"frecuencia": "mensual"})
    assert r.status_code == 200

    await responder(
        client, form_id, {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "en_espera"
    assert entrada["next_available_at"] is not None


async def test_un_cuestionario_a_demanda_sigue_disponible(client, user):
    """El que la mujer decide repetir nunca se pone en espera."""
    form_id, _ = await crear_formulario_iciq(client)
    await client.put(f"{ADMIN}/forms/{form_id}", json={"frecuencia": "a_demanda"})

    await responder(
        client, form_id, {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "disponible"


async def test_un_cuestionario_manual_no_aparece_en_el_listado(client, user):
    """
    No se ofrece solo: se llega por enlace directo. Pero su esquema sigue
    siendo accesible por código, que es como funciona ese enlace.
    """
    code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    form_id, _ = await crear_formulario_iciq(client, code=code)
    await client.put(f"{ADMIN}/forms/{form_id}", json={"disparador": "manual"})

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]

    r = await client.get(f"{CLIN}/forms/{code}/schema")
    assert r.status_code == 200


async def test_un_cuestionario_de_dia_30_no_aparece_a_una_usuaria_nueva(
    client, user, db_session
):
    """Los disparadores temporales cuentan desde el alta de la usuaria."""
    form_id, _ = await crear_formulario_iciq(client)
    await client.put(f"{ADMIN}/forms/{form_id}", json={"disparador": "dia_30"})

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "proximamente"
    assert entrada["next_available_at"] is not None

    # La misma usuaria, dada de alta hace dos meses
    from datetime import datetime, timedelta

    user.created_at = datetime.utcnow() - timedelta(days=60)
    await db_session.commit()

    r = await client.get(f"{CLIN}/forms")
    entrada = next(f for f in r.json() if f["form_id"] == form_id)
    assert entrada["availability"] == "disponible"


async def test_un_bloqueante_pendiente_encabeza_el_listado(client, user):
    """Lo que hay que responder antes que nada va primero y viene marcado."""
    await crear_formulario_iciq(client)
    bloqueante_id, _ = await crear_formulario_iciq(client)
    await client.put(
        f"{ADMIN}/forms/{bloqueante_id}", json={"disparador": "bloqueante"}
    )

    r = await client.get(f"{CLIN}/forms")
    listado = r.json()
    assert listado[0]["form_id"] == bloqueante_id
    assert listado[0]["is_blocking"] is True
    assert all(f["is_blocking"] is False for f in listado[1:])


# ─────────────────────────────────────────────────────────────────────────────
# F12 / F42 · Varias secciones
# ─────────────────────────────────────────────────────────────────────────────


async def test_f12_un_formulario_puede_tener_varias_secciones(client, user):
    """
    CERRADO en la fase 7. El modelo y el backend siempre soportaron N secciones
    con su bloque clínico; era el editor el que fijaba la primera.
    """
    form_id, primera = await crear_formulario_iciq(client, publicar=False)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/sections",
        json={"title_key": "sec.prolapso", "bloque": "PROL", "order_index": 1},
    )
    assert r.status_code == 201
    segunda = r.json()["section_id"]

    await crear_pregunta(client, segunda, "bulto", [("no", 0), ("si", 3)])
    await client.post(f"{ADMIN}/forms/{form_id}/publish")

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    secciones = r.json()["sections"]
    assert len(secciones) == 2
    assert [s["bloque"] for s in secciones] == ["URIN", "PROL"]

    # La app recibe las dos, en orden
    code = r.json()["code"]
    r = await client.get(f"{CLIN}/forms/{code}/schema")
    assert [s["bloque"] for s in r.json()["sections"]] == ["URIN", "PROL"]


async def test_las_secciones_se_pueden_reordenar(client, user):
    form_id, primera = await crear_formulario_iciq(client, publicar=False)
    r = await client.post(
        f"{ADMIN}/forms/{form_id}/sections",
        json={"title_key": "sec.b", "bloque": "B", "order_index": 1},
    )
    segunda = r.json()["section_id"]

    r = await client.put(f"{ADMIN}/sections/{segunda}", json={"order_index": 0})
    assert r.status_code == 200
    r = await client.put(f"{ADMIN}/sections/{primera}", json={"order_index": 1})
    assert r.status_code == 200

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert [s["bloque"] for s in r.json()["sections"]] == ["B", "URIN"]


async def test_f42_borrar_una_seccion_respondida_la_archiva(client, user, db_session):
    """
    CERRADO en la fase 7. El borrado era físico y arrastraba las preguntas en
    cascada; como la clave foránea de las respuestas no declara ondelete, eso
    rompía con una violación sin manejar.
    """
    from sqlalchemy import func, select

    from app.models.clinical import FormSection, SubmissionAnswer

    form_id, section_id = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "poca"}
    )

    r = await client.delete(f"{ADMIN}/sections/{section_id}")
    assert r.status_code == 204

    # La sección sigue existiendo, archivada
    seccion = await db_session.get(FormSection, uuid.UUID(section_id))
    assert seccion is not None
    assert seccion.is_active is False

    # Y las respuestas también
    quedan = await db_session.scalar(select(func.count(SubmissionAnswer.answer_id)))
    assert quedan == 2

    # Pero deja de ofrecerse
    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["sections"] == []


async def test_una_seccion_sin_respuestas_si_se_borra(client, user, db_session):
    from app.models.clinical import FormSection

    form_id, section_id = await crear_formulario_iciq(client, publicar=False)

    r = await client.delete(f"{ADMIN}/sections/{section_id}")
    assert r.status_code == 204
    assert await db_session.get(FormSection, uuid.UUID(section_id)) is None


async def test_archivar_una_seccion_no_cambia_puntajes_ya_calculados(client, user):
    """Igual que con las preguntas: lo que manda es qué respondió la mujer."""
    form_id, section_id = await crear_formulario_iciq(client)
    sub_id, antes = await responder(
        client, form_id, {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}
    )
    assert antes["total_score"] == 7

    await client.delete(f"{ADMIN}/sections/{section_id}")

    r = await client.post(f"{CLIN}/submissions/{sub_id}/finalize")
    assert r.json()["total_score"] == 7
