from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import List
from bson import ObjectId
import os

from app.db.database import db
from app.core.security import get_optional_user_id
from app.models.report import ReportOut

router = APIRouter()

DEFAULT_GUEST_ID = "guest_patient_default"

@router.get("/", response_model=List[ReportOut])
async def list_reports(user_id: str | None = Depends(get_optional_user_id)):
    if user_id:
        query = {"patient_id": user_id}
    else:
        query = {"patient_id": DEFAULT_GUEST_ID}
        
    cursor = db.db.reports.find(query).sort("upload_date", -1)
    reports = await cursor.to_list(length=100)
    
    result = []
    for r in reports:
        r["id"] = str(r["_id"])
        result.append(ReportOut(**r))
    return result

@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: str, user_id: str | None = Depends(get_optional_user_id)):
    try:
        obj_id = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID format")
        
    if user_id:
        query = {"_id": obj_id, "patient_id": user_id}
    else:
        query = {"_id": obj_id, "patient_id": DEFAULT_GUEST_ID}
        
    report = await db.db.reports.find_one(query)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report["id"] = str(report["_id"])
    return ReportOut(**report)

@router.get("/{report_id}/view")
async def view_report_file(report_id: str, user_id: str | None = Depends(get_optional_user_id)):
    try:
        obj_id = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID format")
        
    if user_id:
        query = {"_id": obj_id, "patient_id": user_id}
    else:
        query = {"_id": obj_id, "patient_id": DEFAULT_GUEST_ID}

    report = await db.db.reports.find_one(query)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    file_path = report.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(file_path)

@router.delete("/{report_id}")
async def delete_report(report_id: str, user_id: str | None = Depends(get_optional_user_id)):
    try:
        obj_id = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID format")
        
    if user_id:
        query = {"_id": obj_id, "patient_id": user_id}
    else:
        query = {"_id": obj_id, "patient_id": DEFAULT_GUEST_ID}
        
    report = await db.db.reports.find_one(query)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Delete from DB
    await db.db.reports.delete_one({"_id": obj_id})
    
    # Delete file from disk
    file_path = report.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing file {file_path}: {e}")
            
    return {"status": "success", "message": "Report deleted"}
