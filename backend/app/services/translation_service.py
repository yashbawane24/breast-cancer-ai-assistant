"""
Translates medical and UI content into regional languages (Hindi, Tamil, Bengali).
Uses Qwen on Groq with local dictionary caching for instant UI translation.
"""
import json
from app.services.llm_service import client

TRANSLATION_MODEL = "qwen/qwen3.8-27b"

# Pre-compiled high-speed medical & UI dictionary
COMMON_DICTIONARY = {
    "hi": {
        "overview": "अवलोकन",
        "home": "होम",
        "upload": "अपलोड करें",
        "report insights": "रिपोर्ट अंतर्दृष्टि",
        "trends": "रुझान",
        "treatment sandbox": "उपचार सैंडबॉक्स",
        "sandbox": "सैंडबॉक्स",
        "assistant": "एआई सहायक",
        "chat": "चैट",
        "history": "इतिहास",
        "sign in": "साइन इन करें",
        "create account": "खाता बनाएं",
        "clinical summary": "नैदानिक सारांश",
        "terminologies explained": "शब्दावली स्पष्टीकरण",
        "patient demographics": "रोगी का विवरण",
        "recommendations": "सिफारिशें",
        "lab parameters": "लैब पैरामीटर",
        "extracted medications": "दवाइयाँ",
        "view original": "मूल देखें",
        "confidence": "विश्वास",
        "your timeline, compared": "आपकी समयरेखा, तुलना",
        "health trends": "स्वास्थ्य रुझान",
        "biomarker timeline": "बायोमार्कर समयरेखा",
        "compare two reports": "दो रिपोर्टों की तुलना करें",
        "compare": "तुलना करें",
        "proactive clinical alerts": "सक्रिय नैदानिक अलर्ट",
        "manchester triage system (mts) assessment": "मैनचेस्टर ट्राइएज सिस्टम (MTS) मूल्यांकन",
        "target response window": "लक्षित प्रतिक्रिया समय",
        "key clinical indicators": "प्रमुख नैदानिक संकेतक",
        "recommended next action": "अनुशंसित अगली कार्रवाई",
        "physician handwritten prescription extraction": "हस्तलिखित नुस्खे का विश्लेषण",
        "ask about your reports": "अपनी रिपोर्ट के बारे में पूछें",
        "upload a medical document": "चिकित्सा दस्तावेज़ अपलोड करें",
        "every report, understood.": "हर रिपोर्ट, आसानी से समझें।",
        "interactive clinical sandbox": "इंटरैक्टिव क्लिनिकल सैंडबॉक्स",
        "select biological subtype": "जैविक उपप्रकार चुनें",
        "clinical stage": "नैदानिक चरण",
        "recommended sequence pathway": "अनुशंसित उपचार क्रम",
        "treatment sequence steps": "उपचार के चरण"
    },
    "ta": {
        "overview": "மேற்பார்வை",
        "home": "முகப்பு",
        "upload": "பதிவேற்றவும்",
        "report insights": "அறிக்கை நுண்ணறிவு",
        "trends": "போக்குகள்",
        "treatment sandbox": "சிகிச்சை சாண்ட்பாக்ஸ்",
        "sandbox": "சாண்ட்பாக்ஸ்",
        "assistant": "உதவியாளர்",
        "chat": "உரையாடல்",
        "history": "வரலாறு",
        "sign in": "உள்நுழைக",
        "create account": "கணக்கை உருவாக்கவும்",
        "clinical summary": "மருத்துவ சுருக்கம்",
        "terminologies explained": "கலைச்சொல் விளக்கம்",
        "patient demographics": "நோயாளி விவரங்கள்",
        "recommendations": "பரிந்துரைகள்",
        "lab parameters": "ஆய்வக அளவீடுகள்",
        "extracted medications": "மருந்துகள்",
        "view original": "அசலைப் பார்",
        "confidence": "நம்பகத்தன்மை",
        "your timeline, compared": "உங்கள் காலவரிசை ஒப்பீடு",
        "health trends": "சுகாதார போக்குகள்",
        "biomarker timeline": "பயோமார்க் காலவரிசை",
        "compare two reports": "இரு அறிக்கைகளை ஒப்பிடு",
        "compare": "ஒப்பிடுக",
        "proactive clinical alerts": "செயல்முனைப்பு மருத்துவ எச்சரிக்கைகள்",
        "manchester triage system (mts) assessment": "மான்செஸ்டர் ட்ரையேஜ் மதிப்பீடு",
        "target response window": "இலக்கு மறுமொழி நேரம்",
        "key clinical indicators": "முக்கிய மருத்துவ குறிகாட்டிகள்",
        "recommended next action": "பரிந்துரைக்கப்பட்ட நடவடிக்கை",
        "physician handwritten prescription extraction": "மருத்துவர் கையெழுத்து மருந்துச்சீட்டு",
        "ask about your reports": "உங்கள் அறிக்கைகளைப் பற்றிக் கேளுங்கள்",
        "upload a medical document": "மருத்துவ ஆவணத்தைப் பதிவேற்றவும்",
        "every report, understood.": "ஒவ்வொரு அறிக்கையும் தெளிவாக புரிந்துகொள்ளப்படும்.",
        "interactive clinical sandbox": "ஊடாடும் சிகிச்சை சாண்ட்பாக்ஸ்"
    },
    "bn": {
        "overview": "সংক্ষিপ্ত বিবরণ",
        "home": "হোম",
        "upload": "আপলোড করুন",
        "report insights": "রিপোর্ট অন্তর্দৃষ্টি",
        "trends": "ট্রেন্ড ও পরিবর্তন",
        "treatment sandbox": "চিকিৎসা স্যান্ডবক্স",
        "sandbox": "স্যান্ডবক্স",
        "assistant": "সহায়ক",
        "chat": "চ্যাট",
        "history": "ইতিহাস",
        "sign in": "সাইন ইন করুন",
        "create account": "অ্যাকাউন্ট তৈরি করুন",
        "clinical summary": "ক্লিনিক্যাল সারাংশ",
        "terminologies explained": "পরিভাষা ব্যাখ্যা",
        "patient demographics": "রোগীর বিবরণ",
        "recommendations": "পরামর্শ",
        "lab parameters": "ল্যাব প্যারামিটার",
        "extracted medications": "ওষুধসমূহ",
        "view original": "আসল দেখুন",
        "confidence": "নির্ভরযোগ্যতা",
        "your timeline, compared": "আপনার টাইমলাইন তুলনা",
        "health trends": "স্বাস্থ্য প্রবণতা",
        "biomarker timeline": "বায়োমার্কার টাইমলাইন",
        "compare two reports": "দুটি রিপোর্ট তুলনা করুন",
        "compare": "তুলনা করুন",
        "proactive clinical alerts": "প্রোঅ্যাকটিভ ক্লিনিক্যাল সতর্কতা",
        "manchester triage system (mts) assessment": "ম্যানচেস্টার ট্রায়াজ মূল্যায়ন",
        "target response window": "প্রতিক্রিয়া সময়সীমা",
        "key clinical indicators": "মূল ক্লিনিক্যাল নির্দেশক",
        "recommended next action": "সুপারিশকৃত পদক্ষেপ",
        "physician handwritten prescription extraction": "ডাক্তারের হাতের লেখা প্রেসক্রিপশন",
        "ask about your reports": "আপনার রিপোর্ট সম্পর্কে জিজ্ঞাসা করুন",
        "upload a medical document": "চিকিৎসা নথি আপলোড করুন",
        "every report, understood.": "প্রতিটি রিপোর্ট, সহজে বোধগম্য।"
    }
}

