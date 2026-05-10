
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging
from simpleeval import simple_eval, NameNotDefined, InvalidExpression
from app.models.clinical import ScoringRule, AlertType

logger = logging.getLogger(__name__)

@dataclass
class AlertResult:
    rule_id: str
    alert_type: str
    level: str
    message: str

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
            
            # Check if user has ALL required targets (AND logic)
            match = False
            if required_targets:
                # Check intersection: If user has ANY of the required targets?
                # Usually targets in rules means "Applies if user is X".
                # If rule has ["Athlete", "Pregnant"] -> usually implies OR in UI chips?
                # But "Combined Rules" UI implies "Combination" -> AND.
                # Let's support AND for specificity.
                if set(required_targets).issubset(set(user_target_ids)):
                   match = True
            else:
                # No target condition?
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
                    alert = AlertResult(
                        rule_id=str(rule.rule_id),
                        alert_type=rule.alert_type or AlertType.INFO,
                        level="high",
                        message=f"Alert triggered by: {rule.variable_name}"
                    )
                    triggered_alerts.append(alert)

        return calculated_scores, triggered_alerts
