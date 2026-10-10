
import json
import os
import re
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = PROJECT_ROOT / "data" / "memory.json"

_MEMORY_FILE_INVALID = False


def _is_valid_memory(data):
    return (
        isinstance(data, list)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("key"), str)
            and isinstance(item.get("value"), str)
            for item in data
        )
    )


def _deduplicate_memory(memory):
    """Remove duplicate keys while preserving their original order."""
    unique = []
    positions = {}

    for item in memory:
        if not isinstance(item, dict):
            continue

        key = item.get("key")
        value = item.get("value")

        if not isinstance(key, str) or not isinstance(value, str):
            continue

        normalized_key = normalize_key(key)

        if not normalized_key:
            continue

        cleaned = {"key": key, "value": value}

        if normalized_key in positions:
            unique[positions[normalized_key]] = cleaned
        else:
            positions[normalized_key] = len(unique)
            unique.append(cleaned)

    return unique


def load_memory():
    global _MEMORY_FILE_INVALID

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_FILE_INVALID = False

    if not MEMORY_PATH.exists():
        return []

    try:
        with MEMORY_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not _is_valid_memory(data):
            _MEMORY_FILE_INVALID = True
            print("WOS: Memory file contains invalid data.")
            return []

        return _deduplicate_memory(data)

    except (json.JSONDecodeError, OSError) as error:
        _MEMORY_FILE_INVALID = True
        print(f"WOS: Could not load memory: {error}")
        return []


def save_memory(memory):
    """Save memories atomically without overwriting invalid existing data."""
    global _MEMORY_FILE_INVALID

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if _MEMORY_FILE_INVALID:
        raise OSError(
            "The existing memory file could not be loaded safely."
        )

    if MEMORY_PATH.exists():
        try:
            with MEMORY_PATH.open("r", encoding="utf-8") as file:
                existing_data = json.load(file)

            if not _is_valid_memory(existing_data):
                _MEMORY_FILE_INVALID = True
                raise OSError(
                    "The existing memory file contains invalid data."
                )

        except json.JSONDecodeError as error:
            _MEMORY_FILE_INVALID = True
            raise OSError(
                "The existing memory file contains invalid JSON."
            ) from error

    if not _is_valid_memory(memory):
        raise ValueError("Memory must be a list of valid memory entries.")

    cleaned_memory = _deduplicate_memory(memory)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=MEMORY_PATH.parent,
            prefix="memory_",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)

            json.dump(
                cleaned_memory,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, MEMORY_PATH)
        temporary_path = None
        memory[:] = cleaned_memory

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def normalize_key(text):
    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^a-z0-9]+", "_", text.lower()),
    ).strip("_")


def _excluded_subjects(text):
    """Extract subjects explicitly excluded by a question."""
    patterns = (
        r"\bbesides\s+(.+?)(?=[?.!,;]|$)",
        r"\bother than\s+(.+?)(?=[?.!,;]|$)",
        r"\bapart from\s+(.+?)(?=[?.!,;]|$)",
        r"\bexcluding\s+(.+?)(?=[?.!,;]|$)",
        r"\bexcept for\s+(.+?)(?=[?.!,;]|$)",
        r"\bexcept\s+(.+?)(?=[?.!,;]|$)",
        r"\bnot\s+([a-z][a-z0-9+#.-]*(?:\s+[a-z][a-z0-9+#.-]*){0,3})(?=[?.!,;]|$)",
    )

    excluded = set()

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            subject = normalize_key(match.group(1))

            if subject:
                excluded.add(subject)

    return excluded


def _memory_subject(item):
    """Return the subject represented by a learning memory."""
    key = normalize_key(item.get("key", ""))

    if key.startswith("fact_learning_"):
        return key[len("fact_learning_"):]

    value = item.get("value", "")
    match = re.match(
        r"^(?:i am|i'm)\s+learning\s+(.+)$",
        value.strip(),
        re.IGNORECASE,
    )

    if match:
        return normalize_key(match.group(1))

    return ""


def _is_excluded_learning_memory(item, excluded_subjects):
    """Check whether a learning memory matches an excluded subject."""
    subject = _memory_subject(item)

    if not subject:
        return False

    for excluded in excluded_subjects:
        if subject == excluded:
            return True

        # Match multiword subjects without treating partial words
        # as equivalent subjects.
        if (
            subject.startswith(excluded + "_")
            or excluded.startswith(subject + "_")
        ):
            return True

    return False


