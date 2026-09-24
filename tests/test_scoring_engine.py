"""
Pruebas del motor de scoring, a nivel unitario.

Preparación de la FASE 2 del plan: antes de unificar el camino del simulador
con el de producción hay que fijar qué hace hoy cada pieza por separado. Estas
pruebas son deliberadamente de grano fino —operan sobre ScoringEngine sin pasar
por HTTP— porque la fase 2 cambia resultados clínicos y conviene ver
exactamente cuáles.

Complementan tests/test_forms_flow.py, que cubre el recorrido completo.
"""

from types import SimpleNamespace
from uuid import uuid4

from app.models.clinical import AlertType
from app.services.scoring import DEFAULT_ALERT_TYPE, RAW_SUFFIX, ScoringEngine


def opcion(score, context_rules=None):
    return SimpleNamespace(score=score, context_rules=context_rules)


def regla(variable_name, formula=None, alert_condition=None, target_id=None, order=0):
    return SimpleNamespace(
        rule_id=uuid4(),
        variable_name=variable_name,
        formula=formula,
        alert_condition=alert_condition,
        alert_type=None,
        target_id=target_id,
        order_index=order,
    )


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_expression
# ─────────────────────────────────────────────────────────────────────────────


def test_una_formula_valida_se_evalua():
    e = ScoringEngine()
    assert e.evaluate_expression("a + b", {"a": 4, "b": 3}) == 7


def test_una_variable_ausente_devuelve_none_en_vez_de_propagar():
    """
    El motor traga el error y devuelve None. Es intencional —una fórmula mal
    escrita no debe tumbar el cierre de una evaluación— pero significa que una
    fórmula que referencia una pregunta sin responder no calcula nada y no
    avisa.
    """
    e = ScoringEngine()
    assert e.evaluate_expression("a + inexistente", {"a": 1}) is None


def test_las_funciones_permitidas_son_solo_max_min_abs():
    e = ScoringEngine()
    assert e.evaluate_expression("max(a, b)", {"a": 2, "b": 9}) == 9
    assert e.evaluate_expression("round(a)", {"a": 2.4}) is None


# ─────────────────────────────────────────────────────────────────────────────
# F30 · resolve_answer_score devuelve un diccionario
# ─────────────────────────────────────────────────────────────────────────────


def test_f30_resolve_answer_score_devuelve_un_dict_no_un_numero():
    """
    Devuelve {"score": n, "alert": ...}. El simulador lo asigna tal cual al
    contexto de las fórmulas, así que la fórmula recibe un diccionario.

    Es un segundo bug detrás de F14: incluso arreglando el UnboundLocalError,
    el simulador seguiría sin calcular nada.

    Al cerrar F30: la función compartida debe poner en el contexto el número y
    encaminar la alerta por separado.
    """
    e = ScoringEngine()
    r = e.resolve_answer_score(opcion(4), [])

    assert isinstance(r, dict)
    assert r == {"score": 4, "alert": None}


def test_f30_un_dict_en_el_contexto_anula_la_formula():
    """La consecuencia concreta, medida."""
    e = ScoringEngine()
    r = e.resolve_answer_score(opcion(4), [])

    # Tal como lo hace el simulador hoy
    assert e.evaluate_expression("a + b", {"a": r, "b": r}) is None
    # Con el número, que es lo que corresponde
    assert e.evaluate_expression("a + b", {"a": r["score"], "b": 3}) == 7


# ─────────────────────────────────────────────────────────────────────────────
# resolve_answer_score · reglas contextuales por opción
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_reglas_contextuales_devuelve_el_puntaje_base():
    e = ScoringEngine()
    assert e.resolve_answer_score(opcion(3), ["cualquiera"])["score"] == 3


def test_una_regla_contextual_sobrescribe_si_la_usuaria_tiene_el_segmento():
    e = ScoringEngine()
    reglas = [{"conditions": {"targets": ["emb"]}, "override_score": 99}]
    assert e.resolve_answer_score(opcion(1, reglas), ["emb"])["score"] == 99


def test_una_regla_contextual_no_aplica_sin_el_segmento():
    e = ScoringEngine()
    reglas = [{"conditions": {"targets": ["emb"]}, "override_score": 99}]
    assert e.resolve_answer_score(opcion(1, reglas), ["otro"])["score"] == 1


def test_una_regla_de_varios_segmentos_exige_todos():
    """
    La condición es conjuntiva: subconjunto de los segmentos de la usuaria.
    Vale fijarlo porque el comentario del código dudaba entre Y y O.
    """
    e = ScoringEngine()
    reglas = [{"conditions": {"targets": ["emb", "atleta"]}, "override_score": 50}]

    assert e.resolve_answer_score(opcion(1, reglas), ["emb"])["score"] == 1
    assert e.resolve_answer_score(opcion(1, reglas), ["emb", "atleta"])["score"] == 50
    assert (
        e.resolve_answer_score(opcion(1, reglas), ["emb", "atleta", "extra"])["score"]
        == 50
    )


def test_gana_la_primera_regla_que_coincide():
    e = ScoringEngine()
    reglas = [
        {"conditions": {"targets": ["emb"]}, "override_score": 10},
        {"conditions": {"targets": ["emb"]}, "override_score": 20},
    ]
    assert e.resolve_answer_score(opcion(1, reglas), ["emb"])["score"] == 10


def test_una_regla_sin_condiciones_aplica_siempre():
    e = ScoringEngine()
    reglas = [{"conditions": {}, "override_score": 7}]
    assert e.resolve_answer_score(opcion(1, reglas), [])["score"] == 7


