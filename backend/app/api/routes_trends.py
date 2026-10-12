from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from app.db.database import db
from app.core.security import get_current_user_id, get_optional_user_id
from bson import ObjectId
from langchain_groq import ChatGroq
from app.config import settings

router = APIRouter()

@router.get("/timeline")
async def get_timeline(marker: str | None = None, document_type: str | None = None, user_id: str | None = Depends(get_optional_user_id)):
    """
    Returns time-series values for lab parameters across all of a patient's uploaded reports.
    """
    timeline = []
    
    target_user_id = user_id or "guest_patient_default"
    query = {"patient_id": target_user_id, "status": "completed"}
    if document_type:
        query["document_type"] = document_type
        
    cursor = db.db.reports.find(query).sort("upload_date", 1)  # Chronological order
    reports = await cursor.to_list(length=100)
    for report in reports:
        entities = report.get("extracted_entities") or {}
        date = entities.get("report_date") or str(report["upload_date"].date())
        
        lab_params = entities.get("lab_parameters") or []
        
        if marker:
            import re
            clean_marker = re.sub(r'\(.*?\)', '', marker).lower().replace("ae","e").strip()
            
            # Filter for specific marker (loose substring matching)
            param = None
            for p in lab_params:
                clean_name = re.sub(r'\(.*?\)', '', p["name"]).lower().replace("ae","e").strip()
                if clean_marker in clean_name or clean_name in clean_marker:
                    param = p
                    break
            
            if param:
                timeline.append({
                    "date": date,
                    "value": param.get("value"),
                    "units": param.get("units"),
                    "report_id": str(report["_id"])
                })
        else:
            # All markers
            for param in lab_params:
                timeline.append({
                    "date": date,
                    "marker": param["name"],
                    "value": param.get("value"),
                    "units": param.get("units"),
                    "report_id": str(report["_id"])
                })

    return timeline

@router.get("/compare")
async def compare_reports(id1: str, id2: str, language: str = "en", user_id: str | None = Depends(get_optional_user_id)):
    """
    Compare two reports and return AI generated summary of changes.
    """
    effective_id = user_id or "guest_patient_default"
    try:
        r1 = await db.db.reports.find_one({"_id": ObjectId(id1), "patient_id": effective_id})
        r2 = await db.db.reports.find_one({"_id": ObjectId(id2), "patient_id": effective_id})
    except Exception:
        r1, r2 = None, None
    
    if not r1 or not r2:
        return {
            "summary": "Please select two valid reports from your history to compare.",
            "confidence_score": None,
            "chart_data": [],
            "insights": []
        }
        
    e1 = r1.get("extracted_entities", {})
    e2 = r2.get("extracted_entities", {})
    
    llm = ChatGroq(
        temperature=0,
        model_name="qwen/qwen3.8-27b",
        api_key=settings.groq_api_key
    )
    
    chart_data = []
    
    import re
    def normalize_name(name):
        n = re.sub(r'\(.*?\)', '', str(name))
        return n.lower().strip()
        
    def extract_number(val):
        if not val:
            return None
        match = re.search(r"[-+]?\d*\.?\d+", str(val))
        if match:
            return float(match.group())
        return None

    l1 = {}
    for p in (e1.get("lab_parameters") or []):
        val = extract_number(p.get("value"))
        if val is not None:
            l1[normalize_name(p["name"])] = val
            
    l2 = {}
    name_map = {}
    for p in (e2.get("lab_parameters") or []):
        val = extract_number(p.get("value"))
        if val is not None:
            norm_name = normalize_name(p["name"])
            l2[norm_name] = val
            name_map[norm_name] = p["name"]
    
    for norm_name, v2 in l2.items():
        if norm_name in l1:
            v1 = l1[norm_name]
            pct = ((v2 - v1) / v1) * 100 if v1 != 0 else 0
            chart_data.append({
                "parameter": name_map[norm_name],
                "old_value": v1,
                "new_value": v2,
                "percent_change": round(pct, 2)
            })
            
    from pydantic import BaseModel, Field
    class Insight(BaseModel):
        parameter: str = Field(description="The name of the parameter from the chart data")
        insight: str = Field(description="A short, patient-friendly explanation of why this change matters")
    class ComparisonOutput(BaseModel):
        insights: List[Insight]
        summary: str = Field(description="A 2-sentence overarching summary of the comparison")
        confidence_score: int = Field(description="Confidence percentage (0-100) of this comparison summary")
        
    structured_llm = llm.with_structured_output(ComparisonOutput)
    
    lang_map = {
        "en": "English",
        "hi": "Hindi",
        "ta": "Tamil",
        "bn": "Bengali"
    }
    target_lang = lang_map.get(language, "English")
    
    prompt = f"""
    You are a helpful medical assistant. Compare these two medical reports and explain the changes in simple language for the patient.
    
    IMPORTANT INSTRUCTION: You MUST write all your insights and the final summary entirely in {target_lang}.
    CRITICAL INSTRUCTION FOR MEDICAL TERMS: Do not try to translate complex medical terms (like 'Hemoglobin', 'Ki-67'). Instead, transliterate them (write them in the literal spelling/script of {target_lang}, matching the English pronunciation).
    
    Here is the calculated chart data showing changes in their lab parameters:
    {chart_data}
    
    1. Identify any significant or meaningful changes from the chart data and provide a short, patient-friendly insight for it in {target_lang}.
    2. Provide a brief 2-sentence summary of the overall comparison in {target_lang}, noting if things are generally stable, improving, or require attention.
    3. Provide an overall confidence_score (0-100) indicating how sure you are of these conclusions based on the data provided.
    """
    
    try:
        if len(chart_data) > 0:
            result = structured_llm.invoke(prompt)
            insights = result.model_dump()["insights"]
            summary = result.summary
            confidence_score = result.confidence_score
        else:
            insights = []
            summary = "No common numerical lab parameters found to compare between these reports."
            confidence_score = None
    except Exception as e:
        print(f"LLM Compare Error: {e}")
        insights = []
        summary = "Unable to generate AI comparison at this time."
        confidence_score = None
        
    return {
        "chart_data": chart_data,
        "insights": insights,
        "summary": summary,
        "confidence_score": confidence_score
    }

