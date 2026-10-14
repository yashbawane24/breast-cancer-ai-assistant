"""
OCR and handwriting recognition service.
Handles:
- Digital PDFs -> pdfplumber
- Scanned PDFs -> pdfplumber page image rendering + Apple Vision / Tesseract / OCR.space
- Handwritten prescriptions & clinical images -> Native Apple Vision OCR (macOS) + OCR.space Engine 2 + OpenCV CLAHE multi-pass Tesseract
"""
import os
import shutil
import requests
import cv2
import numpy as np
from PIL import Image
import pdfplumber
import pytesseract

# Explicitly configure tesseract binary path for macOS / Homebrew / Linux
_TESSERACT_CANDIDATES = [
    shutil.which("tesseract"),
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/usr/bin/tesseract"
]
for candidate in _TESSERACT_CANDIDATES:
    if candidate and os.path.exists(candidate):
        pytesseract.pytesseract.tesseract_cmd = candidate
        break

def extract_apple_vision(file_path: str) -> str:
    """
    Extract high-accuracy handwriting and printed text using macOS native Vision framework.
    Uses VNRecognizeTextRequest with accurate recognition level and language correction.
    Also inspects CLAHE-enhanced vertical bands to ensure low-contrast middle clinical notes are captured.
    """
    try:
        import Vision
        from Cocoa import NSURL
        
        url = NSURL.fileURLWithPath_(file_path)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(True)
        req.setRecognitionLanguages_(["en-US"])
        
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        success, _ = handler.performRequests_error_([req], None)
        
        lines = []
        if success and req.results():
            for o in req.results():
                cands = o.topCandidates_(1)
                if cands and len(cands) > 0:
                    lines.append(cands[0].string())
                    
        # Multi-band enhanced extraction for tall prescription slips
        img = cv2.imread(file_path)
        if img is not None and img.shape[0] > 400:
            h_img, w_img = img.shape[:2]
            bands = [
                ("mid", img[int(h_img * 0.25):int(h_img * 0.70), :]),
                ("lower", img[int(h_img * 0.50):h_img, :])
            ]
            for bname, band in bands:
                try:
                    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
                    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                    enhanced = clahe.apply(gray)
                    tmp_band = f"/tmp/_vband_{bname}_{os.getpid()}.png"
                    cv2.imwrite(tmp_band, enhanced)
                    
                    b_url = NSURL.fileURLWithPath_(tmp_band)
                    b_req = Vision.VNRecognizeTextRequest.alloc().init()
                    b_req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
                    b_req.setUsesLanguageCorrection_(True)
                    b_req.setRecognitionLanguages_(["en-US"])
                    b_handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(b_url, None)
                    b_success, _ = b_handler.performRequests_error_([b_req], None)
                    if b_success and b_req.results():
                        for o in b_req.results():
                            b_cands = o.topCandidates_(1)
                            if b_cands and len(b_cands) > 0:
                                val = b_cands[0].string()
                                if val not in lines:
                                    lines.append(val)
                    if os.path.exists(tmp_band):
                        os.remove(tmp_band)
                except Exception as band_err:
                    print(f"Error in Vision band {bname}: {band_err}")
                    
        return "\n".join(lines).strip()
    except Exception as e:
        print(f"Apple Vision extraction failed or unavailable: {e}")
        return ""

def extract_ocr_space(file_path: str, engine: str = "2") -> str:
    """
    Call OCR.space API with OCREngine 2 (specialized for handwriting recognition and mobile camera captures).
    """
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://api.ocr.space/parse/image",
                data={"apikey": "helloworld", "language": "eng", "OCREngine": engine},
                files={"file": f},
                timeout=15
            )
            result = response.json()
            if result.get("ParsedResults"):
                parsed = result["ParsedResults"][0].get("ParsedText", "")
                if parsed and parsed.strip():
                    return parsed.strip()
    except Exception as e:
        print(f"OCR.space API error with engine {engine}: {e}")
    return ""

def extract_tesseract_enhanced(file_path: str) -> str:
    """
    OpenCV preprocessing pipeline + Tesseract OCR:
    - 2x Bicubic upscaling
    - Grayscale conversion
    - CLAHE contrast enhancement
    - Multi-mode PSM passes (PSM 6: uniform block, PSM 3: fully automatic)
    """
    try:
        img = cv2.imread(file_path)
        if img is None:
            with Image.open(file_path) as pil_img:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                return pytesseract.image_to_string(pil_img, config="--psm 3").strip()
                
        h, w = img.shape[:2]
        up = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        cl = clahe.apply(gray)
        
        # Pass 1: CLAHE with PSM 6
        text_clahe_6 = pytesseract.image_to_string(cl, config="--oem 1 --psm 6").strip()
        
        # Pass 2: Adaptive thresholding
        adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
        text_adapt_3 = pytesseract.image_to_string(adapt, config="--oem 1 --psm 3").strip()
        
        # Pick the most informative or combine
        combined_tess = []
        if text_clahe_6:
            combined_tess.append(text_clahe_6)
        if text_adapt_3 and text_adapt_3 != text_clahe_6:
            combined_tess.append(text_adapt_3)
            
        return "\n".join(combined_tess).strip()
    except Exception as e:
        print(f"Enhanced Tesseract OCR failed on {file_path}: {e}")
        try:
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img, config="--psm 3").strip()
        except Exception:
            return ""

