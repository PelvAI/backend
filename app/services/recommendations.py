from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.recommendations import RecommendationRule, RuleActionType
from app.models.clinical import UserSubmission
from app.api.v1.endpoints.training import get_daily_plan, update_session_progress # Stub
 # We need direct DB access to assign training, not via router
from app.models.training import UserAssignment, AssignmentStatus, SessionTemplate
from app.models.gamification import UserStreak
import logging
from simpleeval import simple_eval
from datetime import date, datetime
import uuid

logger = logging.getLogger(__name__)

class RecommendationService:
    @staticmethod
    async def evaluate_submission(db: AsyncSession, submission: UserSubmission):
        """
        Evaluates active rules against the submission result.
        Triggered actions (ASSIGN_TRAINING, etc.) are executed.
        """
        logger.info(f"Evaluating submission {submission.submission_id} for recommendations.")
        
        # 1. Fetch Active Rules
        result = await db.execute(
            select(RecommendationRule)
            .where(RecommendationRule.is_active == True)
            .order_by(RecommendationRule.priority.desc())
        )
        rules = result.scalars().all()
        
        context = submission.calculated_values or {}
        # Also Flatten answers if needed?
        # For now, we rely on calculated_values (e.g. iciq_total)
        
        triggered_rules = []
        
        for rule in rules:
            if not rule.condition_expression:
                continue
                
            # Filter by form code if set
            if rule.target_form_code:
                # Need to load form to check code
                # or submission.form.code if loaded
                # submission.form_id is available.
                # Assuming context matching for now or robust check later.
                pass 

            try:
                # Context must be Dict[str, Any]
                # safe_eval
                is_triggered = simple_eval(rule.condition_expression, names=context)
                if is_triggered:
                    triggered_rules.append(rule)
                    logger.info(f"Rule triggered: {rule.name}")
                    
                    # Execute Action
                    await RecommendationService.execute_action(db, rule, submission)
                    
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
                
        return triggered_rules

    @staticmethod
    async def execute_action(db: AsyncSession, rule: RecommendationRule, submission: UserSubmission):
        if rule.action_type == RuleActionType.ASSIGN_TRAINING:
            await RecommendationService.assign_training_plan(db, submission.user_id, rule.target_id)
        elif rule.action_type == RuleActionType.SEND_EMAIL:
            logger.info("Email action skipped (stub).")
            
    @staticmethod
    async def assign_training_plan(db: AsyncSession, user_id: uuid.UUID, template_id: uuid.UUID):
        """
        Assigns a specific session template to the user for TODAY.
        If an assignment exists for today, it might overwrite or skip depending on logic.
        """
        today = date.today()
        
        # Check if already assigned
        result = await db.execute(
            select(UserAssignment)
            .where(UserAssignment.user_id == user_id)
            .where(UserAssignment.date == today)
        )
        existing = result.scalars().first()
        
        if existing:
            # Overwrite? Or just log?
            logger.info(f"User {user_id} already has assignment for today. Updating template.")
            existing.template_id = template_id
            existing.status = AssignmentStatus.PENDING
        else:
            new_assign = UserAssignment(
                user_id=user_id,
                template_id=template_id,
                date=today,
                status=AssignmentStatus.PENDING
            )
            db.add(new_assign)
            
        await db.commit()
        logger.info(f"Assigned Template {template_id} to User {user_id}")

class GamificationService:
    @staticmethod
    async def update_streak(db: AsyncSession, user_id: uuid.UUID):
        """
        Updates variable 'current_streak' based on activity via date check.
        """
        today = datetime.utcnow()
        
        result = await db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
        streak = result.scalars().first()
        
        if not streak:
            streak = UserStreak(user_id=user_id, current_streak=1, max_streak=1, last_activity_date=today)
            db.add(streak)
        else:
            # Logic: verify dates
            last = streak.last_activity_date
            delta = (today.date() - last.date()).days
            
            if delta == 0:
                pass # Already active today
            elif delta == 1:
                streak.current_streak += 1
                streak.max_streak = max(streak.max_streak, streak.current_streak)
            else:
                streak.current_streak = 1 # Reset
            
            streak.last_activity_date = today
            
        await db.commit()
