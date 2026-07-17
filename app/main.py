from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base # Register all models
from app.api.v1.api import api_router

app = FastAPI(
    title="ALMA API",
    version="1.0.0",
    description="ALMA Health Intelligence System — DOM 07 · SUELO · B2C & Platform"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
