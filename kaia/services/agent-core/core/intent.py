# core/intent.py
# Classifies a user message into one of 10 intent categories using the LLM.
# Used by conversation_loop.py to decide whether to trigger a module or just chat.

from llm.client import ask_llm

INTENT_PROMPT = """Classify the user message into exactly one category. Reply with only the category name.

Categories and when to use them:
- chat: general conversation, greetings, feelings, questions, anything else
- food: asking what to eat, recipe ideas, meal suggestions
- clothing: what to wear, outfit ideas, clothes shopping
- news: asking about news, current events, what happened today
- article: asking for a long read, article recommendation
- events: asking about events, concerts, activities in the city
- price: asking to track a product price, price drop alerts
- tone_change: ONLY when user explicitly asks to change speaking style (e.g. "be more serious", "talk casually", "be professional") — NOT for general expressions like "great", "nice", "thanks"
- module: enabling or disabling a feature (/module food on)
- unclear: cannot determine

Examples:
"Hi how are you" → chat
"it's great thanks" → chat
"what should I eat" → food
"be more serious please" → tone_change
"any events this week" → events
"what's the news today" → news

Message: "{message}"

Category:"""

VALID_INTENTS = {
    "chat", "clothing", "food", "news", "article",
    "events", "price", "tone_change", "module", "unclear",
}


def detect_intent(message: str) -> str:
    result = ask_llm(INTENT_PROMPT.format(message=message), temperature=0.1)
    intent = result.strip().lower()
    return intent if intent in VALID_INTENTS else "unclear"
