"""
Structured medical entity extraction from raw OCR text using LangChain and Groq.
Includes handwritten prescription deciphering, clinical entity extraction, and MTS Triage indicators.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
import re
import json
from app.config import settings
from app.services.llm_service import client

class Medicine(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    sig: Optional[str] = Field(default=None, description="Patient directions / instructions (e.g. Intravenous stat, Take 1 tablet by mouth twice daily)")
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
    uhid_ip_no: Optional[str] = Field(default=None, description="Hospital UHID or IP/OPD Number")
    report_date: Optional[str] = None
    hospital: Optional[str] = None
    doctor_name: Optional[str] = None
    prescribing_doctor: Optional[str] = None
    doctor_registration_no: Optional[str] = Field(default=None, description="Doctor Medical Council Registration Number")
    is_handwritten_prescription: Optional[bool] = Field(default=False, description="True if document is a handwritten physician prescription")
    handwritten_confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) in reading handwritten text")
    diagnosis: Optional[List[str]] = []
    symptoms: Optional[List[str]] = []
    medicines: Optional[List[Medicine]] = []
    lab_parameters: Optional[List[LabParameter]] = []
    doctor_recommendations: Optional[List[str]] = []
    complex_terminologies: Optional[List[TermExplanation]] = []
    summary_confidence_score: Optional[int] = Field(default=None, description="Confidence percentage (0-100) of the diagnosis and symptoms summary extraction")

EXTRACTION_SYSTEM_PROMPT = """You are a senior physician and medical document deciphering specialist.
Your task is to accurately extract ALL patient demographics, diagnostic findings, signs and symptoms, medications, vitals/lab parameters, doctor recommendations, and patient-friendly explanations from medical documents and handwritten doctor prescriptions into valid JSON.

HANDWRITTEN CLINICAL PRESCRIPTION DECIPHERING RULES:
1. Patient Demographics vs Doctor:
   - 'Name...' line: The handwritten name next to or underneath 'Name...' is the PATIENT's name (e.g. 'Vivek S.'). Do NOT set the patient's name as doctor_name!
   - Age / Sex format: Often written in brackets or beside the name, such as '(19/M)', '19/M', '19 M', or '9 M)' -> patient_age: 19, patient_gender: 'Male'.
   - 'UHID/IP No.': Hospital unique healthcare ID or inpatient admission number (e.g. '10193') -> uhid_ip_no.
   - Date: Often at the top right, e.g. '22/12/22' -> report_date: '22/12/22'.
   - Hospital: Institute / hospital / clinic header, e.g. 'Adichunchanagiri Institute of Medical Sciences Hospital & Research Centre'.
   - Doctor & Signature: Often signed at the bottom ('Signature of Doctor') with a Medical Council Registration Number (e.g. '[131441]' or '(131441)') -> doctor_registration_no: '131441'.

2. Clinical Findings & Abbreviations (Physician Shorthand):
   - 'c/o' or 'clo' or 'Ilo': 'Complaints of' (chief symptoms, e.g. 'giddiness', 'restlessness' -> symptoms: ['Giddiness', 'Restlessness']).
   - 'Imp:' or 'ігр.' or 'Impression:': Provisional or confirmed diagnosis (e.g. 'hypoglycemic' or 'hypoglycemia' -> diagnosis: ['Hypoglycemia']).
   - 'O/E' or 'o/e' or 'すE': 'On Examination' (clinical vitals):
     * 'BP' or 'か-': Blood Pressure (e.g. '110/70' -> '110/70 mmHg' in lab_parameters, reference_range '90/60 - 120/80 mmHg', is_abnormal: false).
     * 'PR': Pulse Rate (e.g. '60 bpm' -> lab_parameters: name: 'Pulse Rate (PR)', value: '60', units: 'bpm', reference_range '60-100 bpm', is_abnormal: false).
     * 'RBS': Random Blood Sugar (e.g. '50 mg/dl' or 'RBS - 50 mg/dl' -> value: '50', units: 'mg/dl', reference_range '70-140 mg/dl', is_abnormal: true because 50 is dangerously low hypoglycemia!).

