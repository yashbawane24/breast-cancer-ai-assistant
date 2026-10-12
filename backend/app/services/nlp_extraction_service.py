"""
Structured medical entity extraction from raw OCR text using LangChain and Groq.
Includes handwritten prescription reading and MTS Triage indicators.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from groq import Groq
from app.config import settings
from app.services.llm_service import client
import json

class Medicine(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    sig: Optional[str] = Field(default=None, description="Patient directions / instructions (e.g. Take 1 tablet by mouth twice daily after meals)")
    refills: Optional[str] = Field(default=None, description="Number of authorized refills")
    confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) of this extraction")

class LabParameter(BaseModel):
    name: str
    value: Optional[str] = None
    units: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: Optional[bool] = None
    confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) of this extraction")

class TermExplanation(BaseModel):
    term: str
    explanation: str
    confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) of this explanation")

class ExtractedEntities(BaseModel):
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    report_date: Optional[str] = None
    hospital: Optional[str] = None
    doctor_name: Optional[str] = None
    prescribing_doctor: Optional[str] = None
    is_handwritten_prescription: Optional[bool] = Field(default=False, description="True if document is a handwritten physician prescription")
    handwritten_confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) in reading handwritten text")
    diagnosis: Optional[List[str]] = []
    symptoms: Optional[List[str]] = []
    medicines: Optional[List[Medicine]] = []
    lab_parameters: Optional[List[LabParameter]] = []
    doctor_recommendations: Optional[List[str]] = []
    complex_terminologies: Optional[List[TermExplanation]] = []
    summary_confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) of the diagnosis and symptoms summary extraction")

EXTRACTION_SYSTEM_PROMPT = """You are an expert clinical data and medical document extractor.
Your task is to extract ALL patient demographics, diagnostic findings, medications, laboratory parameters, doctor recommendations, and complex terminology explanations from the medical document text into valid JSON.

JSON Schema format:
{
  "patient_name": string or null,
  "patient_age": integer or null,
  "patient_gender": string or null,
  "report_date": string or null,
  "hospital": string or null,
  "doctor_name": string or null,
  "prescribing_doctor": string or null,
  "is_handwritten_prescription": boolean,
  "handwritten_confidence_score": integer (0-100) or null,
  "diagnosis": [string, ...],
  "symptoms": [string, ...],
  "medicines": [
    {
      "name": string,
      "dosage": string or null,
      "frequency": string or null,
      "duration": string or null,
      "sig": string or null,
      "refills": string or null,
      "confidence_score": integer (0-100)
    }
  ],
  "lab_parameters": [
    {
      "name": string,
      "value": string or null,
      "units": string or null,
      "reference_range": string or null,
      "is_abnormal": boolean,
      "confidence_score": integer (0-100)
    }
  ],
  "doctor_recommendations": [string, ...],
  "complex_terminologies": [
    {
      "term": string,
      "explanation": string (plain English, patient-friendly explanation),
      "confidence_score": integer (0-100)
    }
  ],
  "summary_confidence_score": integer (0-100)
}

