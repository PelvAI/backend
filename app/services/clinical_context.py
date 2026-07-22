from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai import AIMessage, SenderType
from app.models.clinical import ClinicalSnapshot
from app.models.training import AssignmentStatus, UserAssignment
from app.models.user import Profile, User


def _pregnancy_week(profile: Profile, now: datetime) -> Optional[int]:
    """Estima semana de gestação. Preferir last_period_date; senão due_date - 280d."""
    if profile.last_period_date:
        days = (now.date() - profile.last_period_date.date()).days
        if days < 0:
            return None
        return min(45, max(0, days // 7))
    if profile.due_date:
        est_lmp = profile.due_date - timedelta(days=280)
        days = (now.date() - est_lmp.date()).days
        if days < 0:
            return None
        return min(45, max(0, days // 7))
    return None


def _postpartum_weeks(profile: Profile, now: datetime) -> Optional[int]:
    if not profile.delivery_date:
        return None
    days = (now.date() - profile.delivery_date.date()).days
    if days < 0:
        return None
    return days // 7


def _summarize_daily_plan(assignment) -> Optional[str]:
    if not assignment or not assignment.template:
        return None
    name = assignment.template.name or "plan"
    return f"Asignación de hoy: {name} (status={assignment.status})."


async def build_clinical_context(
    db: AsyncSession,
    user: User,
    *,
    conversation_id: Optional[UUID] = None,
    history_limit: int = 12,
) -> dict[str, Any]:
    """
    Monta clinical_context v1 para o chatbot.
    Nunca inclui email, nickname, firebase_uid nem IDs de paciente.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Sempre carregar profile com selectinload (evita lazy-load async)
    result = await db.execute(
        select(Profile)
        .where(Profile.user_id == user.user_id)
        .options(selectinload(Profile.targets))
    )
    profile = result.scalars().first()

    preferred_language = "es"
    pregnancy_week = None
    postpartum_weeks = None
    clinical_targets: list[str] = []

    if profile:
        preferred_language = profile.preferred_language or "es"
        pregnancy_week = _pregnancy_week(profile, now)
        postpartum_weeks = _postpartum_weeks(profile, now)
        clinical_targets = [t.code for t in (profile.targets or []) if t.code]

    snap_result = await db.execute(
        select(ClinicalSnapshot)
        .where(ClinicalSnapshot.user_id == user.user_id)
        .order_by(ClinicalSnapshot.last_updated.desc())
        .limit(1)
    )
    snapshot = snap_result.scalars().first()
    scores = None
    if snapshot and snapshot.data:
        data = snapshot.data
        scores = {
            "iciq_sf": data.get("iciq_sf"),
            "pfdi_20": data.get("pfdi_20"),
            "wellness": data.get("wellness"),
        }
        scores = {k: v for k, v in scores.items() if v is not None} or None

    daily_plan_summary = None
    try:
        today = now.date()
        asg = await db.execute(
            select(UserAssignment)
            .options(selectinload(UserAssignment.template))
            .where(UserAssignment.user_id == user.user_id)
            .where(UserAssignment.date == today)
        )
        assignment = asg.scalars().first()
        if not assignment:
            asg = await db.execute(
                select(UserAssignment)
                .options(selectinload(UserAssignment.template))
                .where(UserAssignment.user_id == user.user_id)
                .where(UserAssignment.status == AssignmentStatus.PENDING)
                .order_by(UserAssignment.date)
                .limit(1)
            )
            assignment = asg.scalars().first()
        daily_plan_summary = _summarize_daily_plan(assignment)
    except Exception:
        daily_plan_summary = None

    history_pairs: list[list[str]] = []
    if conversation_id:
        msgs = await db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at)
            .limit(history_limit)
        )
        for m in msgs.scalars().all():
            if m.sender == SenderType.AI:
                role = "assistant"
            elif m.sender == SenderType.SYSTEM:
                role = "assistant"
            else:
                role = "user"
            text = (m.content_encrypted or "")[:2000]
            if text:
                history_pairs.append([role, text])

    ctx: dict[str, Any] = {
        "schema_version": "v1",
        "preferred_language": preferred_language,
        "clinical_targets": clinical_targets,
    }
    if pregnancy_week is not None:
        ctx["pregnancy_week"] = pregnancy_week
    if postpartum_weeks is not None:
        ctx["postpartum_weeks"] = postpartum_weeks
    if scores:
        ctx["scores"] = scores
    if daily_plan_summary:
        ctx["daily_plan_summary"] = daily_plan_summary[:2000]
    if history_pairs:
        ctx["history_pairs"] = history_pairs

    return ctx