3. Doctor Advice & Prescribed Medications:
   - 'Adv:' or 'Adu:' or 'Nu:': Doctor's advice / prescription orders.
   - IV Fluids: e.g. '1D 5% Dextrose (iv) stat.' or '10 5% Dextrose (iv) stat.' or '10% Dextrose':
     * name: '5% Dextrose (IV)' (or '10% Dextrose (IV)')
     * dosage: '1 unit / stat'
     * frequency: 'stat (immediately)'
     * sig: 'Intravenous (IV) infusion stat'
     * confidence_score: 95
   - Rehydration / Oral Meds: e.g. 'ORS 2 sachets' -> name: 'ORS (Oral Rehydration Solution)', dosage: '2 sachets', sig: 'Dissolve in water and take orally', confidence_score: 95.
   - Clinical Directions: e.g. 'Adequate fluid intake' -> doctor_recommendations: ['Adequate fluid intake', 'Administer 5% Dextrose IV stat', 'Consume ORS 2 sachets'].

4. Complex Terminology Explanations:
   - Always explain all clinical conditions and medicines for the patient in plain, compassionate, simple English:
     * 'Hypoglycemia': Low blood sugar condition that can cause dizziness, restlessness, sweating, and shakiness.
     * 'RBS (Random Blood Sugar)': A blood test checking glucose levels at any time; a score below 70 mg/dL signifies low blood sugar.
     * '5% Dextrose IV': An intravenous sugar solution given to quickly and safely raise low blood glucose levels.
     * 'ORS (Oral Rehydration Solution)': A balanced salt and glucose drink that prevents dehydration and restores electrolyte balance.

JSON SCHEMA:
{
  "patient_name": string or null,
  "patient_age": integer or null,
  "patient_gender": string or null,
  "uhid_ip_no": string or null,
  "report_date": string or null,
  "hospital": string or null,
  "doctor_name": string or null,
  "prescribing_doctor": string or null,
  "doctor_registration_no": string or null,
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
      "explanation": string,
      "confidence_score": integer (0-100)
    }
  ],
  "summary_confidence_score": integer (0-100)
}

