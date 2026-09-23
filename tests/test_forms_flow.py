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
async def target_embarazadas(db_session: AsyncSession) -> Target:
    t = Target(code="PREGNANT", name="Embarazadas", is_active=True)
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


async def crear_formulario_iciq(client, *, code=None, target_ids=None):
    """
    Arma un formulario de dos preguntas con puntaje por opción y una regla que
    los suma, imitando la forma del ICIQ-SF. Devuelve (form_id, section_id).
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


async def test_f2_un_borrador_ya_es_visible_para_la_usuaria(client, user):
    """
    create_form fuerza status=DRAFT, y list_forms no filtra por status.

    Al cerrar F2: un DRAFT no debe aparecer hasta publicarse.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.get(f"{ADMIN}/forms/{form_id}")
    assert r.json()["status"] == "draft"

    r = await client.get(f"{CLIN}/forms")
    assert form_id in [f["form_id"] for f in r.json()]  # visible aun siendo borrador


async def test_f3_un_formulario_sin_segmento_se_muestra_a_todas(client, user):
    """
    Al cerrar F3: un formulario sin segmento no debería alcanzar a todas por
    defecto, o al menos no combinado con F1.
    """
    form_id, _ = await crear_formulario_iciq(client, target_ids=[])
    r = await client.get(f"{CLIN}/forms")
    assert form_id in [f["form_id"] for f in r.json()]


async def test_f9_archivar_lo_saca_de_la_app_y_tambien_del_admin(client, user):
    """
    El borrado suave funciona de cara a la app, pero el listado del admin filtra
    is_active == True, así que el formulario archivado se vuelve inalcanzable.

    Al cerrar F9: debe seguir visible en el admin y poder restaurarse.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.delete(f"{ADMIN}/forms/{form_id}")
    assert r.status_code == 204

    r = await client.get(f"{CLIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()]  # correcto

    r = await client.get(f"{ADMIN}/forms")
    assert form_id not in [f["form_id"] for f in r.json()["items"]]  # queda huérfano


async def test_f10_el_filtro_de_archivados_nunca_devuelve_nada(client, user):
    """status se combina con is_active == True mediante AND: conjunto vacío."""
    form_id, _ = await crear_formulario_iciq(client)
    await client.delete(f"{ADMIN}/forms/{form_id}")

    r = await client.get(f"{ADMIN}/forms", params={"status": "archived"})
    assert r.json()["items"] == []


# ─────────────────────────────────────────────────────────────────────────────
# F5 · Periodicidad
# ─────────────────────────────────────────────────────────────────────────────


async def test_f5_un_formulario_de_unica_vez_reaparece_tras_completarlo(client, user):
    """
    frecuencia no se lee en ninguna parte: list_forms nunca consulta las
    submissions previas.

    Al cerrar F5: tras completarlo, un UNICA_VEZ no debe volver a listarse.
    """
    form_id, _ = await crear_formulario_iciq(client)
    await responder(
        client, form_id, {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca"}
    )

    r = await client.get(f"{CLIN}/forms")
    assert form_id in [f["form_id"] for f in r.json()]  # sigue ahí, ya respondido


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


async def test_f14_el_simulador_falla_con_preguntas_de_puntaje_por_opcion(
    client, user
):
    """
    `engine` y `target_ids_str` se usan 17 líneas antes de definirse. El
    UnboundLocalError sale como 500 por el except genérico.

    Al cerrar F14: 200 con el puntaje calculado.
    """
    form_id, _ = await crear_formulario_iciq(client)

    r = await client.post(
        f"{ADMIN}/forms/{form_id}/simulate",
        json={"answers": {"iciq_frecuencia": "diario", "iciq_cantidad": "moderada"}},
    )
    assert r.status_code == 500
    assert "engine" in r.json()["detail"]


async def test_f15_las_reglas_por_segmento_se_saltean_en_produccion(
    client, user, target_embarazadas, db_session
):
    """
    finalize_submission llama process_rules sin user_target_ids, así que toda
    regla con target_id se descarta con `continue`.

    Al cerrar F15: la regla debe aplicarse si la usuaria tiene ese segmento.
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

    assert "iciq_total" in sub["calculated_values"]
    assert "riesgo_embarazo" not in sub["calculated_values"]  # nunca se evaluó


async def test_f16_las_reglas_por_opcion_no_afectan_el_puntaje_real(
    client, user, target_embarazadas
):
    """
    finalize_submission calcula el puntaje en línea en vez de llamar a
    resolve_answer_score, así que context_rules queda sin efecto.

    Al cerrar F16: con el segmento activo el puntaje debe ser el sobrescrito.
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

    _, sub = await responder(
        client,
        form_id,
        {"iciq_frecuencia": "nunca", "iciq_cantidad": "poca", "dolor": "si"},
    )

    # El override de 99 se ignora: el total sigue siendo el puntaje base.
    assert sub["calculated_values"]["iciq_total"] == 0


async def test_f17_el_puntaje_total_solo_reconoce_los_nombres_de_iciq(client, user):
    """
    La heurística busca 'iciq_total' y 'total_score'. Cualquier otro nombre
    deja total_score en cero, en silencio.

    Al cerrar F17: el formulario debe poder declarar cuál es su variable total.
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
    assert sub["total_score"] == 0  # calculado pero no promovido


# ─────────────────────────────────────────────────────────────────────────────
# F20 / F21 · Persistencia e integridad
# ─────────────────────────────────────────────────────────────────────────────


async def test_f20_guardar_dos_veces_duplica_las_respuestas(client, user, db_session):
    """
    save_answers inserta en vez de actualizar.

    Al cerrar F20: la segunda escritura debe reemplazar a la primera.
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
    assert total == 2  # quedan las dos versiones de la misma pregunta


async def test_f21_se_puede_cerrar_la_evaluacion_de_otra_usuaria(
    client, user, otra_usuaria
):
    """
    Ni save_answers ni finalize_submission comparan contra la usuaria
    autenticada.

    Al cerrar F21: ambas deben responder 404 sobre una evaluación ajena.
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

    # test_uid_123 escribe y cierra la evaluación de otra_uid_456
    r = await client.put(
        f"{CLIN}/submissions/{sub_ajena}/answers",
        json={"answers": [{"question_id": qid, "value": "diario"}]},
    )
    assert r.status_code == 200

    r = await client.post(f"{CLIN}/submissions/{sub_ajena}/finalize")
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


async def test_f33_una_regla_con_alerta_sin_tipo_rompe_el_cierre(client, user):
    """
    scoring.py hace `rule.alert_type or AlertType.INFO`, y ese miembro no
    existe en el enum: solo hay DERIVACION_CLINICA, ACTIVAR_PLAN y SEGUIMIENTO.

    El admin permite crear una regla con condición de alerta y sin tipo, así
    que en cuanto esa alerta se dispara el cierre de la evaluación explota con
    AttributeError. Es la funcionalidad central del motor clínico —generar
    derivaciones— y está caída.

    Al cerrar F33: el cierre debe completarse y persistir la alerta con un tipo
    por defecto válido.
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

    with pytest.raises(AttributeError, match="AlertType.*INFO"):
        await client.post(f"{CLIN}/submissions/{sub_id}/finalize")


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