def find_memory(memory, query):
    """Find an exact memory or a clearly relevant natural-language match."""
    normalized_query = normalize_key(query)

    if not normalized_query:
        return None

    text = query.strip().lower()

    question_patterns = (
        r"^(?:what|which|who|where|when|how)\b",
        r"^(?:do|did|can|could)\s+you\s+remember\b",
        r"^what\s+do\s+you\s+know\s+about\s+me\b",
        r"^what\s+did\s+i\s+tell\s+you\b",
        r"^do\s+you\s+know\b",
    )

    is_question = any(
        re.search(pattern, text) for pattern in question_patterns
    )

    excluded_subjects = _excluded_subjects(text)

    wants_learning = bool(
        re.search(r"\b(learn|learning|study|studying)\b", text)
    )

    # If a question asks about learning while excluding a subject,
    # search the remaining learning memories rather than returning
    # an excluded memory or falling through to general word matching.
    if is_question and wants_learning and excluded_subjects:
        candidates = [
            item for item in memory
            if normalize_key(item.get("key", "")).startswith(
                "fact_learning_"
            )
            and not _is_excluded_learning_memory(
                item, excluded_subjects
            )
        ]

        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) > 1:
            query_words = set(normalized_query.split("_"))
            scored = []

            for item in candidates:
                subject = _memory_subject(item)
                subject_words = set(subject.split("_"))
                overlap = len(query_words & subject_words)

                if overlap:
                    scored.append((overlap, item))

            scored.sort(key=lambda result: result[0], reverse=True)

            if (
                scored
                and (
                    len(scored) == 1
                    or scored[0][0] > scored[1][0]
                )
            ):
                return scored[0][1]

        return None

    # Preserve exact key lookup for ordinary queries.
    for item in memory:
        if normalize_key(item.get("key", "")) == normalized_query:
            return item

    if not is_question:
        return None

    wants_usage = bool(
        re.search(r"\b(use|using|used)\b", text)
    )
    wants_favorite = bool(
        re.search(r"\b(favorite|favourite)\b", text)
    )

    candidates = []

    for item in memory:
        key = normalize_key(item.get("key", ""))

        if wants_learning and key.startswith("fact_learning_"):
            candidates.append(item)
            continue

        if wants_favorite and key.startswith("favorite_"):
            category = key[len("favorite_"):]
            if category in normalized_query:
                candidates.append(item)
            continue

        if wants_usage and key.startswith("fact_i_use_"):
            distinctive_parts = [
                part for part in key.split("_")
                if part not in {
                    "fact", "i", "use", "for", "a", "an", "the",
                    "what", "which", "do", "you", "me", "my",
                }
            ]

            query_words = set(normalized_query.split("_"))

            if any(part in query_words for part in distinctive_parts):
                candidates.append(item)

    if len(candidates) == 1:
        return candidates[0]

    ignored_words = {
        "what", "which", "who", "where", "when", "how",
        "am", "is", "are", "was", "were", "do", "does", "did",
        "i", "you", "me", "my", "mine", "your", "the", "a", "an",
        "to", "for", "of", "in", "on", "about", "that", "this",
        "and", "or", "it", "know", "remember", "tell", "told",
        "please", "can", "could",
    }

    query_words = {
        word for word in normalized_query.split("_")
        if word not in ignored_words
    }

    if not query_words:
        return None

    scored = []

    for item in memory:
        key_words = set(normalize_key(item.get("key", "")).split("_"))
        value_words = set(
            normalize_key(item.get("value", "")).split("_")
        )

        searchable_words = key_words | value_words
        overlap = query_words & searchable_words

        if overlap:
            scored.append((len(overlap), item))

    if not scored:
        return None

    scored.sort(key=lambda result: result[0], reverse=True)

    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None

    if scored[0][0] < 2:
        return None

    return scored[0][1]


def clean_statement(text):
    return text.strip().rstrip(".!?")


