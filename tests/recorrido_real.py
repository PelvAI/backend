"""
Recorrido real del circuito de formularios, contra el sistema levantado.

No es una prueba de pytest: no lleva prefijo test_ a propósito, porque necesita
un servidor corriendo. Habla HTTP con el backend, que a su vez habla con
Postgres.

Existe porque las pruebas con SQLite y esquemas armados a mano no alcanzan:
este recorrido encontró que la respuesta que recibe la aplicación no incluía
show_if ni is_required, de modo que la lógica condicional y la validación de
obligatorias estaban implementadas en la app y no podían funcionar (F43).

    docker compose up db -d
    createdb / alembic upgrade head / python -m app.db.seeds
    DATABASE_URL=... CHATBOT_REQUIRED=false uvicorn app.main:app --port 8001
    python tests/recorrido_real.py
"""

import json
import sys

import httpx

BASE = "http://127.0.0.1:8001/api/v1"
ADMIN = {"Authorization": "Bearer test_uid_123"}
PACIENTE = {"Authorization": "Bearer ana_test_123"}

fallos = []


def ok(nombre, condicion, detalle=""):
    if condicion:
        print(f"  ✓ {nombre}")
    else:
        fallos.append(nombre)
        print(f"  ✗ {nombre}" + (f" — {detalle}" if detalle else ""))


c = httpx.Client(timeout=30)


def pedir(metodo, ruta, headers, **kw):
    r = c.request(metodo, BASE + ruta, headers=headers, **kw)
    return r


print("\n══ 1. CREACIÓN DESDE EL PANEL ══\n")

# Segmentos disponibles
r = pedir("GET", "/admin/targets", ADMIN)
ok("el panel lista los segmentos", r.status_code == 200, r.text[:120])
segmentos = {t["code"]: t["target_id"] for t in r.json()}
ok("la siembra dejó los segmentos esperados",
   {"todas", "PREGNANT", "POSTPARTUM"} <= set(segmentos), str(list(segmentos)))

# Crear formulario con segmento, como lo hace el editor tras la fase 1
r = pedir("POST", "/admin/forms", ADMIN, json={
    "code": "E2E_PELVICO",
    "title_key": "Evaluación de prueba",
    "description_key": "Recorrido completo",
    "target_ids": [segmentos["todas"]],
    "frecuencia": "unica_vez",
    "disparador": "al_registro",
})
ok("crea un formulario con su segmento", r.status_code == 201, r.text[:200])
form = r.json()
form_id = form["form_id"]
ok("el segmento quedó asignado",
   [t["code"] for t in form["targets"]] == ["todas"], str(form["targets"]))
ok("nace como borrador", form["status"] == "draft", form["status"])

# Dos secciones, como permite la fase 7
r = pedir("POST", f"/admin/forms/{form_id}/sections", ADMIN,
          json={"title_key": "Síntomas urinarios", "bloque": "URIN", "order_index": 0})
ok("crea la primera sección", r.status_code == 201, r.text[:150])
sec_urin = r.json()["section_id"]

r = pedir("POST", f"/admin/forms/{form_id}/sections", ADMIN,
          json={"title_key": "Síntomas de prolapso", "bloque": "PROL", "order_index": 1})
ok("crea la segunda sección", r.status_code == 201, r.text[:150])
sec_prol = r.json()["section_id"]

# Preguntas de varios tipos, incluida una condicionada
preguntas = [
    (sec_urin, {
        "data_key": "disparadora", "text_key": "¿Pierde orina alguna vez?",
        "type": "single", "score_mode": "option_score", "is_required": True,
        "order_index": 0,
        "options": [
            {"value": "no", "label_key": "No", "score": 0, "order_index": 0},
            {"value": "si", "label_key": "Sí", "score": 1, "order_index": 1},
        ],
    }),
    (sec_urin, {
        "data_key": "frecuencia", "text_key": "¿Con qué frecuencia?",
        "type": "single", "score_mode": "option_score",
        "show_if": "disparadora == 'si'", "order_index": 1,
        "options": [
            {"value": "0", "label_key": "Nunca", "score": 0, "order_index": 0},
            {"value": "3", "label_key": "Una vez al día", "score": 3, "order_index": 1},
            {"value": "5", "label_key": "Siempre", "score": 5, "order_index": 2},
        ],
    }),
    (sec_urin, {
        "data_key": "impacto", "text_key": "¿Cuánto le afecta? (0 a 10)",
        "type": "scale", "score_mode": "value_as_score", "order_index": 2,
    }),
    (sec_prol, {
        "data_key": "bulto", "text_key": "¿Siente un bulto?",
        "type": "single", "score_mode": "option_score", "order_index": 0,
        "options": [
            {"value": "no", "label_key": "No", "score": 0, "order_index": 0},
            {"value": "si", "label_key": "Sí", "score": 4, "order_index": 1},
        ],
    }),
    (sec_prol, {
        "data_key": "relato", "text_key": "¿Querés contarnos algo más?",
        "type": "paragraph", "score_mode": "none", "order_index": 1,
    }),
]

