
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import logging
import re
from simpleeval import simple_eval, NameNotDefined, InvalidExpression
from app.models.clinical import ScoringRule, AlertType, ScoreMode

logger = logging.getLogger(__name__)

# Tipo con el que se persiste una alerta cuando la regla no declara uno. Antes
# acá se usaba AlertType.INFO, un miembro que nunca existió en el enum, así que
# toda alerta sin tipo explícito tumbaba el cierre de la evaluación con
# AttributeError (F33).
DEFAULT_ALERT_TYPE = AlertType.SEGUIMIENTO

# Sufijo con el que el valor crudo de una respuesta entra al contexto de las
# fórmulas. El data_key a secas sigue siendo el puntaje: cambiarlo reescribiría
# el significado de toda fórmula y de toda regla de recomendación ya escrita.
RAW_SUFFIX = "__valor"


@dataclass
class AlertResult:
    rule_id: str
    alert_type: str
    level: str
    message: str
    triggered_value: Optional[float] = None


@dataclass
class AnswerScore:
    """Puntaje resuelto de una respuesta concreta."""
    question_id: Any
    data_key: Optional[str]
    raw_value: Any
    score: float
    alert: Optional[dict] = None


@dataclass
class ScoringResult:
    """
    Resultado completo de puntuar una evaluación.

    `values` es lo único que se persiste en UserSubmission.calculated_values, y
    su forma no cambia respecto de la anterior a propósito: es el contexto que
    RecommendationService usa para decidir qué plan de entrenamiento se asigna,
    y alterarlo cambiaría prescripciones clínicas.

    `context` es el contexto completo que vieron las fórmulas —puntajes más
    valores crudos— y queda disponible para depurar y para el simulador.
    """
    values: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    answer_scores: List[AnswerScore] = field(default_factory=list)
    alerts: List[AlertResult] = field(default_factory=list)

    # Nulo, no cero, cuando la fórmula del total no resolvió. Un cero se lee
    # clínicamente como "sin síntomas", que puede ser exactamente lo contrario
    # de lo que pasó: basta que la mujer haya salteado un ítem para que la
    # fórmula no resuelva (F40).
    total_score: Optional[float] = None
    # Variables cuya fórmula no pudo evaluarse, normalmente porque falta alguna
    # respuesta que referencian.
    uncomputed: List[str] = field(default_factory=list)

    interpretation: Optional[str] = None
    # La interpretación surge de umbrales que son criterio clínico. Mientras la
    # regla no esté marcada como validada, la etiqueta se entrega igual pero
    # señalada: informa, no decide.
    interpretation_is_provisional: bool = False


