# llm/client.py
# The single entry point for all LLM calls in KAIA.
# Primary: Google Gemini (gemini-2.5-flash for speed, gemini-2.5-pro for complex tasks).
# Fallback: Ollama / Mistral running locally — used when Gemini API is unavailable.
# Web search: pass use_search=True to let Gemini query Google in real-time.

import logging
import os

import httpx

logger = logging.getLogger("llm.client")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_URL     = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")

# Gemini model names — flash is the default, pro is used for heavy reasoning tasks
GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO   = "gemini-2.5-pro"


def ask_llm(
    prompt: str,
    system: str = None,
    history: list = None,
    temperature: float = 0.7,
    model: str = "flash",       # "flash" | "pro" | any explicit model name
    use_search: bool = False,   # True → Gemini searches Google before answering
) -> str:
    if GEMINI_API_KEY:
        try:
            return _ask_gemini(prompt, system, history, temperature, model, use_search)
        except Exception as e:
            logger.warning(f"Gemini failed ({e}), falling back to Ollama")

    # Ollama fallback
    return _ask_ollama(prompt, system, history, temperature)


# ── Gemini ────────────────────────────────────────────────────────────────────

def _ask_gemini(
    prompt: str,
    system: str,
    history: list,
    temperature: float,
    model: str,
    use_search: bool,
) -> str:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig

    genai.configure(api_key=GEMINI_API_KEY)

    model_name = GEMINI_PRO if model == "pro" else (model if model not in ("flash", "pro") else GEMINI_FLASH)

    # Google Search grounding tool — lets Gemini pull live web results
    tools = ["google_search_retrieval"] if use_search else None

    gemini_model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system or "",
        tools=tools,
    )

    # Convert history to Gemini format: [{"role": "user"/"model", "parts": [...]}]
    chat_history = []
    if history:
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            chat_history.append({"role": role, "parts": [msg["content"]]})

    chat = gemini_model.start_chat(history=chat_history)
    response = chat.send_message(
        prompt,
        generation_config=GenerationConfig(temperature=temperature),
    )
    return response.text


# ── Ollama (local fallback) ───────────────────────────────────────────────────

def _ask_ollama(
    prompt: str,
    system: str,
    history: list,
    temperature: float,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": prompt})

    response = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