creadas = 0
for sec, payload in preguntas:
    r = pedir("POST", f"/admin/sections/{sec}/questions", ADMIN, json=payload)
    if r.status_code == 201:
        creadas += 1
    else:
        print(f"      fallo en {payload['data_key']}: {r.status_code} {r.text[:150]}")
ok(f"crea las {len(preguntas)} preguntas con sus opciones en línea", creadas == len(preguntas))

# Regla de puntuación
r = pedir("POST", f"/admin/forms/{form_id}/rules", ADMIN, json={
    "variable_name": "total_pelvico",
    "formula": "frecuencia + impacto + bulto",
    "is_total": True,
    "interpretation_ranges": {"0-4": "Leve", "5-10": "Moderado", ">=11": "Severo"},
    "order_index": 0,
})
ok("crea la regla del puntaje total", r.status_code == 201, r.text[:200])


print("\n══ 2. VISIBILIDAD: UN BORRADOR NO LLEGA A LA PACIENTE ══\n")

r = pedir("GET", "/clinical/forms", PACIENTE)
ok("la app responde su listado", r.status_code == 200, r.text[:150])
ids = [f["form_id"] for f in r.json()]
ok("el borrador NO aparece en la app", form_id not in ids)

r = pedir("GET", "/clinical/forms/E2E_PELVICO/schema", PACIENTE)
ok("tampoco se abre adivinando su código", r.status_code == 404, str(r.status_code))


print("\n══ 3. PUBLICACIÓN ══\n")

r = pedir("POST", f"/admin/forms/{form_id}/publish", ADMIN)
ok("publica", r.status_code == 200, r.text[:200])
ok("queda activo", r.json().get("status") == "active", str(r.json().get("status")))

r = pedir("GET", "/clinical/forms", PACIENTE)
entrada = next((f for f in r.json() if f["form_id"] == form_id), None)
ok("ahora sí aparece en la app", entrada is not None)
if entrada:
    ok("viene marcado como pendiente", entrada["availability"] == "disponible",
       entrada["availability"])


print("\n══ 3b. LA SEGMENTACIÓN FILTRA DE VERDAD ══\n")

# Ana sólo tiene el segmento "todas". Un formulario dirigido a embarazadas no
# debe alcanzarla.
r = pedir("POST", "/admin/forms", ADMIN, json={
    "code": "E2E_SOLO_EMBARAZADAS",
    "title_key": "Sólo para embarazadas",
    "target_ids": [segmentos["PREGNANT"]],
})
otro_id = r.json()["form_id"]
r = pedir("POST", f"/admin/forms/{otro_id}/sections", ADMIN,
          json={"title_key": "s", "bloque": "X", "order_index": 0})
otra_sec = r.json()["section_id"]
pedir("POST", f"/admin/sections/{otra_sec}/questions", ADMIN, json={
    "data_key": "x", "text_key": "x", "type": "single", "order_index": 0})
r = pedir("POST", f"/admin/forms/{otro_id}/publish", ADMIN)
ok("publica el dirigido a embarazadas", r.status_code == 200, r.text[:150])

r = pedir("GET", "/clinical/forms", PACIENTE)
ids = [f["form_id"] for f in r.json()]
ok("una usuaria sin ese segmento NO lo recibe", otro_id not in ids)
ok("pero sí recibe el dirigido a todas", form_id in ids)


print("\n══ 4. EL ESQUEMA QUE RECIBE LA APP ══\n")

r = pedir("GET", "/clinical/forms/E2E_PELVICO/schema", PACIENTE)
ok("la app obtiene el esquema", r.status_code == 200, r.text[:150])
esquema = r.json()

ok("llegan las dos secciones", len(esquema["sections"]) == 2,
   str(len(esquema["sections"])))
ok("con su bloque clínico",
   [s["bloque"] for s in esquema["sections"]] == ["URIN", "PROL"],
   str([s.get("bloque") for s in esquema["sections"]]))

todas = [q for s in esquema["sections"] for q in s["questions"]]
ok("llegan las cinco preguntas", len(todas) == 5, str(len(todas)))

por_clave = {q["data_key"]: q for q in todas}
ok("las opciones viajan con su puntaje",
   len(por_clave["frecuencia"]["options"]) == 3,
   str(len(por_clave["frecuencia"].get("options", []))))
ok("la condición show_if viaja",
   por_clave["frecuencia"]["show_if"] == "disparadora == 'si'",
   str(por_clave["frecuencia"].get("show_if")))
ok("lo obligatorio viaja marcado", por_clave["disparadora"]["is_required"] is True)
ok("lo no obligatorio también, en falso",
   por_clave["impacto"]["is_required"] is False)

with open("/tmp/esquema_real.json", "w") as f:
    json.dump(esquema, f)