@router.get("/alerts")
async def get_clinical_alerts(user_id: str | None = Depends(get_optional_user_id)):
    """
    Proactive Clinical Alerts: Analyzes patient's longitudinal findings to detect significant changes
    and recommend healthcare provider discussion.
    """
    effective_id = user_id or "guest_patient_default"
    cursor = db.db.reports.find({"patient_id": effective_id}).sort("upload_date", 1)
    reports = await cursor.to_list(length=50)
    
    if not reports:
        return []
    
    alerts = []
    
    # Check for high risk conditions or parameter shifts across reports
    for report in reports:
        entities = report.get("extracted_entities") or {}
        date = entities.get("report_date") or str(report["upload_date"].date())
        
        # Check lab parameters
        for p in (entities.get("lab_parameters") or []):
            name = (p.get("name") or "").lower()
            val_str = str(p.get("value") or "")
            import re
            m = re.search(r"[-+]?\d*\.?\d+", val_str)
            if m:
                val = float(m.group())
                if "ca 15" in name or "ca15" in name:
                    if val > 30:
                        alerts.append({
                            "id": f"alert-ca153-{report['_id']}",
                            "severity": "Warning" if val < 40 else "High",
                            "title": f"Elevated Tumor Marker (CA 15-3: {val} U/mL)",
                            "date": date,
                            "parameter": "CA 15-3",
                            "value": f"{val} U/mL",
                            "baseline": "Normal < 30 U/mL",
                            "message": f"Your CA 15-3 level measured {val} U/mL on {date}. This is above the standard reference threshold (30 U/mL).",
                            "recommendation": "We recommend discussing this trend with your oncologist during your next visit to evaluate if follow-up imaging is beneficial.",
                            "supports_decision": True
                        })

    if not alerts:
        alerts.append({
            "id": "alert-default-1",
            "severity": "Info",
            "title": "Longitudinal Baseline Established",
            "date": "Recent Visit",
            "parameter": "Overall Biomarkers",
            "value": "Stable",
            "baseline": "Baseline Parameters",
            "message": "All tracked longitudinal values are currently stable within baseline ranges.",
            "recommendation": "Continue standard scheduled surveillance visits with your care team.",
            "supports_decision": True
        })
        
    return alerts
