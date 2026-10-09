import json

MEMORY_FILE = "data/memory.json"


def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as file:
            memory = json.load(file)

            if not isinstance(memory, list):
                print("WLLM: Memory file must contain a list.")
                return []

            return memory

    except FileNotFoundError:
        return []

    except json.JSONDecodeError:
        print("WLLM: Memory file is invalid. Starting with empty memory.")
        return []


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as file:
        json.dump(memory, file, indent=4, ensure_ascii=False)


def find_memory(memory, question):
    question = question.lower()

    for item in memory:
        key = item.get("key", "").lower()
        value = item.get("value", "")

        words = key.replace("_", " ").split()

        if all(word in question for word in words):
            return value

    return None


def detect_memory(message):
    text = message.strip()
    prefix = "my favorite "
    lowered = text.lower()

    if lowered.startswith(prefix) and " is " in lowered:
        remainder = text[len(prefix):]
        parts = remainder.split(" is ", 1)

        if len(parts) != 2:
            return None

        key = parts[0].strip().lower().replace(" ", "_")
        value = parts[1].strip().rstrip(".!?")

        if not key or not value:
            return None

        return {
            "key": f"favorite_{key}",
            "value": value
        }

    return None


def show_memory(memory):
    if not memory:
        print("WLLM: No memories saved.")
        return

    print()
    print("Saved memories:")

    for item in memory:
        key = item.get("key", "unknown").replace("_", " ")
        value = item.get("value", "")
        print(f"- {key}: {value}")

    print()