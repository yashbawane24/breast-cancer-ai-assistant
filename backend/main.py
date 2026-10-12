"""
Entry point for the Breast Health Copilot API.
Run locally with: uvicorn main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api import routes_auth, routes_upload, routes_reports, routes_trends, routes_chat, routes_translate, routes_sandbox, routes_triage

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Multimodal AI Healthcare Assistant API",
    description="OCR + NLP + LLM pipeline for medical report analysis & clinical decision support",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes_upload.router, prefix="/api/reports", tags=["upload"])
app.include_router(routes_reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(routes_trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(routes_chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(routes_translate.router, prefix="/api/translate", tags=["translate"])
app.include_router(routes_sandbox.router, prefix="/api/sandbox", tags=["sandbox"])
app.include_router(routes_triage.router, prefix="/api/triage", tags=["triage"])

@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok", "service": "breast-cancer-ai-assistant"}

@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check():
    db_status = "ok"
    db_error = None
    try:
        if db.client is not None:
            await db.client.admin.command('ping')
        else:
            db_status = "disconnected"
    except Exception as e:
        db_status = "error"
        db_error = str(e)
    return {
        "status": "ok",
        "database": db_status,
        "database_error": db_error
    }
