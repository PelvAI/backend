import asyncio
import logging
from datetime import datetime, timedelta
from app.db.session import AsyncSessionLocal
from app.models.clinical import ClinicalForm, FormSection, FormQuestion, QuestionType, UserSubmission, SubmissionAnswer
from app.models.training import Exercise, SessionTemplate, UserAssignment, AssignmentStatus, SessionPerformance
from app.models.gamification import Currency, Wallet
from app.models.map import LearningPath
from app.models.business import SubscriptionPlan
from app.models.user import User, Profile
from app.models.education import EducationModule, EducationType
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    async with AsyncSessionLocal() as db:
        logger.info("Seeding Investor Demo Data...")

        # --- Currencies ---
        result = await db.execute(select(Currency).where(Currency.code == "XP"))
        if not result.scalars().first():
            xp = Currency(code="XP")
            db.add(xp)
            logger.info("Created Currency: XP")

        # --- Clinical Forms ---
        # 1. Onboarding
        result = await db.execute(select(ClinicalForm).where(ClinicalForm.code == "onboarding"))
        if not result.scalars().first():
            form = ClinicalForm(code="onboarding", version=1, is_active=True)
            db.add(form)
            await db.flush()
            
            s1 = FormSection(form_id=form.form_id, title_key="symptoms", order_index=1)
            db.add(s1)
            await db.flush()
            
            q1 = FormQuestion(section_id=s1.section_id, type=QuestionType.SINGLE_CHOICE, config={"text": "¿Sueles tener fugas de orina al toser, estornudar o saltar?", "options": ["Nunca", "A veces", "Frecuentemente", "Siempre"]})
            q2 = FormQuestion(section_id=s1.section_id, type=QuestionType.SINGLE_CHOICE, config={"text": "¿Sueles tener una sensación de bulto o pesadez en tu zona vaginal?", "options": ["Nunca", "A veces", "Frecuentemente", "Siempre"]})
            db.add_all([q1, q2])
            logger.info("Created Form: Onboarding")

        # 2. PFDI-20 (Pelvic Floor Distress Inventory)
        result = await db.execute(select(ClinicalForm).where(ClinicalForm.code == "pfdi20"))
        pfdi_form = result.scalars().first()
        if not pfdi_form:
            pfdi_form = ClinicalForm(code="pfdi20", version=1, is_active=True)
            db.add(pfdi_form)
            await db.flush()
            s_pfdi = FormSection(form_id=pfdi_form.form_id, title_key="symptoms", order_index=1)
            db.add(s_pfdi)
            await db.flush()
            # Simplified PFDI questions for demo
            q_pfdi1 = FormQuestion(section_id=s_pfdi.section_id, type=QuestionType.SCALE, config={"text": "Sensación de pesadez pélvica (0-100)", "min": 0, "max": 100})
            db.add(q_pfdi1)
            logger.info("Created Form: PFDI-20")

        # 3. Wellness Index
        result = await db.execute(select(ClinicalForm).where(ClinicalForm.code == "wellness"))
        wellness_form = result.scalars().first()
        if not wellness_form:
            wellness_form = ClinicalForm(code="wellness", version=1, is_active=True)
            db.add(wellness_form)
            await db.flush()
            s_well = FormSection(form_id=wellness_form.form_id, title_key="general", order_index=1)
            db.add(s_well)
            await db.flush()
            q_well1 = FormQuestion(section_id=s_well.section_id, type=QuestionType.SCALE, config={"text": "Bienestar General (0-100)", "min": 0, "max": 100})
            db.add(q_well1)
            logger.info("Created Form: Wellness Index")

        # --- Exercises ---
        exercises_data = [
            {"code": "kegel_fast", "name": "Contracciones Rápidas", "duration": 5, "category": "Fortalecer", "video": "/videos/kegel_fast.mp4"},
            {"code": "kegel_hold", "name": "Contracciones de Resistencia", "duration": 8, "category": "Fortalecer", "video": "/videos/kegel_hold.mp4"},
            {"code": "breathing", "name": "Respiración Diafragmática", "duration": 10, "category": "Relajar", "video": "/videos/breathing.mp4"},
            {"code": "coordination", "name": "Coordinación con Movimiento", "duration": 12, "category": "Coordinar", "video": "/videos/coordination.mp4"}
        ]
        
        created_exercises = []
        for ex_data in exercises_data:
            result = await db.execute(select(Exercise).where(Exercise.internal_code == ex_data["code"]))
            ex = result.scalars().first()
            if not ex:
                ex = Exercise(
                    internal_code=ex_data["code"],
                    video_path=ex_data["video"],
                    meta_data={"name": ex_data["name"], "duration": ex_data["duration"], "category": ex_data["category"]}
                )
                db.add(ex)
                await db.flush()
                logger.info(f"Created Exercise: {ex_data['name']}")
            created_exercises.append(ex)

        # --- Education Modules ---
        education_data = [
            {"title": "Anatomía del Suelo Pélvico", "type": EducationType.ARTICLE, "cat": "Anatomía", "content": "El suelo pélvico es un conjunto de músculos..."},
            {"title": "Suelo Pélvico y Deporte", "type": EducationType.ARTICLE, "cat": "Deporte", "content": "Impacto del deporte en el suelo pélvico..."},
            {"title": "Señales de Alarma", "type": EducationType.TIP, "cat": "Salud", "content": "Si sientes dolor..."},
            {"title": "Mitos y Verdades", "type": EducationType.VIDEO, "cat": "Mitos", "content": "Video url..."}
        ]

        for edu in education_data:
            result = await db.execute(select(EducationModule).where(EducationModule.title == edu["title"]))
            if not result.scalars().first():
                mod = EducationModule(title=edu["title"], type=edu["type"], category=edu["cat"], content=edu["content"])
                db.add(mod)
                logger.info(f"Created Education Module: {edu['title']}")

        # --- Test User ---
        result = await db.execute(select(User).where(User.email == "test@pelvia.com"))
        user = result.scalars().first()
        if not user:
            user = User(
                firebase_uid="test_uid_123",
                email="test@pelvia.com",
                is_active=True
            )
            db.add(user)
            await db.flush()
            
            profile = Profile(
                user_id=user.user_id,
                nickname="Ana",
                timezone="UTC",
                preferred_language="es",
                weight=65.5,
                height=170.0,
                birth_date=datetime(1990, 5, 15),
                gender="female"
            )
            db.add(profile)
            
            # Add Wallet
            xp_currency = (await db.execute(select(Currency).where(Currency.code == "XP"))).scalars().first()
            if xp_currency:
                wallet = Wallet(user_id=user.user_id, currency_id=xp_currency.currency_id, balance=450)
                db.add(wallet)
            
            logger.info("Created Test User: Ana")
        else:
            # Update existing profile with biometrics if missing
            profile_result = await db.execute(select(Profile).where(Profile.user_id == user.user_id))
            profile = profile_result.scalars().first()
            if profile:
                profile.nickname = "Ana"
                profile.weight = 65.5
                profile.height = 170.0
                profile.birth_date = datetime(1990, 5, 15)
                profile.gender = "female"
                db.add(profile)
                logger.info("Updated Test User Profile with Biometrics")

        # --- Historical Data (Simulated) ---
        # 1. Past Submissions (Wellness & PFDI)
        # Week 1
        date_w1 = datetime.utcnow() - timedelta(weeks=4)
        if pfdi_form:
            sub1 = UserSubmission(user_id=user.user_id, form_id=pfdi_form.form_id, created_at=date_w1)
            db.add(sub1)
        if wellness_form:
            sub2 = UserSubmission(user_id=user.user_id, form_id=wellness_form.form_id, created_at=date_w1)
            db.add(sub2)
        
        # Week 2
        date_w2 = datetime.utcnow() - timedelta(weeks=3)
        if pfdi_form:
            sub3 = UserSubmission(user_id=user.user_id, form_id=pfdi_form.form_id, created_at=date_w2)
            db.add(sub3)
        
        # 2. Past Workouts (Streak)
        # Create 7 days of completed assignments
        if created_exercises:
            template = SessionTemplate(name="Daily", exercises_config={}) # Dummy template
            db.add(template)
            await db.flush()

            for i in range(7):
                date = datetime.utcnow().date() - timedelta(days=i)
                # Check if exists
                exists = await db.execute(select(UserAssignment).where(UserAssignment.user_id == user.user_id, UserAssignment.date == date))
                if not exists.scalars().first():
                    assign = UserAssignment(
                        user_id=user.user_id,
                        template_id=template.template_id,
                        date=date,
                        status=AssignmentStatus.COMPLETED
                    )
                    db.add(assign)
            logger.info("Created 7-day workout streak history")

        # 3. Clinical Snapshots (Scores History)
        from app.models.clinical import ClinicalSnapshot
        
        # Week 1 (Low scores)
        snap1 = ClinicalSnapshot(
            user_id=user.user_id,
            last_updated=datetime.utcnow() - timedelta(weeks=4),
            data={"wellness": 45, "pfdi20": 85} # High PFDI is bad
        )
        db.add(snap1)
        
        # Week 2
        snap2 = ClinicalSnapshot(
            user_id=user.user_id,
            last_updated=datetime.utcnow() - timedelta(weeks=3),
            data={"wellness": 52, "pfdi20": 75}
        )
        db.add(snap2)
        
        # Week 3
        snap3 = ClinicalSnapshot(
            user_id=user.user_id,
            last_updated=datetime.utcnow() - timedelta(weeks=2),
            data={"wellness": 60, "pfdi20": 65}
        )
        db.add(snap3)
        
        # Week 4 (Current)
        snap4 = ClinicalSnapshot(
            user_id=user.user_id,
            last_updated=datetime.utcnow(),
            data={"wellness": 72, "pfdi20": 45} # Low PFDI is good
        )
        db.add(snap4)
        logger.info("Created Clinical Snapshots History")

        await db.commit()
        logger.info("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
