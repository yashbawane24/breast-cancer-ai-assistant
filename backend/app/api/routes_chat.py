from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services import rag_service
from app.core.security import get_optional_user_id
from app.db.database import db

router = APIRouter()

DEFAULT_GUEST_ID = "guest_patient_default"

class ChatRequest(BaseModel):
    message: str
    report_id: str | None = None
    language: str | None = "en"

@router.post("")
async def chat(payload: ChatRequest, user_id: str | None = Depends(get_optional_user_id)):
    """
    Retrieves relevant passages, performs emotion/sentiment detection, compiles longitudinal history,
    and generates an empathetic, context-aware answer via LLM.
    """
    effective_user_id = user_id or DEFAULT_GUEST_ID
    longitudinal_summary = ""
    try:
        cursor = db.db.reports.find({"patient_id": effective_user_id}).sort("upload_date", 1)
        reports = await cursor.to_list(length=10)
        if reports:
            summary_items = []
            for r in reports:
                date = str(r.get("upload_date", "")).split()[0]
                doc_type = r.get("document_type", "report")
                entities = r.get("extracted_entities", {})
                diag = ", ".join(entities.get("diagnosis", [])) or "Routine evaluation"
                summary_items.append(f"- Date: {date} | Type: {doc_type} | Findings: {diag}")
            longitudinal_summary = "\n".join(summary_items)
    except Exception as e:
        print(f"Error fetching longitudinal history: {e}")

    result = await rag_service.answer_question(
        message=payload.message,
        patient_id=effective_user_id,
        language=payload.language or "en",
        longitudinal_context=longitudinal_summary
    )
    
    return result