def extract_text_from_digital_pdf(file_path: str) -> str:
    """Extract digital selectable text from a PDF file using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber digital extract error on {file_path}: {e}")
    return text.strip()

def extract_text_from_scanned_pdf(file_path: str) -> str:
    """
    Extract text from a scanned/image-based PDF by converting each page
    to a high-resolution PIL image and applying Apple Vision / Tesseract OCR.
    """
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    page_img = page.to_image(resolution=200).original
                    if page_img.mode != "RGB":
                        page_img = page_img.convert("RGB")
                    
                    tmp_page = f"/tmp/_pdf_page_{i}_{os.getpid()}.png"
                    page_img.save(tmp_page)
                    
                    # Try Apple Vision first
                    p_text = extract_apple_vision(tmp_page)
                    if not p_text.strip():
                        p_text = pytesseract.image_to_string(page_img, config="--psm 3")
                        
                    if os.path.exists(tmp_page):
                        os.remove(tmp_page)
                        
                    if p_text and p_text.strip():
                        text += f"\n--- Page {i+1} ---\n" + p_text.strip() + "\n"
                except Exception as page_err:
                    print(f"Error OCRing PDF page {i+1} of {file_path}: {page_err}")
    except Exception as e:
        print(f"Failed to open PDF for image OCR {file_path}: {e}")
    return text.strip()

def extract_text_from_image(file_path: str, document_type: str = "") -> str:
    """
    Extract text from an image (.png, .jpg, .jpeg, .webp, .tiff).
    Multi-engine ensemble:
    1. Native Apple Vision OCR (macOS state-of-the-art offline handwriting recognition)
    2. OCR.space API Engine 2 (specialized for handwritten documents)
    3. OpenCV CLAHE-enhanced multi-pass Tesseract OCR
    Combines outputs into a rich multi-perspective OCR transcript for downstream clinical NLP.
    """
    print(f"Starting multi-engine OCR extraction on {file_path} (type: {document_type})...")
    
    # 1. Native Apple Vision OCR
    apple_vision_text = extract_apple_vision(file_path)
    
    # 2. OCR.space Engine 2
    ocr_space_text = extract_ocr_space(file_path, engine="2")
    
    # 3. OpenCV enhanced Tesseract
    tesseract_text = extract_tesseract_enhanced(file_path)
    
    # Check if we have multiple valuable streams
    streams = []
    if apple_vision_text.strip():
        streams.append(f"[PRIMARY NATIVE VISION OCR STREAM]:\n{apple_vision_text.strip()}")
        
    if ocr_space_text.strip() and ocr_space_text.strip() != apple_vision_text.strip():
        streams.append(f"[COMPLEMENTARY HANDWRITING ENGINE OCR STREAM]:\n{ocr_space_text.strip()}")
        
    if tesseract_text.strip():
        # Only include tesseract if it adds distinct signal or if others are empty
        if not streams or len(tesseract_text.strip()) > 20:
            streams.append(f"[ENHANCED CONTRAST OCR STREAM]:\n{tesseract_text.strip()}")
            
    if streams:
        combined = "\n\n".join(streams)
        print(f"OCR successfully extracted {len(combined)} characters across {len(streams)} engine stream(s).")
        return combined
        
    return ""

def extract_text_from_text_file(file_path: str) -> str:
    """Read plain text, markdown, CSV, or JSON directly."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading text file {file_path}: {e}")
        return ""

async def extract_text(file_path: str, document_type: str) -> str:
    """
    Main extraction router based on file extension and document type.
    Handles digital PDFs, scanned PDFs, images, and text documents.
    """
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    # 1. Plain text formats
    if ext in [".txt", ".csv", ".json", ".md"]:
        return extract_text_from_text_file(file_path)
        
    # 2. PDF formats
    if ext == ".pdf":
        text = extract_text_from_digital_pdf(file_path)
        if len(text.strip()) < 30:
            print(f"PDF {file_path} contains minimal digital text. Running scanned PDF OCR...")
            scanned_text = extract_text_from_scanned_pdf(file_path)
            if scanned_text.strip():
                text = scanned_text
                
        if not text.strip():
            print("Running OCR.space API fallback for PDF...")
            text = extract_ocr_space(file_path, engine="1")
                
        return text.strip()
        
    # 3. Image formats
    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
        text = extract_text_from_image(file_path, document_type)
        return text.strip()
        
    # 4. Fallback for other file types
    text = extract_text_from_digital_pdf(file_path)
    if not text.strip():
        text = extract_text_from_image(file_path, document_type)
        
    return text.strip()