memory_cache = {}

async def translate(text: str, target_lang: str) -> str:
    lang = target_lang.lower().strip()
    if lang in ["en", "english"] or not text:
        return text

    clean_key = text.lower().strip()
    # Check local dictionary
    if lang in COMMON_DICTIONARY and clean_key in COMMON_DICTIONARY[lang]:
        return COMMON_DICTIONARY[lang][clean_key]

    cache_key = f"{lang}:{text}"
    if cache_key in memory_cache:
        return memory_cache[cache_key]

    lang_map = {
        "hi": "Hindi",
        "ta": "Tamil",
        "bn": "Bengali"
    }
    target_lang_name = lang_map.get(lang, "Hindi")

    prompt = f"Translate the following medical or healthcare text directly into {target_lang_name}. Do NOT translate medical biomarker acronyms (like ER, PR, HER2, Ki-67, CA 15-3). Return ONLY the translated string without quotes or conversational commentary.\n\nText: {text}"

    try:
        from app.services.llm_service import async_client
        response = await async_client.chat.completions.create(
            model=TRANSLATION_MODEL,
            messages=[
                {"role": "system", "content": f"You are a professional medical translator into {target_lang_name}. Return ONLY the direct translation."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024
        )
        translated = response.choices[0].message.content.strip().strip('"').strip("'")
        if translated:
            memory_cache[cache_key] = translated
            return translated
    except Exception as e:
        print(f"Translation error: {e}")

    return text

async def translate_batch(texts: list[str], target_lang: str) -> list[str]:
    lang = target_lang.lower().strip()
    if lang in ["en", "english"] or not texts:
        return texts

    lang_map = {
        "hi": "Hindi",
        "ta": "Tamil",
        "bn": "Bengali"
    }
    target_lang_name = lang_map.get(lang, "Hindi")

    results = [None] * len(texts)
    missing_indices = []
    missing_texts = []

    # Check cache and common dictionary first
    for i, t in enumerate(texts):
        clean_key = (t or "").lower().strip()
        cache_key = f"{lang}:{t}"
        if lang in COMMON_DICTIONARY and clean_key in COMMON_DICTIONARY[lang]:
            results[i] = COMMON_DICTIONARY[lang][clean_key]
        elif cache_key in memory_cache:
            results[i] = memory_cache[cache_key]
        else:
            missing_indices.append(i)
            missing_texts.append(t)

    if not missing_texts:
        return results

    prompt = f"""Translate the following text items into {target_lang_name}. Do NOT translate medical biomarker names or acronyms (e.g. ER, PR, HER2, Ki-67, CA 15-3).
Return ONLY a valid JSON object with key "translations" containing the list of translated strings in the exact same order.

Texts to translate:
{json.dumps(missing_texts)}"""

    try:
        from app.services.llm_service import async_client
        response = await async_client.chat.completions.create(
            model=TRANSLATION_MODEL,
            messages=[
                {"role": "system", "content": f"You are a professional medical translator into {target_lang_name}. Output valid JSON with 'translations' list only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        translated_list = data.get("translations", [])

        for idx, trans in zip(missing_indices, translated_list):
            results[idx] = trans
            memory_cache[f"{lang}:{texts[idx]}"] = trans

    except Exception as e:
        print(f"Batch translation API error: {e}")

    # Fallback to original text for any that failed
    for i in range(len(results)):
        if results[i] is None:
            results[i] = texts[i]

    return results
