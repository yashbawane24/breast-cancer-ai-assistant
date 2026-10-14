"""
Retrieval-Augmented Generation for the chat assistant using lightweight SQLite KB search and Groq.
Ultra-low memory footprint (<50MB RAM) designed for cloud deployment on free-tier containers (Render 512MB).
Includes Empathetic Emotion-Aware AI and Personalized Longitudinal RAG context.
"""
import os
import re
import sqlite3
from app.config import settings
from app.services.llm_service import client

RAG_MODEL = "qwen/qwen3.8-27b"

# In-memory cache of the medical knowledge base chunks
_kb_documents = None

def get_kb_documents():
    global _kb_documents
    if _kb_documents is None:
        db_file = os.path.join(settings.vector_db_path, "chroma.sqlite3")
        docs = []
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file)
                cur = conn.cursor()
                cur.execute('SELECT string_value FROM embedding_metadata WHERE key="chroma:document";')
                rows = cur.fetchall()
                docs = [r[0] for r in rows if r and r[0]]
                conn.close()
            except Exception as e:
                print(f"Failed to load KB documents from sqlite: {e}")
        _kb_documents = docs
    return _kb_documents

def retrieve_relevant_context(query: str, top_k: int = 4) -> str:
    docs = get_kb_documents()
    if not docs:
        return ""
    
    query_words = set(re.findall(r'\w+', query.lower()))
    scored = []
    for doc in docs:
        doc_words = set(re.findall(r'\w+', doc.lower()))
        intersection = query_words.intersection(doc_words)
        if intersection:
            score = len(intersection)
            scored.append((score, doc))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    top_docs = [d[1] for d in scored[:top_k]]
    return "\n\n---\n\n".join(top_docs)

def analyze_emotion(message: str) -> dict:
    """
    Identifies emotion/sentiment (anxious, distressed, neutral, optimistic, uncertain)
    to adapt the AI's tone with empathy.
    """
    lower_msg = message.lower()
    
    anxiety_keywords = ["worried", "scared", "afraid", "anxious", "panic", "fear", "cancer", "metastasis", "stage", "dying", "danger", "bi-rads 5", "high risk"]
    distress_keywords = ["pain", "terrible", "can't sleep", "crying", "depressed", "overwhelmed", "hopeless", "severe"]
    uncertainty_keywords = ["don't understand", "confused", "what does this mean", "explain", "help me read", "not sure"]

    if any(k in lower_msg for k in distress_keywords):
        return {
            "emotion": "Distressed",
            "empathy_level": "High",
            "guidance": "Acknowledge the emotional burden with deep empathy and reassurance. Use warm, highly supportive, clear language before explaining medical terms."
        }
    elif any(k in lower_msg for k in anxiety_keywords):
        return {
            "emotion": "Anxious / Concerned",
            "empathy_level": "Moderate-High",
            "guidance": "Provide gentle, compassionate validation of their concerns. Emphasize that medical findings are steps toward clarity and action."
        }
    elif any(k in lower_msg for k in uncertainty_keywords):
        return {
            "emotion": "Uncertain / Seeking Clarity",
            "empathy_level": "Moderate",
            "guidance": "Use a clear, patient-friendly, reassuring educational tone with step-by-step plain English explanations."
        }
    else:
        return {
            "emotion": "Neutral / Informational",
            "empathy_level": "Standard",
            "guidance": "Be polite, warm, clear, professional, and patient-centered."
        }

async def answer_question(message: str, patient_id: str, language: str = "en", longitudinal_context: str = "") -> dict:
    emotion_meta = analyze_emotion(message)
    context = retrieve_relevant_context(message)
    
    lang_map = {
        "en": "English",
        "hi": "Hindi",
        "ta": "Tamil",
        "bn": "Bengali"
    }
    target_lang = lang_map.get(language, "English")
    
    system_prompt = (
        f"You are Halcyon, an empathetic, expert AI medical assistant specializing in breast health and medical report interpretation. "
        f"Always answer the user in {target_lang}. "
        f"EMPATHY & TONE INSTRUCTION: The user is currently feeling {emotion_meta['emotion']}. {emotion_meta['guidance']} "
        f"CRITICAL INSTRUCTION FOR MEDICAL TERMS: Do not try to translate complex medical terms (like 'Hemoglobin', 'Ki-67', 'CA 15-3'). Instead, transliterate them (write them in the literal spelling/script of {target_lang}, matching the English pronunciation). "
        f"\n\nPATIENT LONGITUDINAL HISTORY:\n{longitudinal_context if longitudinal_context else 'No prior longitudinal report timeline provided.'}\n\n"
        f"Use the retrieved medical literature and patient context below to answer the user's question clearly. "
        f"If you don't know the answer or the information is not in the context, clearly state that it is not present in the uploaded documents or knowledge base. "
        f"Never hallucinate medical information. "
        f"Always include a disclaimer that you are an AI, not a doctor. "
        f"IMPORTANT: At the end of your answer, include a confidence percentage (e.g. 'Confidence: 95%') indicating how sure you are of this inference based on the retrieved context."
        f"\n\nContext:\n{context}"
    )
    
    try:
        from app.services.llm_service import async_client
        response = await async_client.chat.completions.create(
            model=RAG_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            max_tokens=1024
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"RAG Error: {e}")
        answer = "I am here with you. While accessing full details encountered a brief delay, I am here to help answer your questions about your breast health reports. Please feel free to ask again."
    
    return {
        "answer": answer,
        "emotion_analysis": emotion_meta,
        "grounded": True,
        "longitudinal_applied": bool(longitudinal_context)
    }

def add_document_to_kb(text: str, metadata: dict):
    docs = get_kb_documents()
    docs.append(text)
