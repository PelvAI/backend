import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import configure_mappers

from app.db.session import AsyncSessionLocal
from app.db.base import * # Import all models for relationships
from app.models.clinical import (
    ClinicalForm, FormSection, FormQuestion, QuestionType, 
    AnswerOption, ScoringRule, ScoreMode, Target, FormStatus
)

# Force SQLAlchemy to recognize all relationships
configure_mappers()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    async with AsyncSessionLocal() as db:
        logger.info("🚀 Starting Master Seeding Process (Production Ready)...")

        # --- 1. CLEANUP ---
        # NOTA PARA EL SERVIDOR/PRODUCCIÓN:
        # Se realiza una limpieza en cascada respetando las dependencias de llaves foráneas para evitar
        # el error ForeignKeyViolationError. Correr este script en cualquier servidor vaciará estas tablas.
        # Clear existing definitions in dependency order to ensure fresh state
        await db.execute(delete(ClinicalSnapshot))
        await db.execute(delete(Profile))
        await db.execute(delete(Wallet))
        await db.execute(delete(User))
        await db.execute(delete(ClinicalForm))
        await db.execute(delete(Target))
        await db.execute(delete(Exercise))
        await db.commit()

        # --- 2. TARGETS (Segmentation) ---
        target_data = [
            ("todas", "Todas", "Público General"),
            ("PREGNANT", "Embarazadas", "Usuarias en etapa de gestación"),
            ("POSTPARTUM", "Post-parto", "Usuarias en etapa de recuperación post-parto"),
            ("menopausia", "Menopausia", "Usuarias en etapa de menopausia"),
            ("deportista", "Deportista", "Usuarias con alta actividad física")
        ]
        
        targets = {}
        for code, name, desc in target_data:
            t = Target(code=code, name=name, description=desc)
            db.add(t)
            await db.flush()
            targets[code] = t
        logger.info(f"Created {len(targets)} clinical targets.")

        # --- 3. CLINICAL FORMS (Professional Standards) ---
        
        # A. ICIQ-SF (Incontinence)
        iciq = ClinicalForm(
            code="iciq_sf", 
            title_key="Consulta Internacional sobre Incontinencia (ICIQ-SF)", 
            description_key="Evaluación estándar de síntomas de pérdida de orina.",
            status=FormStatus.ACTIVE
        )
        iciq.targets.append(targets["todas"])
        db.add(iciq)
        await db.flush()
        
        sec_iciq = FormSection(form_id=iciq.form_id, title_key="Síntomas Urinarios", order_index=1)
        db.add(sec_iciq)
        await db.flush()

        # Q1: Frequency
        q1 = FormQuestion(
            section_id=sec_iciq.section_id, id_pregunta="ICIQ_1", data_key="freq", 
            text_key="¿Con qué frecuencia pierde orina?", type=QuestionType.single, 
            score_mode=ScoreMode.OPTION_SCORE, order_index=1
        )
        db.add(q1)
        await db.flush()
        for v, txt, s in [("0", "Nunca", 0), ("1", "Una vez a la semana o menos", 1), ("2", "Dos o tres veces a la semana", 2), ("3", "Una vez al día", 3), ("4", "Varias veces al día", 4), ("5", "Siempre", 5)]:
            db.add(AnswerOption(question_id=q1.question_id, value=v, label_key=txt, score=s))

        # Q2: Amount
        q2 = FormQuestion(
            section_id=sec_iciq.section_id, id_pregunta="ICIQ_2", data_key="amount", 
            text_key="¿Qué cantidad de orina cree que pierde?", type=QuestionType.single, 
            score_mode=ScoreMode.OPTION_SCORE, order_index=2
        )
        db.add(q2)
        await db.flush()
        for v, txt, s in [("0", "Ninguna", 0), ("1", "Poca cantidad", 2), ("2", "Una cantidad moderada", 4), ("3", "Mucha cantidad", 6)]:
            db.add(AnswerOption(question_id=q2.question_id, value=v, label_key=txt, score=s))

        # Q3: Impact
        q3 = FormQuestion(
            section_id=sec_iciq.section_id, id_pregunta="ICIQ_3", data_key="impact", 
            text_key="En general, ¿cuánto le afecta esta pérdida de orina en su vida diaria? (0: nada, 10: mucho)", 
            type=QuestionType.scale, score_mode=ScoreMode.VALUE_AS_SCORE, order_index=3, config={"min": 0, "max": 10}
        )
        db.add(q3)

        # B. PFDI-20 (POPDI-6 Section)
        pfdi = ClinicalForm(
            code="pfdi_20", 
            title_key="Inventario de Disfunción de Suelo Pélvico (PFDI-20)", 
            description_key="Evaluación integral de síntomas de prolapso y disfunciones pélvicas.",
            status=FormStatus.ACTIVE
        )
        pfdi.targets.append(targets["todas"])
        db.add(pfdi)
        await db.flush()

        sec_pop = FormSection(form_id=pfdi.form_id, title_key="Síntomas de Prolapso (POPDI-6)", order_index=1)
        db.add(sec_pop)
        await db.flush()

        pop_questions = [
            "¿Siente presión en la parte baja del abdomen?",
            "¿Siente pesadez o plenitud en la zona vaginal?",
            "¿Siente un bulto o que algo sale de su vagina?",
            "¿Tiene que empujar el bulto con los dedos para orinar?",
            "¿Siente que no vacía completamente la vejiga?",
            "¿Siente que no vacía completamente el intestino?"
        ]
        for idx, txt in enumerate(pop_questions):
            q = FormQuestion(
                section_id=sec_pop.section_id, id_pregunta=f"POPDI_{idx+1}", 
                data_key=f"popdi_{idx+1}", text_key=txt, type=QuestionType.single, 
                score_mode=ScoreMode.OPTION_SCORE, order_index=idx
            )
            db.add(q)
            await db.flush()
            for v, opt_txt, s in [("0", "Nada", 0), ("1", "Un poco", 1), ("2", "Moderadamente", 2), ("3", "Mucho", 3)]:
                db.add(AnswerOption(question_id=q.question_id, value=v, label_key=opt_txt, score=s))

        logger.info("Created professional clinical forms.")

        # --- 4. EXERCISES ---
        exercises_data = [
            {"code": "kegel_fast", "name": "Contracciones Rápidas", "cat": "Fortalecer"},
            {"code": "kegel_hold", "name": "Contracciones de Resistencia", "cat": "Fortalecer"},
            {"code": "breathing", "name": "Respiración Diafragmática", "cat": "Relajar"},
            {"code": "coordination", "name": "Coordinación con Movimiento", "cat": "Coordinar"}
        ]
        for ex_data in exercises_data:
            ex = Exercise(
                internal_code=ex_data["code"],
                video_path=f"/videos/{ex_data['code']}.mp4",
                meta_data={"name": ex_data["name"], "category": ex_data["cat"]}
            )
            db.add(ex)
        
        # --- 5. TEST USER (Ana) ---
        ana = User(firebase_uid="ana_test_123", email="ana@alma.com", is_active=True)
        db.add(ana)

        # --- 6. DEFAULT TEST USER (test_uid_123) ---
        test_user = User(firebase_uid="test_uid_123", email="test@alma.com", is_active=True)
        db.add(test_user)
        await db.flush()
        
        profile = Profile(
            user_id=ana.user_id, nickname="Ana", timezone="America/Argentina/Buenos_Aires", 
            preferred_language="es", gender="female", birth_date=datetime(1992, 8, 20)
        )
        db.add(profile)
        
        profile_test = Profile(
            user_id=test_user.user_id, nickname="Test", timezone="America/Argentina/Buenos_Aires", 
            preferred_language="es", gender="female", birth_date=datetime(1995, 1, 1)
        )
        db.add(profile_test)
        
        # Historical Snapshots
        for i in range(4):
            snap = ClinicalSnapshot(
                user_id=ana.user_id,
                last_updated=datetime.utcnow() - timedelta(weeks=4-i),
                data={"wellness": 40 + (i*10), "iciq_sf": 18 - (i*4)}
            )
            db.add(snap)

        await db.commit()
        logger.info("✅ Master Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