def test_la_alerta_por_opcion_se_devuelve_pero_nadie_la_consume():
    """
    Producción no llama a este método y el simulador descarta el campo, así que
    las alertas por opción están muertas de punta a punta (parte de F16).

    Al cerrar F16: la función compartida debe recolectarlas.
    """
    e = ScoringEngine()
    reglas = [
        {
            "conditions": {},
            "override_score": 5,
            "alert_config": {"type": "derivacion_clinica", "message": "Derivar"},
        }
    ]
    r = e.resolve_answer_score(opcion(1, reglas), [])

    assert r["score"] == 5
    assert r["alert"]["message"] == "Derivar"


# ─────────────────────────────────────────────────────────────────────────────
# process_rules
# ─────────────────────────────────────────────────────────────────────────────


def test_las_reglas_se_evaluan_en_orden_y_se_encadenan():
    """
    Una regla puede usar la variable que calculó la anterior: el contexto se va
    enriqueciendo. Por eso order_index importa.
    """
    e = ScoringEngine()
    reglas = [
        regla("subtotal", formula="a + b", order=0),
        regla("doble", formula="subtotal * 2", order=1),
    ]
    scores, _ = e.process_rules(reglas, {"a": 2, "b": 3})

    assert scores == {"subtotal": 5, "doble": 10}


def test_el_orden_inverso_rompe_el_encadenamiento_en_silencio():
    """
    Si la regla dependiente corre primero, su variable no existe todavía: la
    fórmula devuelve None y la variable no se calcula, sin error visible.
    """
    e = ScoringEngine()
    reglas = [
        regla("doble", formula="subtotal * 2", order=0),
        regla("subtotal", formula="a + b", order=1),
    ]
    scores, _ = e.process_rules(reglas, {"a": 2, "b": 3})

    assert "doble" not in scores
    assert scores == {"subtotal": 5}


def test_f15_una_regla_con_segmento_se_saltea_si_no_se_pasan_targets():
    """
    Es exactamente lo que hace finalize_submission: llama sin user_target_ids,
    así que active_target_ids queda vacío y la regla se descarta.

    Al cerrar F15: producción debe pasar los segmentos del perfil.
    """
    e = ScoringEngine()
    tid = uuid4()
    reglas = [regla("riesgo", formula="a * 10", target_id=tid)]

    scores, _ = e.process_rules(reglas, {"a": 2})
    assert scores == {}

    scores, _ = e.process_rules(reglas, {"a": 2}, user_target_ids=[str(tid)])
    assert scores == {"riesgo": 20}


def test_una_regla_sin_segmento_aplica_a_todas():
    e = ScoringEngine()
    scores, _ = e.process_rules([regla("t", formula="a")], {"a": 1})
    assert scores == {"t": 1}


def test_una_alerta_se_dispara_cuando_su_condicion_es_verdadera():
    e = ScoringEngine()
    reglas = [regla("total", formula="a + b", alert_condition="total >= 10")]

    _, alertas = e.process_rules(reglas, {"a": 6, "b": 5})
    assert len(alertas) == 1

    _, alertas = e.process_rules(reglas, {"a": 1, "b": 1})
    assert alertas == []


def test_la_alerta_si_registra_el_valor_que_la_disparo():
    """
    CERRADO en la fase 2 (F19 parcial): AlertResult lleva ahora el valor
    evaluado, que es lo que se persiste en ClinicalAlert.triggered_value en vez
    del cero fijo anterior.
    """
    e = ScoringEngine()
    reglas = [regla("total", formula="a", alert_condition="total >= 1")]
    _, alertas = e.process_rules(reglas, {"a": 42})

    assert alertas[0].triggered_value == 42
    assert alertas[0].alert_type == DEFAULT_ALERT_TYPE


def test_f33_el_tipo_por_defecto_es_un_miembro_real_del_enum():
    """
    CERRADO en la fase 2. Antes se usaba AlertType.INFO, inexistente, y toda
    alerta sin tipo explícito tumbaba el cierre con AttributeError.
    """
    assert DEFAULT_ALERT_TYPE in list(AlertType)
    assert not hasattr(AlertType, "INFO")


def test_f29_los_rangos_de_interpretacion_se_traducen_a_una_etiqueta():
    """
    CERRADO en la fase 2. Los rangos se persistían desde el panel y nunca se
    evaluaban, así que score_interpretation quedaba siempre nulo.
    """
    e = ScoringEngine()
    assert e._interpret({"0-5": "Leve", "6-10": "Moderado"}, 8) == "Moderado"
    assert e._interpret({"0-5": "Leve", "6-10": "Moderado"}, 3) == "Leve"
    assert e._interpret({"0-5": "Leve", ">10": "Severo"}, 42) == "Severo"
    assert e._interpret({">=10": "Alto"}, 10) == "Alto"
    assert e._interpret({"<3": "Bajo"}, 2) == "Bajo"
    assert e._interpret({"7": "Justo"}, 7) == "Justo"


def test_f29_un_valor_fuera_de_todo_rango_no_inventa_etiqueta():
    e = ScoringEngine()
    assert e._interpret({"0-5": "Leve"}, 99) is None
    assert e._interpret(None, 3) is None


def test_f29_un_rango_mal_escrito_no_tumba_la_interpretacion():
    """Un rango inválido se ignora y los demás siguen evaluándose."""
    e = ScoringEngine()
    assert e._interpret({"basura": "X", "0-5": "Leve"}, 3) == "Leve"
