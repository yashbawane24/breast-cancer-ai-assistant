"""
Wrapper around the Groq API (LLaMA / Qwen models) with both synchronous and native asynchronous clients.
"""
from groq import Groq, AsyncGroq
from app.config import settings

client = Groq(api_key=settings.groq_api_key)
async_client = AsyncGroq(api_key=settings.groq_api_key)
