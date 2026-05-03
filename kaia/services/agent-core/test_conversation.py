import sys
from core.conversation_loop import handle_message_sync

USER_ID = "test_user"

print("KAIA Terminal Test — type 'quit' to exit\n")

while True:
    try:
        msg = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
        break

    if msg.lower() in ("quit", "exit"):
        break
    if not msg:
        continue

    response = handle_message_sync(USER_ID, msg)
    print(f"KAIA: {response}\n")
