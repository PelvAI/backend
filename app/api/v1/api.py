from fastapi import APIRouter
from app.api.v1.endpoints import auth, clinical, training, gamification, profiles, orgs, map, ai, subscriptions, system, education, admin_forms

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(orgs.router, tags=["orgs"]) # Orgs has top level /orgs and /my-links, so no prefix or handle inside
api_router.include_router(clinical.router, prefix="/clinical", tags=["clinical"])
api_router.include_router(map.router, tags=["map"]) # Map has /paths /nodes
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(gamification.router, prefix="/gamification", tags=["gamification"])
api_router.include_router(subscriptions.router, tags=["subscriptions"]) # Mixed /subscriptions /ads
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(education.router, prefix="/education", tags=["education"])

# Admin endpoints
api_router.include_router(admin_forms.router, prefix="/admin", tags=["admin"])

