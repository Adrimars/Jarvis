from llm.client import ask_llm
from llm.prompts import KAIA_SYSTEM
from memory.conversation import ConversationMemory
from core.intent import detect_intent
from core.tone_manager import ToneManager, extract_tone_from_message

MODULE_INTENTS = {"clothing", "food", "news", "article", "events", "price"}


async def handle_message(user_id: str, message: str) -> str:
    memory = ConversationMemory(user_id)
    tone = ToneManager(user_id)

    intent = detect_intent(message)

    if intent == "tone_change":
        new_tone = extract_tone_from_message(message)
        tone.set(new_tone)
        response = "Anladım." if new_tone == "serious" else "Tamam :)"
        memory.add("user", message)
        memory.add("assistant", response)
        return response

    if intent in MODULE_INTENTS:
        return await _trigger_module(intent, message, user_id, memory, tone)

    recent = memory.get_recent(last_n=20)
    summary = memory.get_summary()

    system = KAIA_SYSTEM + f"\nTone: {tone.instruction()}"
    if summary:
        system += f"\nPrevious conversation summary: {summary}"

    response = ask_llm(message, system=system, history=recent)

    memory.add("user", message)
    memory.add("assistant", response)

    return response


async def _trigger_module(intent: str, message: str, user_id: str, memory: ConversationMemory, tone: ToneManager) -> str:
    memory.add("user", message)
    response = f"[{intent} module not yet implemented — coming in a later week]"
    memory.add("assistant", response)
    return response


def handle_message_sync(user_id: str, message: str) -> str:
    import asyncio
    return asyncio.run(handle_message(user_id, message))
