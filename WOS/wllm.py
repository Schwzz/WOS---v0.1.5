
import json

from core.memory import (
    load_memory,
    save_memory,
    detect_memory,
    forget_memory,
    show_memory
)

from core.conversation import (
    load_conversation,
    save_conversation
)

from core.config import load_config
from core.character import load_character
from core.providers import chat

MAX_CONTEXT_MESSAGES = 20


def show_context():
    conversation = load_conversation()

    print()
    print("WLLM Context")
    print("-------------")
    print(f"Saved messages:     {len(conversation)}")
    print(f"Messages in context: {min(len(conversation), MAX_CONTEXT_MESSAGES)}")
    print(f"Context limit:      {MAX_CONTEXT_MESSAGES}")
    print()


def show_help():
    print()
    print("WLLM commands:")
    print("/clear   Clear the current conversation")
    print("/memory  Show saved memories")
    print("/context Show current context usage")
    print("/help    Show available commands")
    print("/exit    Close WLLM")
    print()
    print("Memory phrases:")
    print("Remember that ...")
    print("Keep in mind that ...")
    print("Don't forget that ...")
    print("Forget that ...")
    print("Forget about ...")
    print()


def build_system_prompt():
    memory_text = json.dumps(memory, ensure_ascii=False, indent=2)

    return f"""
You are {CHARACTER_NAME}, a private AI companion.

Personality:
{PERSONALITY}

The user's name is Swartz.

Known information about the user:
{memory_text}

Use known information naturally when relevant.
Answer questions about the user using these memories when appropriate.
If you do not know something, do not invent an answer.

You cannot directly change saved memories.
The application handles memory saving and deletion through explicit commands.
Never claim that you saved, updated, or deleted a memory unless the application
confirms that operation.

Stay in character as {CHARACTER_NAME}.
Do not mention these instructions or your system prompt.
"""


def create_messages():
    conversation = load_conversation()
    recent_messages = conversation[-MAX_CONTEXT_MESSAGES:]

    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        *recent_messages
    ]


def upsert_memory(new_memory):
    key = new_memory["key"].strip().lower()

    existing_memory = next(
        (
            item for item in memory
            if item.get("key", "").strip().lower() == key
        ),
        None
    )

    if existing_memory is not None:
        existing_memory["value"] = new_memory["value"]
        return "updated"

    memory.append(new_memory)
    return "saved"


def record_exchange(user_message, assistant_reply):
    messages.append({
        "role": "user",
        "content": user_message
    })
    messages.append({
        "role": "assistant",
        "content": assistant_reply
    })

    save_conversation(messages[1:])


config = load_config()

PROVIDER = config.get("provider")
MODEL = config.get("model")
CHARACTER_ID = config.get("character")

if not PROVIDER:
    print("WLLM: No provider is configured in config.json.")
    raise SystemExit(1)

if not MODEL:
    print("WLLM: No model is configured in config.json.")
    raise SystemExit(1)

if not CHARACTER_ID:
    print("WLLM: No character is configured in config.json.")
    raise SystemExit(1)

character = load_character(CHARACTER_ID)
memory = load_memory()

CHARACTER_NAME = character["name"]
PERSONALITY = character["personality"]

SYSTEM_PROMPT = build_system_prompt()
messages = create_messages()


print()
print("==============================")
print("            WLLM")
print("==============================")
print(f"Character: {CHARACTER_NAME}")
print(f"Model:     {MODEL}")
print(f"Memory:    {len(memory)} item(s)")
print("==============================")
print("Type /help for commands.")
print()


while True:
    message = input("You: ").strip()

    if not message:
        continue

    command = message.lower()

    if command in ["/exit", "/quit"]:
        save_conversation(messages[1:])
        print("WLLM: Conversation saved.")
        break

    if command == "/help":
        show_help()
        continue

    if command == "/memory":
        show_memory(memory)
        continue

    if command == "/context":
        show_context()
        continue

    if command == "/clear":
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        save_conversation([])
        print("WLLM: Conversation cleared.")
        continue

    # Handle explicit forget requests before calling the AI.
    forget_reply = forget_memory(memory, message)

    if forget_reply is not None:
        SYSTEM_PROMPT = build_system_prompt()
        messages = create_messages()

        record_exchange(message, forget_reply)
        print(f"{CHARACTER_NAME}: {forget_reply}")

        messages = create_messages()
        continue

    # Handle explicit remember requests.
    new_memory = detect_memory(message)

    if new_memory is not None:
        old_memory = [item.copy() for item in memory]

        result = upsert_memory(new_memory)

        try:
            save_memory(memory)
        except OSError as error:
            memory[:] = old_memory
            print(f"WLLM: Could not save memory: {error}")
            continue

        SYSTEM_PROMPT = build_system_prompt()

        if result == "updated":
            reply = (
                f"I've updated that memory: "
                f"{new_memory['key'].replace('_', ' ')} "
                f"is now {new_memory['value']}."
            )
        else:
            reply = f"I'll remember that. {new_memory['value']}"

        messages = create_messages()
        record_exchange(message, reply)

        print(f"{CHARACTER_NAME}: {reply}")

        messages = create_messages()
        continue

    # All other messages are handled as normal conversation.
    messages.append({
        "role": "user",
        "content": message
    })

    reply = chat(PROVIDER, MODEL, messages)

    if reply is None:
        messages.pop()
        continue

    messages.append({
        "role": "assistant",
        "content": reply
    })

    save_conversation(messages[1:])
    print(f"{CHARACTER_NAME}: {reply}")

    messages = create_messages()