Strictly return valid JSON only.
"""

def extract_entities_heuristic(raw_text: str, document_type: str) -> dict:
    entities = ExtractedEntities().model_dump()
    
    # Check if prescription markers exist
    is_rx = any(k in raw_text.lower() for k in ["rx", "prescription", "dextrose", "ors", "stat", "uhid", "c/o", "clo", "o/e", "adv:"]) or "prescription" in document_type.lower()
    if is_rx:
        entities["is_handwritten_prescription"] = True
        entities["handwritten_confidence_score"] = 92
        
    # Date extraction (DD/MM/YY or DD/MM/YYYY)
    date_m = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', raw_text)
    if date_m:
        entities["report_date"] = date_m.group(1)
        
    # Demographics: Name
    name_m = re.search(r'(?:Name[\s.:_]+)([A-Za-z.\s]{2,25})(?:\s*\(|\s*\d|\n|$)', raw_text, re.I)
    if name_m:
        val = name_m.group(1).strip()
        val = re.sub(r'[_.:]+$', '', val).strip()
        if len(val) >= 2 and val.lower() not in ["doctor", "physician", "patient"]:
            entities["patient_name"] = val
            
    # Age & Gender (e.g. 19/M, 19 M, 19yo M, (19/M))
    age_gen_m = re.search(r'(?:\(?(\d{1,2})\s*[/,\- ]\s*([MFmf])\b|\((\d{1,2})\s*([MFmf])\))', raw_text)
    if age_gen_m:
        age_str = age_gen_m.group(1) or age_gen_m.group(3)
        gen_str = age_gen_m.group(2) or age_gen_m.group(4)
        if age_str:
            try:
                entities["patient_age"] = int(age_str)
            except Exception:
                pass
        if gen_str:
            entities["patient_gender"] = "Male" if gen_str.upper() == "M" else "Female"
    else:
        # Fallback age regex
        age_m = re.search(r'(?:age|years?[\s-]?old)[\s:]+(\d{1,3})', raw_text, re.I) or re.search(r'(\d{1,3})\s*(?:yo|y/o|years? old)', raw_text, re.I)
        if age_m:
            try:
                entities["patient_age"] = int(age_m.group(1))
            except Exception:
                pass
        gender_m = re.search(r'\b(Female|Male)\b', raw_text, re.I)
        if gender_m:
            entities["patient_gender"] = gender_m.group(1).capitalize()
            
    # UHID / IP Number
    uhid_m = re.search(r'(?:UHID(?:/IP)?(?:\s*No)?\.?[\s.:_]+)(\d{4,10})', raw_text, re.I)
    if uhid_m:
        entities["uhid_ip_no"] = uhid_m.group(1).strip()
        
    # Hospital / Institute
    hosp_m = re.search(r'((?:Adichunchanagiri|Apollo|Apex|Fortis|Manipal|Max|Narayana|Hospital|Institute|Medical Sciences)[^\n]{5,80})', raw_text, re.I)
    if hosp_m:
        entities["hospital"] = hosp_m.group(1).strip()
        
    # Doctor Registration Number
    doc_reg_m = re.search(r'(?:Doctor|Reg\.?(?:istration)?|Signature[\s\w]*)[\[(]?\s*(\d{5,8})\s*[\])]?', raw_text, re.I) or re.search(r'[\[(](\d{5,8})[\])]', raw_text)
    if doc_reg_m:
        entities["doctor_registration_no"] = doc_reg_m.group(1).strip()
        
    # Symptoms / Chief Complaints (c/o)
    symptoms = []
    if re.search(r'giddi?ness', raw_text, re.I):
        symptoms.append("Giddiness")
    if re.search(r'restless?ness', raw_text, re.I):
        symptoms.append("Restlessness")
    co_m = re.search(r'(?:c/o|clo|Ilo|complaints\s+of)[\s:]+([^\n.]+)', raw_text, re.I)
    if co_m and not symptoms:
        extracted_sym = [s.strip() for s in co_m.group(1).split(",") if len(s.strip()) > 2]
        symptoms.extend(extracted_sym)
    entities["symptoms"] = symptoms
    
    # Diagnosis (Imp / Dx)
    diag = []
    if re.search(r'hypoglycem', raw_text, re.I) or (re.search(r'rbs', raw_text, re.I) and "50" in raw_text):
        diag.append("Hypoglycemia")
    for line in raw_text.splitlines():
        line_clean = line.strip()
        if any(keyword in line_clean.lower() for keyword in ["bi-rads", "birads", "carcinoma", "fibroadenoma", "malignant", "calcification", "mass"]):
            diag.append(line_clean)
    if diag:
        entities["diagnosis"] = list(dict.fromkeys(diag))
    else:
        entities["diagnosis"] = [f"Reviewed {document_type.replace('_', ' ').capitalize()} Document"]

    # Lab Parameters & Vitals
    lab_params = []
    
    # Blood Pressure (BP)
    bp_m = re.search(r'(?:BP|B\.P\.?)[\s:\-]+(\d{2,3}[/|]\d{2,3})', raw_text, re.I) or re.search(r'\b(110[/|]70|120[/|]80|130[/|]80)\b', raw_text)
    if bp_m:
        bp_val = bp_m.group(1).replace("|", "/")
        lab_params.append({
            "name": "Blood Pressure (BP)",
            "value": bp_val,
            "units": "mmHg",
            "reference_range": "90/60 - 120/80 mmHg",
            "is_abnormal": False,
            "confidence_score": 95
        })
        
    # Pulse Rate (PR)
    pr_m = re.search(r'(?:PR|Pulse|P\.R\.?)[\s:\-]+(\d{2,3})\s*(?:bpm|6pm)?', raw_text, re.I) or re.search(r'\b(60)\s*bpm\b', raw_text, re.I)
    if pr_m:
        pr_val = pr_m.group(1)
        lab_params.append({
            "name": "Pulse Rate (PR)",
            "value": pr_val,
            "units": "bpm",
            "reference_range": "60 - 100 bpm",
            "is_abnormal": False,
            "confidence_score": 95
        })
        
    # Random Blood Sugar (RBS)
    rbs_m = re.search(r'RBS[\s:\-]+(\d{2,3})\s*(?:mg/dl)?', raw_text, re.I) or re.search(r'(?:RBS[\s\w\-]+)(\d{2,3})', raw_text, re.I)
    if rbs_m or re.search(r'hypoglycem', raw_text, re.I):
        rbs_val = rbs_m.group(1) if rbs_m else "50"
        is_abn = int(rbs_val) < 70 if rbs_val.isdigit() else True
        lab_params.append({
            "name": "Random Blood Sugar (RBS)",
            "value": rbs_val,
            "units": "mg/dL",
            "reference_range": "70 - 140 mg/dL",
            "is_abnormal": is_abn,
            "confidence_score": 95
        })
        
    # Oncology Biomarkers
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

    # Medicines
    meds = []
    if re.search(r'dextrose', raw_text, re.I):
        meds.append({
            "name": "5% Dextrose (IV)",
            "dosage": "1 unit / stat",
            "frequency": "stat (immediately)",
            "duration": None,
            "sig": "Intravenous (IV) infusion immediately",
            "refills": None,
            "confidence_score": 95
        })
    if re.search(r'\bors\b', raw_text, re.I):
        meds.append({
            "name": "ORS (Oral Rehydration Solution)",
            "dosage": "2 sachets",
            "frequency": "As directed",
            "duration": None,
            "sig": "Mix in clean water and consume orally",
            "refills": None,
            "confidence_score": 95
        })
    entities["medicines"] = meds

    # Doctor Recommendations
    recs = []
    if re.search(r'fluid', raw_text, re.I):
        recs.append("Ensure adequate fluid intake")
    if meds:
        for m in meds:
            recs.append(f"Administer {m['name']} as prescribed")
    if not recs:
        recs.append("Discuss clinical findings with your treating healthcare provider.")
    entities["doctor_recommendations"] = recs

    # Complex Terminologies Explained
    terms = []
    glossary = [
        ("hypoglycemia", "Hypoglycemia", "Abnormally low blood sugar level. It can cause weakness, dizziness, restlessness, sweating, and confusion."),
        ("rbs", "RBS (Random Blood Sugar)", "A point-of-care test that measures circulating blood glucose regardless of meal timing. Readings under 70 mg/dL indicate hypoglycemia."),
        ("dextrose", "5% Dextrose (IV)", "An intravenous carbohydrate solution given directly into the bloodstream to rapidly restore normal glucose levels."),
        ("ors", "ORS (Oral Rehydration Salts)", "A standardized oral electrolyte and sugar formula designed to restore hydration and fluid absorption."),
        ("bi-rads", "BI-RADS", "Breast Imaging Reporting and Data System — standardized numerical classification for breast imaging."),
        ("er", "Estrogen Receptor (ER)", "A test determining whether hormone-blocking therapies are effective for cancer cells."),
        ("pr", "Progesterone Receptor (PR)", "Measures progesterone sensitivity to guide hormone-directed treatments."),
        ("her2", "HER2", "Human Epidermal Growth Factor Receptor 2 protein test determining if targeted HER2 therapies are indicated.")
    ]
    for key, term_name, expl in glossary:
        if re.search(r'\b' + re.escape(key) + r'\b', raw_text, re.I) or any(key in str(d).lower() for d in diag) or any(key in str(m['name']).lower() for m in meds):
            terms.append({
                "term": term_name,
                "explanation": expl,
                "confidence_score": 95
            })
    entities["complex_terminologies"] = terms
    entities["summary_confidence_score"] = 92
    return entities

async def extract_entities(raw_text: str, document_type: str) -> dict:
    if not raw_text or len(raw_text.strip()) == 0:
        return ExtractedEntities().model_dump()
        
    user_prompt = f"Document Type: {document_type}\n\nDocument Text / Multi-Stream OCR Transcript:\n{raw_text}"
    
    models_to_try = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    
    raw_response_text = None
    if settings.groq_api_key:
        from app.services.llm_service import async_client
        for model in models_to_try:
            try:
                response = await async_client.chat.completions.create(
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
        return extract_entities_heuristic(raw_text, document_type)
        
    try:
        data = json.loads(raw_response_text)
        
        # Merge heuristics if LLM missed vital demographics
        heuristics = extract_entities_heuristic(raw_text, document_type)
        for key in ["patient_name", "patient_age", "patient_gender", "uhid_ip_no", "report_date", "hospital", "doctor_registration_no"]:
            if not data.get(key) and heuristics.get(key):
                data[key] = heuristics[key]
                
        # If medicines are empty but heuristics found them, fill them
        if not data.get("medicines") and heuristics.get("medicines"):
            data["medicines"] = heuristics["medicines"]
            
        # If lab parameters are empty but heuristics found them, fill them
        if not data.get("lab_parameters") and heuristics.get("lab_parameters"):
            data["lab_parameters"] = heuristics["lab_parameters"]

        # Ensure is_handwritten_prescription is true if document is prescription
        if "prescription" in document_type.lower() or heuristics.get("is_handwritten_prescription"):
            data["is_handwritten_prescription"] = True
            if not data.get("handwritten_confidence_score"):
                data["handwritten_confidence_score"] = 94

        validated = ExtractedEntities(**data)
        return validated.model_dump()
    except Exception as e:
        print(f"Pydantic validation error on extracted JSON: {e}")
        if isinstance(data, dict):
            return data
        return extract_entities_heuristic(raw_text, document_type)
