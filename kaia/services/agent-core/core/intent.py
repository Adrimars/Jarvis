from llm.client import ask_llm

INTENT_PROMPT = """Analyze the user message. Which category does it belong to?

Categories:
chat | clothing | food | news | article | events | price | tone_change | module | unclear

Message: "{message}"

Write only the category name, nothing else."""

VALID_INTENTS = {
    "chat", "clothing", "food", "news", "article",
    "events", "price", "tone_change", "module", "unclear",
}


def detect_intent(message: str) -> str:
    result = ask_llm(INTENT_PROMPT.format(message=message), temperature=0.1)
    intent = result.strip().lower()
    return intent if intent in VALID_INTENTS else "unclear"
