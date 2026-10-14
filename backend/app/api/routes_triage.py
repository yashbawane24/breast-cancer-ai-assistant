"""
Manchester Triage System (MTS) Assessment API route.
Evaluates clinical findings, symptoms, and report parameters into 5 MTS urgency levels.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class TriageRequest(BaseModel):
    report_id: Optional[str] = None
    symptoms: Optional[List[str]] = []
    findings: Optional[dict] = {}

class MTSTriageResponse(BaseModel):
    triage_color: str
    triage_level_name: str
    urgency_score: int  # 1 (Highest) to 5 (Lowest)
    target_time_minutes: int
    clinical_indicators: List[str]
    action_recommendation: str
    provider_guidance: str

@router.post("/assess", response_model=MTSTriageResponse)
async def assess_triage(payload: TriageRequest):
    symptoms = [s.lower() for s in (payload.symptoms or [])]
    findings = payload.findings or {}
    
    # Look for BI-RADS in findings root, diagnosis list, or complex terminologies
    bi_rads = str(findings.get("bi_rads") or "")
    if not bi_rads:
        for diag in (findings.get("diagnosis") or []):
            if "bi-rads" in str(diag).lower() or "birads" in str(diag).lower():
                bi_rads = str(diag)
                break
        if not bi_rads:
            for term in (findings.get("complex_terminologies") or []):
                t_name = str(term.get("term", "") if isinstance(term, dict) else getattr(term, "term", "")).lower()
                if "bi-rads" in t_name or "birads" in t_name:
                    bi_rads = t_name
                    break

    # Look for CA 15-3 in findings root or inside lab_parameters
    ca153 = findings.get("ca15_3")
    if not ca153:
        for lab in (findings.get("lab_parameters") or []):
            name = (lab.get("name") if isinstance(lab, dict) else getattr(lab, "name", "") or "").lower()
            if "ca 15-3" in name or "ca15-3" in name or "ca 15.3" in name or "ca15.3" in name:
                try:
                    val_str = str(lab.get("value") if isinstance(lab, dict) else getattr(lab, "value", "") or "")
                    import re
                    match = re.search(r'[-+]?\d*\.?\d+', val_str)
                    if match:
                        ca153 = float(match.group())
                        break
                except Exception:
                    pass

    fever = any("fever" in s or "chills" in s for s in symptoms)
    chemo = any("chemo" in s for s in symptoms)
    acute_pain = any("severe pain" in s or "chest pain" in s or "shortness of breath" in s for s in symptoms)

    # Look for RBS / Hypoglycemia in findings or lab_parameters
    rbs_val = None
    for lab in (findings.get("lab_parameters") or []):
        name = (lab.get("name") if isinstance(lab, dict) else getattr(lab, "name", "") or "").lower()
        if "rbs" in name or "glucose" in name or "blood sugar" in name:
            try:
                val_str = str(lab.get("value") if isinstance(lab, dict) else getattr(lab, "value", "") or "")
                import re
                match = re.search(r'[-+]?\d*\.?\d+', val_str)
                if match:
                    rbs_val = float(match.group())
                    break
            except Exception:
                pass
    has_hypo = any("hypoglycem" in str(d).lower() for d in (findings.get("diagnosis") or [])) or (rbs_val is not None and rbs_val < 70)

    # Red / Immediate Triage (Score 1)
    if any("shortness of breath" in s or "chest pain" in s or "unconscious" in s for s in symptoms) or (rbs_val is not None and rbs_val < 40):
        return MTSTriageResponse(
            triage_color="Red",
            triage_level_name="Immediate (Red - Category 1)",
            urgency_score=1,
            target_time_minutes=0,
            clinical_indicators=["Acute Cardiorespiratory Distress / Severe Metabolic Crisis", "Critical Emergency Indicator"],
            action_recommendation="Seek immediate emergency medical evaluation (Call Emergency Services / Visit nearest Emergency Department).",
            provider_guidance="Requires immediate resuscitation assessment and rapid IV dextrose by emergency physician."
        )
        
    # Orange / Very Urgent Triage (Score 2)
    if (fever and chemo) or acute_pain or "4c" in bi_rads.lower() or "5" in bi_rads or (has_hypo and rbs_val is not None and rbs_val <= 60):
        indicators = [c for c in [
            "Febrile Neutropenia Risk (Fever during Active Chemotherapy)" if (fever and chemo) else None,
            f"High-Risk Finding (BI-RADS {bi_rads})" if ("4" in bi_rads or "5" in bi_rads) else None,
            "Acute Inflammatory Symptom" if acute_pain else None,
            f"Acute Hypoglycemia Crisis (RBS {int(rbs_val)} mg/dL)" if (has_hypo and rbs_val is not None and rbs_val <= 60) else None
        ] if c]
        if not indicators:
            indicators = ["High Clinical Priority Parameter"]
            
        return MTSTriageResponse(
            triage_color="Orange",
            triage_level_name="Very Urgent (Orange - Category 2)",
            urgency_score=2,
            target_time_minutes=15,
            clinical_indicators=indicators,
            action_recommendation="Immediate STAT IV Dextrose administration and clinical evaluation within 15-30 minutes." if has_hypo else "Contact your oncology clinical care team or visit Urgent Oncology Care within 1-2 hours.",
            provider_guidance="Administer STAT IV Dextrose (5% or 10%) and re-check blood glucose every 15 minutes." if has_hypo else "Perform STAT CBC with differential to rule out neutropenic sepsis. Evaluate suspicious mass."
        )
        
    # Yellow / Urgent Triage (Score 3)
    if "4a" in bi_rads.lower() or "4b" in bi_rads.lower() or (ca153 and float(ca153) > 35) or any("lump" in s or "bleeding" in s for s in symptoms):
        indicators = [c for c in [
            f"Elevated CA 15-3 ({ca153} U/mL)" if (ca153 and float(ca153) > 35) else None,
            "Palpable Breast Nodule" if any("lump" in s for s in symptoms) else None,
            f"BI-RADS {bi_rads}" if bi_rads else None
        ] if c]
        if not indicators:
            indicators = ["Urgent Medical Finding"]
            
        return MTSTriageResponse(
            triage_color="Yellow",
            triage_level_name="Urgent (Yellow - Category 3)",
            urgency_score=3,
            target_time_minutes=60,
            clinical_indicators=indicators,
            action_recommendation="Schedule a consultation with your treating oncologist/breast specialist within 24-48 hours.",
            provider_guidance="Recommend targeted ultrasound / core needle biopsy verification and repeat biomarker panel."
        )
        
    # Green / Standard Triage (Score 4)
    return MTSTriageResponse(
        triage_color="Green",
        triage_level_name="Standard (Green - Category 4)",
        urgency_score=4,
        target_time_minutes=120,
        clinical_indicators=["Stable Longitudinal Parameters", "BI-RADS 1-3 Routine Follow-up"],
        action_recommendation="Continue routine scheduled follow-up visits and standard surveillance imaging.",
        provider_guidance="Reassess at next annual/semiannual routine follow-up appointment."
    )