RULES:
1. Always populate 'diagnosis', 'symptoms', 'doctor_recommendations', and 'complex_terminologies' with relevant items found in the document.
2. For any biopsy, mammogram, ultrasound, or pathology report: identify the findings/impression (e.g. "BI-RADS Category: 4B", "Invasive Ductal Carcinoma") in the diagnosis list.
3. For blood tests or lab panels: extract all biomarkers/lab tests into 'lab_parameters' with their measured values, reference ranges, and whether abnormal.
4. For prescriptions: extract all medications, doses, frequencies, durations, and sig directions into 'medicines'.
5. For complex medical terms (e.g. BI-RADS, ER-positive, HER2, carcinoma, spiculated mass, etc.): provide a clear, empathetic, plain-language patient explanation in 'complex_terminologies'.
6. Return only valid JSON adhering strictly to the above schema.
"""

def extract_entities_heuristic(raw_text: str, document_type: str) -> dict:
    import re
    entities = ExtractedEntities().model_dump()
    
    # Demographics
    name_m = re.search(r'(?:patient(?:\s*name)?|name)[\s:]+([A-Za-z\s]{3,30})(?:[\n,]|\.|\s{2,}|age)', raw_text, re.I)
    if name_m:
        entities["patient_name"] = name_m.group(1).strip()
        
    age_m = re.search(r'(?:age|years?[\s-]?old)[\s:]+(\d{1,3})', raw_text, re.I) or re.search(r'(\d{1,3})\s*(?:yo|y/o|years? old)', raw_text, re.I)
    if age_m:
        try:
            entities["patient_age"] = int(age_m.group(1))
        except Exception:
            pass
            
    gender_m = re.search(r'\b(Female|Male)\b', raw_text, re.I)
    if gender_m:
        entities["patient_gender"] = gender_m.group(1).capitalize()
        
    hosp_m = re.search(r'(?:hospital|clinic|center|centre|laboratory|lab)[\s:]+([^\n,]{3,40})', raw_text, re.I)
    if hosp_m:
        entities["hospital"] = hosp_m.group(1).strip()
        
    dr_m = re.search(r'(?:dr\.?|doctor|physician)[\s:]+([A-Za-z\s]{3,30})(?:[\n,]|;|$)', raw_text, re.I)
    if dr_m:
        entities["doctor_name"] = dr_m.group(1).strip()

    # Diagnosis & Findings
    findings = []
    for line in raw_text.splitlines():
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 4:
            continue
        if any(keyword in line_clean.lower() for keyword in ["diagnosis", "impression", "findings", "bi-rads", "birads", "carcinoma", "fibroadenoma", "benign", "malignant", "normal", "healthy", "calcification", "mass", "cyst", "tumor"]):
            findings.append(line_clean)
    if findings:
        entities["diagnosis"] = findings[:5]
    else:
        entities["diagnosis"] = [f"Reviewed {document_type.replace('_', ' ').capitalize()} Document"]

    # Lab parameters
    lab_params = []
    # Common biomarkers: CA 15-3, Hemoglobin, ER, PR, HER2, Ki-67, etc.
    biomarkers = [
        (r'ca\s*15[-.]?3[\s:]+([\d.]+)\s*([a-zA-Z/]+)?', "CA 15-3", "< 30 U/mL"),
        (r'hemoglobin[\s:]+([\d.]+)\s*([a-zA-Z/]+)?', "Hemoglobin", "12.0 - 15.5 g/dL"),
        (r'er\b[\s:]+([\d.]+%?|\w+)', "Estrogen Receptor (ER)", "Positive / Negative"),
        (r'pr\b[\s:]+([\d.]+%?|\w+)', "Progesterone Receptor (PR)", "Positive / Negative"),
        (r'her2[\s:]+([\w\+\-]+)', "HER2", "Negative (0-1+)"),
        (r'ki[- ]?67[\s:]+([\d.]+%)', "Ki-67", "< 20% (Low)"),
    ]
    for pattern, name, ref in biomarkers:
        m = re.search(pattern, raw_text, re.I)
        if m:
            val = m.group(1)
            unit = m.group(2) if len(m.groups()) > 1 and m.group(2) else ""
            lab_params.append({
                "name": name,
                "value": str(val),
                "units": unit,
                "reference_range": ref,
                "is_abnormal": False,
                "confidence_score": 90
            })
    entities["lab_parameters"] = lab_params

    # Complex terminologies with explanations
    terms = []
    glossary = [
        ("bi-rads", "BI-RADS", "Breast Imaging Reporting and Data System — standardized numerical classification for mammography and breast imaging findings."),
        ("er", "Estrogen Receptor (ER)", "A test checking if breast cancer cells have estrogen hormone receptors, indicating potential response to hormone therapy."),
        ("pr", "Progesterone Receptor (PR)", "Measures progesterone sensitivity on cells, guiding endocrine/hormone-directed treatment strategies."),
        ("her2", "HER2", "Human Epidermal Growth Factor Receptor 2 protein test determining if targeted HER2 therapies are beneficial."),
        ("ki-67", "Ki-67", "A cellular proliferation marker measuring the percentage of rapidly dividing cancer cells."),
        ("carcinoma", "Carcinoma", "Cancer starting in the epithelial cells of tissues or ducts in the breast."),
        ("fibroadenoma", "Fibroadenoma", "A common, non-cancerous benign breast lump consisting of fibrous and glandular tissue."),
        ("calcification", "Calcification", "Tiny calcium deposits inside breast tissue, usually benign but monitored on surveillance imaging.")
    ]
    for key, term_name, expl in glossary:
        if re.search(r'\b' + re.escape(key) + r'\b', raw_text, re.I):
            terms.append({
                "term": term_name,
                "explanation": expl,
                "confidence_score": 95
            })
    entities["complex_terminologies"] = terms
    entities["doctor_recommendations"] = ["Discuss clinical findings with your treating healthcare provider."]
    entities["summary_confidence_score"] = 90
    return entities

async def extract_entities(raw_text: str, document_type: str) -> dict:
    if not raw_text or len(raw_text.strip()) == 0:
        return ExtractedEntities().model_dump()
        
    user_prompt = f"Document Type: {document_type}\n\nDocument Text:\n{raw_text}"
    
    # Models to try in order of preference
    models_to_try = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    
    raw_response_text = None
    if settings.groq_api_key:
        for model in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                raw_response_text = response.choices[0].message.content
                if raw_response_text:
                    break
            except Exception as e:
                print(f"Model {model} extraction failed: {e}")
                continue
            
    if not raw_response_text:
        # Fall back to heuristic rule-based extraction from the actual raw text
        return extract_entities_heuristic(raw_text, document_type)
        
    try:
        data = json.loads(raw_response_text)
        # Validate and normalize with Pydantic
        validated = ExtractedEntities(**data)
        return validated.model_dump()
    except Exception as e:
        print(f"Pydantic validation error on extracted JSON: {e}")
        # Try raw json dict with default structure
        if isinstance(data, dict):
            return data
        return extract_entities_heuristic(raw_text, document_type)

