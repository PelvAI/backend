from datetime import datetime, timedelta
from typing import List, Set
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import Profile
from app.models.clinical import Target

class TagAutomationService:
    @staticmethod
    async def sync_profile_tags(db: AsyncSession, profile_id: UUID) -> Profile:
        """
        Calculates and updates clinical tags (Targets) for a user profile
        based on their clinical dates (due_date, delivery_date, etc.).
        """
        # 1. Fetch profile with current targets
        result = await db.execute(
            select(Profile)
            .options(selectinload(Profile.targets))
            .where(Profile.profile_id == profile_id)
        )
        profile = result.scalars().first()
        if not profile:
            return None

        # 2. Fetch all available targets to avoid missing codes
        target_result = await db.execute(select(Target))
        all_targets = {t.code.upper(): t for t in target_result.scalars().all()}

        # 3. Calculate desired tags
        desired_codes = TagAutomationService._calculate_desired_codes(profile)
        
        # 4. Map codes to Target objects
        desired_targets = []
        for code in desired_codes:
            if code in all_targets:
                desired_targets.append(all_targets[code])
            elif code == "TODAS" and "todas" in all_targets: # handle case sensitivity
                desired_targets.append(all_targets["todas"])

        # 5. Update collection (SQLAlchemy handles the join table)
        profile.targets = desired_targets
        
        await db.commit()
        await db.refresh(profile, ["targets"])
        return profile

    @staticmethod
    def _calculate_desired_codes(profile: Profile) -> Set[str]:
        """
        Pure logic to determine which tag codes a user should have.
        """
        codes = {"todas"} # Always include the global tag
        now = datetime.utcnow()

        # A. POST-PARTUM LOGIC (Takes precedence)
        if profile.delivery_date:
            months_since_delivery = (now - profile.delivery_date).days / 30
            if months_since_delivery < 6:
                codes.add("POSTPARTUM")
            return codes # If postpartum is set, usually we don't show PREGNANT

        # B. PREGNANCY LOGIC
        is_pregnant = False
        
        # By Last Period (LMP)
        if profile.last_period_date:
            weeks_since_lmp = (now - profile.last_period_date).days / 7
            if 0 <= weeks_since_lmp < 42:
                is_pregnant = True
        
        # By Due Date
        if profile.due_date and not is_pregnant:
            # If due date is in the future, or very recent past (without delivery_date set)
            days_to_due = (profile.due_date - now).days
            if -14 <= days_to_due <= 280: # From conception to 2 weeks overdue
                is_pregnant = True

        if is_pregnant:
            codes.add("PREGNANT")

        # C. OTHER LOGIC (Can be added here, like MENOPAUSE based on age/date)
        
        return codes

    @staticmethod
    def get_pregnancy_week(profile: Profile) -> int:
        """
        Helper to calculate the current pregnancy week for UI display.
        """
        if not profile.last_period_date and not profile.due_date:
            return None
            
        now = datetime.utcnow()
        if profile.last_period_date:
            return int((now - profile.last_period_date).days / 7)
        
        if profile.due_date:
            # Estimated LMP = Due Date - 280 days
            est_lmp = profile.due_date - timedelta(days=280)
            return int((now - est_lmp).days / 7)
            
        return None