def parse_memory_statement(statement):
    statement = clean_statement(statement)

    if not statement:
        return None

    match = re.match(
        r"^my favorite (.+?) is (.+)$",
        statement,
        re.IGNORECASE,
    )
    if match:
        category = normalize_key(match.group(1))
        value = match.group(2).strip()

        if category and value:
            return {
                "key": f"favorite_{category}",
                "value": value,
            }

    match = re.match(
        r"^(?:i am|i'm) learning (.+)$",
        statement,
        re.IGNORECASE,
    )
    if match:
        subject = match.group(1).strip()

        if subject:
            return {
                "key": "fact_learning_" + normalize_key(subject),
                "value": f"I am learning {subject}",
            }

    match = re.match(
        r"^i use (.+?) for (.+)$",
        statement,
        re.IGNORECASE,
    )
    if match:
        tool = match.group(1).strip()
        purpose = match.group(2).strip()

        if tool and purpose:
            value = f"I use {tool} for {purpose}"
            return {
                "key": "fact_" + normalize_key(value),
                "value": value,
            }

    match = re.match(r"^call me (.+)$", statement, re.IGNORECASE)
    if match:
        name = match.group(1).strip()

        if name:
            return {
                "key": "personal_name",
                "value": name,
            }

    return {
        "key": "fact_" + normalize_key(statement),
        "value": statement,
    }


def detect_memory(message):
    """Detect explicit requests to remember information."""
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


def _delete_memory_item(memory, item, success_message):
    """Delete a memory and restore the list if saving fails."""
    original_memory = list(memory)
    memory.remove(item)

    try:
        save_memory(memory)
    except (OSError, ValueError) as error:
        memory[:] = original_memory
        print(f"WOS: Could not save memory changes: {error}")
        return "I couldn't save that change, so the memory was not deleted."

    return success_message


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

    favorite_match = re.match(
        r"^my favorite (.+?) (?:is|being) (.+)$",
        target,
        re.IGNORECASE,
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
                return _delete_memory_item(
                    memory,
                    item,
                    f"I've forgotten that your favorite "
                    f"{category.replace('_', ' ')} is {saved_value}.",
                )

        return "I couldn't find that saved favorite, so nothing was deleted."

    normalized_target = normalize_key(target)

    possible_keys = {
        normalized_target,
        "fact_" + normalized_target,
        "fact_learning_" + normalized_target,
    }

    for item in memory:
        key = normalize_key(item.get("key", ""))

        if key in possible_keys:
            value = str(item.get("value", "")).strip()

            return _delete_memory_item(
                memory,
                item,
                f"I've forgotten that memory: {value}.",
            )

    for item in memory:
        display_key = item.get("key", "").replace("_", " ")

        if display_key.casefold() == target.casefold():
            value = str(item.get("value", "")).strip()

            return _delete_memory_item(
                memory,
                item,
                f"I've forgotten that memory: {value}.",
            )

    for item in memory:
        value = str(item.get("value", "")).strip()

        if value.casefold() == target.casefold():
            return _delete_memory_item(
                memory,
                item,
                f"I've forgotten that memory: {value}.",
            )

    return "I couldn't find that saved memory, so nothing was deleted."


def edit_memory(memory, target, new_value):
    """Edit one memory by its key or exact saved value."""
    target = target.strip()
    new_value = new_value.strip()

    if not target or not new_value:
        return "Both the memory to edit and its new value are required."

    normalized_target = normalize_key(target)

    item = next(
        (
            entry for entry in memory
            if normalize_key(entry.get("key", "")) == normalized_target
        ),
        None,
    )

    if item is None:
        item = next(
            (
                entry for entry in memory
                if entry.get("value", "").strip().casefold()
                == target.casefold()
            ),
            None,
        )

    if item is None:
        return "I couldn't find that saved memory, so nothing was changed."

    original_memory = [dict(entry) for entry in memory]
    item["value"] = new_value

    try:
        save_memory(memory)
    except (OSError, ValueError) as error:
        memory[:] = original_memory
        print(f"WOS: Could not save memory changes: {error}")
        return "I couldn't save that change, so the memory was not edited."

    return "Memory updated successfully."


def clear_memory(memory, confirmed=False):
    """Clear all memories only when the caller explicitly confirms."""
    if not confirmed:
        return "Confirmation is required before clearing all memories."

    original_memory = [dict(entry) for entry in memory]
    memory.clear()

    try:
        save_memory(memory)
    except (OSError, ValueError) as error:
        memory[:] = original_memory
        print(f"WOS: Could not clear memories: {error}")
        return "I couldn't save that change, so the memories were not cleared."

    return "All saved memories have been cleared."


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
