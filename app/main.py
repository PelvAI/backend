from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base # Register all models
from app.api.v1.api import api_router

app = FastAPI(
    title="PelvIA API",
    version="1.0.0",
    description="Backend API for PelvIA - Pelvic Health Platform"
)

# Debug Middleware to print headers
from starlette.requests import Request

@app.middleware("http")
async def log_headers(request: Request, call_next):
    print(f"DEBUG: Request Headers for {request.method} {request.url}:")
    for name, value in request.headers.items():
        print(f"  {name}: {value}")
    response = await call_next(request)
    return response

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins
    allow_credentials=False, # We don't need cookies for now
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
