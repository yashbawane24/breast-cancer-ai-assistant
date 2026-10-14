from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.translation_service import translate, translate_batch

router = APIRouter()

class TranslationRequest(BaseModel):
    text: str
    target_lang: str

class BatchTranslationRequest(BaseModel):
    texts: List[str]
    target_lang: str

@router.post("")
async def translate_text(request: TranslationRequest):
    translated = await translate(request.text, request.target_lang)
    return {"translated_text": translated}

@router.post("/batch")
async def translate_batch_texts(request: BatchTranslationRequest):
    translated = await translate_batch(request.texts, request.target_lang)
    return {"translated_texts": translated}