print("\n══ 5. RESPONDER DESDE LA APP ══\n")

r = pedir("POST", "/clinical/submissions/start", PACIENTE, json={"form_id": form_id})
ok("abre la evaluación", r.status_code == 200, r.text[:200])
sub_id = r.json()["submission_id"]
ok("registra bajo qué versión responde", r.json().get("form_id") == form_id)

respuestas = {"disparadora": "si", "frecuencia": "5", "impacto": 8, "bulto": "si",
              "relato": "Empeoró después del parto."}
payload = {"answers": [
    {"question_id": por_clave[k]["question_id"], "value": v}
    for k, v in respuestas.items()
]}
r = pedir("PUT", f"/clinical/submissions/{sub_id}/answers", PACIENTE, json=payload)
ok("guarda las respuestas", r.status_code == 200, r.text[:200])

# Corregir una: no debe duplicar
payload2 = {"answers": [{"question_id": por_clave["impacto"]["question_id"], "value": 6}]}
r = pedir("PUT", f"/clinical/submissions/{sub_id}/answers", PACIENTE, json=payload2)
ok("corregir una respuesta no la duplica", r.status_code == 200, r.text[:200])

r = pedir("POST", f"/clinical/submissions/{sub_id}/finalize", PACIENTE)
ok("cierra la evaluación", r.status_code == 200, r.text[:300])
resultado = r.json()

# 5 (siempre) + 6 (impacto corregido) + 4 (bulto) = 15
ok("el puntaje es el esperado (5+6+4=15)", resultado.get("total_score") == 15,
   f"dio {resultado.get('total_score')}, valores={resultado.get('calculated_values')}")
ok("trae su interpretación", resultado.get("score_interpretation") == "Severo",
   str(resultado.get("score_interpretation")))


print("\n══ 6. DESPUÉS DE RESPONDER ══\n")

r = pedir("GET", "/clinical/forms", PACIENTE)
entrada = next((f for f in r.json() if f["form_id"] == form_id), None)
ok("queda marcado como completado",
   entrada and entrada["availability"] == "completado",
   entrada["availability"] if entrada else "no está")

r = pedir("GET", "/clinical/submissions/history", PACIENTE)
ok("aparece en su historial", r.status_code == 200 and len(r.json()) >= 1,
   str(r.status_code))


print("\n══ 7. EDICIÓN DESDE EL PANEL ══\n")

r = pedir("GET", f"/admin/forms/{form_id}", ADMIN)
ok("el panel relee el formulario completo", r.status_code == 200, r.text[:150])
detalle = r.json()
ok("avisa que hay evaluaciones respondidas", detalle["submission_count"] == 1,
   str(detalle.get("submission_count")))
ok("el editor recibe las dos secciones", len(detalle["sections"]) == 2)
ok("y la regla con sus rangos",
   detalle["scoring_rules"][0]["interpretation_ranges"] is not None)
ok("marcada como no validada clínicamente",
   detalle["scoring_rules"][0]["interpretation_validated"] is False)

r = pedir("PUT", f"/admin/forms/{form_id}", ADMIN,
          json={"title_key": "Evaluación de prueba (editada)"})
ok("edita los metadatos", r.status_code == 200, r.text[:150])

qid = por_clave["bulto"]["question_id"]
r = pedir("PUT", f"/admin/questions/{qid}", ADMIN,
          json={"text_key": "¿Siente un bulto o que algo sale?"})
ok("edita una pregunta", r.status_code == 200, r.text[:150])

r = pedir("DELETE", f"/admin/questions/{por_clave['relato']['question_id']}", ADMIN)
ok("borra una pregunta sin responder... ", r.status_code == 204, str(r.status_code))

r = pedir("DELETE", f"/admin/questions/{por_clave['bulto']['question_id']}", ADMIN)
ok("...y archiva una respondida sin romper", r.status_code == 204, str(r.status_code))

r = pedir("GET", f"/admin/forms/{form_id}", ADMIN)
restantes = [q["data_key"] for s in r.json()["sections"] for q in s["questions"]]
ok("las archivadas dejan de mostrarse en el editor",
   "bulto" not in restantes and "relato" not in restantes, str(restantes))

r = pedir("POST", f"/clinical/submissions/{sub_id}/finalize", PACIENTE)
ok("recalcular no le cambia el puntaje a quien ya respondió",
   r.json().get("total_score") == 15, str(r.json().get("total_score")))


print("\n══ 8. AISLAMIENTO ENTRE PACIENTES ══\n")

r = pedir("POST", f"/clinical/submissions/{sub_id}/finalize", ADMIN)
ok("otra usuaria no puede cerrar una evaluación ajena", r.status_code == 404,
   str(r.status_code))


print()
if fallos:
    print(f"  {len(fallos)} FALLO(S): " + ", ".join(fallos) + "\n")
    sys.exit(1)
print("  circuito completo verificado contra el sistema real\n")
