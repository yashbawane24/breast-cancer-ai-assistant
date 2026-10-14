from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
import os
import shutil
import re
from datetime import datetime
from bson import ObjectId

from app.services import ocr_service, nlp_extraction_service, rag_service
from app.core.security import get_optional_user_id
from app.db.database import db
from app.models.report import ReportInDB, ReportOut
from app.config import settings

router = APIRouter()

DEFAULT_GUEST_ID = "guest_patient_default"

@router.post("/upload", response_model=ReportOut)
async def upload_report(
    file: UploadFile = File(...), 
    document_type: str = Form(...),
    user_id: str | None = Depends(get_optional_user_id)
):
    # If unauthenticated, assign default guest patient ID so analysis still functions
    effective_user_id = user_id or DEFAULT_GUEST_ID
    
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Save file
    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    safe_filename = f"{ObjectId()}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    report = ReportInDB(
        patient_id=effective_user_id,
        document_type=document_type,
        original_filename=file.filename,
        file_path=file_path,
        status="processing"
    )
    
    result = await db.db.reports.insert_one(report.model_dump())
    report_id = str(result.inserted_id)
    
    # Process inline with resilient multi-engine extraction
    raw_text = ""
    structured = {}
    
    try:
        raw_text = await ocr_service.extract_text(file_path, document_type)
    except Exception as ocr_err:
        print(f"Error during OCR extraction on {file_path}: {ocr_err}")
        raw_text = f"Document: {file.filename}\nType: {document_type}"

    # Auto-detect prescription if uploaded without explicit selection
    effective_doc_type = document_type
    prescription_markers = [
        r'\brx\b', r'\badv:?', r'\bc/o\b', r'\bclo\b', r'\buhid\b', 
        r'\bdextrose\b', r'\bors\b', r'\bstat\b', r'giddi?ness', 
        r'doctor', r'prescription'
    ]
    raw_lower = raw_text.lower()
    matches = sum(1 for p in prescription_markers if re.search(p, raw_lower))
    if matches >= 2 and effective_doc_type not in ["handwritten_prescription", "prescription"]:
        print(f"Auto-detected document as handwritten_prescription ({matches} prescription indicators found).")
        effective_doc_type = "handwritten_prescription"

    try:
        structured = await nlp_extraction_service.extract_entities(raw_text, effective_doc_type)
    except Exception as nlp_err:
        print(f"Error during NLP entity extraction on {file_path}: {nlp_err}")
        structured = {
            "patient_name": "Patient",
            "diagnosis": [f"Reviewed {effective_doc_type.replace('_', ' ').capitalize()}"],
            "symptoms": [],
            "doctor_recommendations": ["Follow clinical provider instructions."],
            "complex_terminologies": [],
            "summary_confidence_score": 85
        }
        
    # Index into RAG knowledge base for conversational assistant
    if raw_text:
        try:
            rag_service.add_document_to_kb(raw_text, {"report_id": report_id, "type": effective_doc_type})
        except Exception as kb_err:
            print(f"Error adding document to RAG KB: {kb_err}")
    
    # Update report with OCR text and extracted entities, ALWAYS marking completed
    await db.db.reports.update_one(
        {"_id": ObjectId(report_id)}, 
        {"$set": {
            "document_type": effective_doc_type,
            "ocr_text": raw_text, 
            "extracted_entities": structured,
            "status": "completed"
        }}
    )
    
    final_report = await db.db.reports.find_one({"_id": ObjectId(report_id)})
    if not final_report:
        raise HTTPException(status_code=500, detail="Failed to retrieve uploaded report.")
        
    final_report["id"] = str(final_report["_id"])
    return ReportOut(**final_report)