class ScoringEngine:
    """
    Service responsible for evaluating scoring logic and generating alerts based on user submission data.
    Uses 'simpleeval' for safe execution of mathematical formulas and boolean conditions stored in the database.
    """

    def __init__(self):
        # Allow basic math functions if needed, e.g., max, min
        self.functions = {"max": max, "min": min, "abs": abs}

    def evaluate_expression(self, expression: str, context: Dict[str, Any]) -> Any:
        try:
            # simple_eval evaluates string expressions using the context variables
            return simple_eval(expression, names=context, functions=self.functions)
        except (NameNotDefined, InvalidExpression, SyntaxError) as e:
            logger.error(f"Error evaluating expression '{expression}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error evaluating '{expression}': {e}")
            return None

    def resolve_answer_score(self, option: Any, user_target_ids: List[str]) -> Dict[str, Any]:
        """
        Calculates the score for a selected option, applying context overrides.
        Returns a dict: {"score": int, "alert": Optional[AlertResult]}
        Args:
            option: AnswerOption object (SQLAlchemy model)
            user_target_ids: List of strings (targets active for user)
        """
        base_score = option.score
        result = {"score": base_score, "alert": None}

        if not option.context_rules:
            return result

        # Iterate rules. First match wins (Waterfall).
        # Rule structure: {"conditions": {"targets": ["t_id"]}, "override_score": 5}
        for rule in option.context_rules:
            conditions = rule.get("conditions", {})
            required_targets = conditions.get("targets", [])

            # La condición es conjuntiva: la usuaria debe tener TODOS los
            # segmentos de la regla. Una regla sin condiciones aplica siempre.
            if required_targets:
                match = set(required_targets).issubset(set(user_target_ids))
            else:
                match = True

            if match:
                override_score = rule.get("override_score", base_score)
                alert_config = rule.get("alert_config", None)

                result["score"] = override_score
                if alert_config:
                    result["alert"] = {
                        "type": alert_config.get("type", "info"),
                        "message": alert_config.get("message", ""),
                        "level": alert_config.get("level", "medium")
                    }
                return result

        return result

    # =========================================================================
    # CAMINO ÚNICO DE PUNTUACIÓN
    # =========================================================================

    def score_answers(
        self,
        questions: List[Any],
        raw_answers: Dict[Any, Any],
        user_target_ids: Optional[List[str]] = None,
    ) -> Tuple[List[AnswerScore], Dict[str, Any]]:
        """
        Resuelve el puntaje de cada respuesta y arma el contexto de fórmulas.

        `raw_answers` va indexado por question_id. Devuelve los puntajes por
        respuesta —con la alerta por opción que corresponda— y el contexto, que
        lleva el puntaje bajo el data_key y el valor crudo bajo
        `<data_key>__valor`.
        """
        targets = [str(t) for t in (user_target_ids or [])]
        resultados: List[AnswerScore] = []
        context: Dict[str, Any] = {}

        for question in questions:
            if question.question_id not in raw_answers:
                continue

            raw_value = raw_answers[question.question_id]
            score: float = 0
            alert: Optional[dict] = None

            if question.score_mode == ScoreMode.OPTION_SCORE:
                opcion = next(
                    (o for o in (question.options or []) if str(o.value) == str(raw_value)),
                    None,
                )
                if opcion is not None:
                    resuelto = self.resolve_answer_score(opcion, targets)
                    score = resuelto["score"]
                    alert = resuelto["alert"]
            elif question.score_mode == ScoreMode.VALUE_AS_SCORE:
                try:
                    score = float(raw_value)
                except (TypeError, ValueError):
                    score = 0

            resultados.append(
                AnswerScore(
                    question_id=question.question_id,
                    data_key=question.data_key,
                    raw_value=raw_value,
                    score=score,
                    alert=alert,
                )
            )

            if question.data_key:
                context[question.data_key] = score
                context[f"{question.data_key}{RAW_SUFFIX}"] = raw_value

        return resultados, context

    def score_submission(
        self,
        questions: List[Any],
        rules: List[ScoringRule],
        raw_answers: Dict[Any, Any],
        user_target_ids: Optional[List[str]] = None,
    ) -> ScoringResult:
        """
        Puntúa una evaluación de punta a punta.

        Es el único camino: lo usan tanto el cierre de una evaluación real como
        el simulador del panel. Antes eran dos implementaciones paralelas que
        divergieron —una aplicaba los segmentos y las reglas por opción y la
        otra no—, de modo que la clínica validaba en el simulador una regla que
        no era la que después se le calculaba a la paciente.
        """
        targets = [str(t) for t in (user_target_ids or [])]

        answer_scores, context = self.score_answers(questions, raw_answers, targets)

        values, rule_alerts = self.process_rules(rules, context, user_target_ids=targets)

        alerts = list(rule_alerts)
        for a in answer_scores:
            if a.alert:
                alerts.append(
                    AlertResult(
                        rule_id="",
                        alert_type=a.alert.get("type") or DEFAULT_ALERT_TYPE,
                        level=a.alert.get("level", "medium"),
                        message=a.alert.get("message", ""),
                        triggered_value=a.score,
                    )
                )

        # Reglas con fórmula que no llegaron a calcularse.
        uncomputed = [
            r.variable_name
            for r in rules
            if r.formula
            and r.variable_name not in values
            and not (r.target_id and str(r.target_id) not in targets)
        ]

        total_rule = self._find_total_rule(rules, values)
        total_score = None
        interpretation = None
        provisional = False

        if total_rule is not None:
            valor = values.get(total_rule.variable_name)
            if isinstance(valor, (int, float)):
                total_score = float(valor)
                interpretation = self._interpret(
                    getattr(total_rule, "interpretation_ranges", None), total_score
                )
                if interpretation is not None:
                    provisional = not getattr(
                        total_rule, "interpretation_validated", False
                    )
            else:
                logger.warning(
                    "No se pudo calcular el puntaje total %r: la fórmula no "
                    "resolvió, probablemente por respuestas faltantes",
                    total_rule.variable_name,
                )

        # Contexto completo para depuración y simulación; lo que se persiste es
        # `values`, cuya forma no cambia.
        full_context = dict(context)
        full_context.update(values)

        return ScoringResult(
            values=values,
            context=full_context,
            answer_scores=answer_scores,
            alerts=alerts,
            total_score=total_score,
            uncomputed=uncomputed,
            interpretation=interpretation,
            interpretation_is_provisional=provisional,
        )

    @staticmethod
    def _find_total_rule(rules: List[ScoringRule], values: Dict[str, Any]):
        """
        Determina qué regla produce el puntaje total.

        Preferencia: la regla marcada con is_total. Si el formulario no tiene
        ninguna —el caso de todo lo cargado antes de esa bandera— se recurre a
        los nombres que la heurística anterior reconocía, para no cambiarles el
        puntaje a los cuestionarios existentes.
        """
        marcadas = [r for r in rules if getattr(r, "is_total", False)]
        if marcadas:
            return sorted(marcadas, key=lambda r: r.order_index)[0]

        for legado in ("iciq_total", "total_score"):
            if legado in values:
                return next((r for r in rules if r.variable_name == legado), None)

        return None

    @staticmethod
    def _interpret(ranges: Optional[Dict[str, str]], value: float) -> Optional[str]:
        """
        Traduce un puntaje a su etiqueta clínica según los rangos del formulario.

        Acepta "0-5", ">10", ">=10", "<3", "<=3" y un número suelto. Los rangos
        se persistían desde el panel y nunca se evaluaban, así que la columna
        score_interpretation quedaba siempre nula (F29).
        """
        if not ranges:
            return None

        for expresion, etiqueta in ranges.items():
            texto = str(expresion).strip()
            try:
                m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", texto)
                if m and float(m.group(1)) <= value <= float(m.group(2)):
                    return etiqueta

                m = re.fullmatch(r"(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", texto)
                if m:
                    limite = float(m.group(2))
                    op = m.group(1)
                    if (
                        (op == ">" and value > limite)
                        or (op == ">=" and value >= limite)
                        or (op == "<" and value < limite)
                        or (op == "<=" and value <= limite)
                    ):
                        return etiqueta
                    continue

                if re.fullmatch(r"-?\d+(?:\.\d+)?", texto) and value == float(texto):
                    return etiqueta
            except ValueError:
                logger.warning(f"Rango de interpretación inválido: {expresion!r}")

        return None

    def process_rules(self, rules: List[ScoringRule], answers_context: Dict[str, Any], user_target_ids: Optional[List[str]] = None) -> Tuple[Dict[str, Any], List[AlertResult]]:
        calculated_scores = {}
        triggered_alerts = []

        context = answers_context.copy()
        sorted_rules = sorted(rules, key=lambda r: r.order_index)
        active_target_ids = set(str(uid) for uid in (user_target_ids or []))

        for rule in sorted_rules:
            # 0. Context Filter: Check if rule applies to this user
            if rule.target_id:
                if str(rule.target_id) not in active_target_ids:
                    continue

            # 1. Evaluate Formula (if present)
            if rule.formula:
                result = self.evaluate_expression(rule.formula, context)
                if result is not None:
                    context[rule.variable_name] = result
                    calculated_scores[rule.variable_name] = result

            # 2. Check Alert Condition
            if rule.alert_condition:
                is_triggered = self.evaluate_expression(rule.alert_condition, context)

                if is_triggered:
                    disparador = context.get(rule.variable_name)
                    alert = AlertResult(
                        rule_id=str(rule.rule_id),
                        alert_type=rule.alert_type or DEFAULT_ALERT_TYPE,
                        level="high",
                        message=f"Alert triggered by: {rule.variable_name}",
                        triggered_value=(
                            float(disparador)
                            if isinstance(disparador, (int, float))
                            else None
                        ),
                    )
                    triggered_alerts.append(alert)

        return calculated_scores, triggered_alerts
