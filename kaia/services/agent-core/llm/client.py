import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = "mistral:7b-instruct-q4_K_M"


def ask_llm(prompt: str, system: str = None, history: list = None, temperature: float = 0.7) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend({"role": m["role"], "content": m["content"]} for m in history)
    messages.append({"role": "user", "content": prompt})

    response = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
