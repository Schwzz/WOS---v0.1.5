
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = PROJECT_ROOT / "data" / "memory.json"


def load_memory():
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not MEMORY_PATH.exists():
        return []

    try:
        with MEMORY_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            print("WLLM: Memory file must contain a JSON list.")
            return []

        return data

    except (json.JSONDecodeError, OSError) as error:
        print(f"WLLM: Could not load memory: {error}")
        return []


def save_memory(memory):
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with MEMORY_PATH.open("w", encoding="utf-8") as file:
        json.dump(memory, file, indent=2, ensure_ascii=False)


def normalize_key(text):
    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^a-z0-9]+", "_", text.lower())
    ).strip("_")


def find_memory(memory, key):
    normalized_key = normalize_key(key)

    for item in memory:
        if normalize_key(item.get("key", "")) == normalized_key:
            return item

    return None


def clean_statement(text):
    return text.strip().rstrip(".!?")


def parse_memory_statement(statement):
    statement = clean_statement(statement)

    if not statement:
        return None

    # Favorite facts
    match = re.match(
        r"^my favorite (.+?) is (.+)$",
        statement,
        re.IGNORECASE
    )
    if match:
        category = normalize_key(match.group(1))
        value = match.group(2).strip()

        if category and value:
            return {
                "key": f"favorite_{category}",
                "value": value
            }

    # Learning facts
    match = re.match(
        r"^(?:i am|i'm) learning (.+)$",
        statement,
        re.IGNORECASE
    )
    if match:
        subject = match.group(1).strip()

        if subject:
            return {
                "key": "fact_learning_" + normalize_key(subject),
                "value": f"I am learning {subject}"
            }

    # Tool and purpose facts
    match = re.match(
        r"^i use (.+?) for (.+)$",
        statement,
        re.IGNORECASE
    )
    if match:
        tool = match.group(1).strip()
        purpose = match.group(2).strip()

        if tool and purpose:
            value = f"I use {tool} for {purpose}"
            return {
                "key": "fact_" + normalize_key(value),
                "value": value
            }

    # Preferred name
    match = re.match(r"^call me (.+)$", statement, re.IGNORECASE)
    if match:
        name = match.group(1).strip()

        if name:
            return {
                "key": "personal_name",
                "value": name
            }

    # Generic facts are saved only after an explicit remember request.
    return {
        "key": "fact_" + normalize_key(statement),
        "value": statement
    }


def detect_memory(message):
    """Detect explicit requests to save or remember information."""
    text = clean_statement(message)

    patterns = (
        r"^(?:please\s+)?remember that\s+(.+)$",
        r"^(?:please\s+)?keep in mind that\s+(.+)$",
        r"^(?:please\s+)?don't forget that\s+(.+)$",
        r"^(?:please\s+)?do not forget that\s+(.+)$",
        r"^(?:please\s+)?remember\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)

        if match:
            statement = match.group(1).strip()
            return parse_memory_statement(statement)

    return None


def forget_memory(memory, message):
    """Delete a memory only when an explicit forget request is recognized."""
    text = clean_statement(message)

    patterns = (
        r"^(?:please\s+)?forget that\s+(.+)$",
        r"^(?:please\s+)?forget about\s+(.+)$",
        r"^(?:please\s+)?remove from memory\s+(.+)$",
        r"^(?:please\s+)?delete that memory\s*:\s*(.+)$",
    )

    target = None

    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)

        if match:
            target = match.group(1).strip()
            break

    if not target:
        return None

    # "Forget about my favorite anime being Frieren"
    favorite_match = re.match(
        r"^my favorite (.+?) (?:is|being) (.+)$",
        target,
        re.IGNORECASE
    )

    if favorite_match:
        category = normalize_key(favorite_match.group(1))
        value = favorite_match.group(2).strip()
        expected_key = f"favorite_{category}"

        for item in memory:
            key = normalize_key(item.get("key", ""))
            saved_value = str(item.get("value", "")).strip()

            if (
                key == expected_key
                and saved_value.casefold() == value.casefold()
            ):
                memory.remove(item)
                save_memory(memory)

                return (
                    f"I've forgotten that your favorite "
                    f"{category.replace('_', ' ')} is {saved_value}."
                )

        return "I couldn't find that saved favorite, so nothing was deleted."

    # Allow forgetting by the exact saved value or memory key.
    normalized_target = normalize_key(target)

    possible_keys = {
        normalized_target,
        "fact_" + normalized_target,
        "fact_learning_" + normalized_target,
    }

    for item in memory:
        key = normalize_key(item.get("key", ""))
        value = str(item.get("value", "")).strip()

        if (
            key in possible_keys
            or value.casefold() == target.casefold()
        ):
            memory.remove(item)
            save_memory(memory)
            return f"I've forgotten that memory: {value}."

    # Allow the human-readable key shown by /memory.
    for item in memory:
        display_key = item.get("key", "").replace("_", " ")

        if display_key.casefold() == target.casefold():
            value = item.get("value", "")
            memory.remove(item)
            save_memory(memory)
            return f"I've forgotten that memory: {value}."

    return "I couldn't find that saved memory, so nothing was deleted."


def show_memory(memory):
    print()

    if not memory:
        print("No saved memories.")
        print()
        return

    print("Saved memories:")

    for item in memory:
        key = item.get("key", "unknown")
        value = item.get("value", "")
        display_key = key.replace("_", " ")

        if key.startswith("favorite_"):
            display_key = (
                "favorite "
                + key[len("favorite_"):].replace("_", " ")
            )

        print(f"- {display_key}: {value}")

    print()