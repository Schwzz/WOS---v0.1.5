
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"

CHATS_DIR = DATA_DIR / "chats"
INDEX_FILE = CHATS_DIR / "index.json"
ACTIVE_SESSION_FILE = CHATS_DIR / "active_session.json"
OLD_CONVERSATION_FILE = DATA_DIR / "conversation.json"

MAX_CHATS = 3


def get_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def ensure_chat_directory():
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(file_path, data, indent=4):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f"{file_path.stem}_",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)

            json.dump(data, file, indent=indent, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, file_path)
        temporary_path = None

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def load_index():
    ensure_chat_directory()

    try:
        with INDEX_FILE.open("r", encoding="utf-8") as file:
            index = json.load(file)

        if not isinstance(index, list):
            print("WOS: Chat index must contain a JSON list.")
            return []

        return [
            item for item in index
            if isinstance(item, dict)
            and isinstance(item.get("session_id"), str)
            and re.fullmatch(r"session_\d+", item["session_id"])
        ]

    except FileNotFoundError:
        return []

    except (json.JSONDecodeError, OSError) as error:
        print(f"WOS: Could not load chat index: {error}")
        return []


def save_index(index):
    _atomic_write_json(INDEX_FILE, index)


def get_next_session_id(index=None):
    numbers = []

    if index is None:
        index = load_index()

    for item in index:
        match = re.fullmatch(
            r"session_(\d+)", item.get("session_id", "")
        )
        if match:
            numbers.append(int(match.group(1)))

    ensure_chat_directory()

    for filename in os.listdir(CHATS_DIR):
        match = re.fullmatch(r"session_(\d+)\.json", filename)
        if match:
            numbers.append(int(match.group(1)))

    return f"session_{max(numbers, default=0) + 1:03d}"


def get_chat_file(session_id):
    if not isinstance(session_id, str) or not re.fullmatch(
        r"session_\d+", session_id
    ):
        raise ValueError("Invalid session ID.")

    return CHATS_DIR / f"{session_id}.json"


def load_chat(session_id):
    try:
        chat_file = get_chat_file(session_id)

        with chat_file.open("r", encoding="utf-8") as file:
            chat = json.load(file)

        if not isinstance(chat, dict):
            return None

        if chat.get("session_id") != session_id:
            return None

        messages = chat.get("messages", [])

        if not isinstance(messages, list):
            return None

        for message in messages:
            if (
                not isinstance(message, dict)
                or not isinstance(message.get("role"), str)
                or not isinstance(message.get("content"), str)
            ):
                return None

        chat.setdefault(
            "title", session_id.replace("_", " ").title()
        )
        chat.setdefault("created", get_timestamp())
        chat.setdefault("updated", chat["created"])
        chat["messages"] = messages

        return chat

    except (FileNotFoundError, ValueError):
        # Missing or invalid IDs are normal lookup failures.
        return None

    except (json.JSONDecodeError, OSError) as error:
        print(f"WOS: Could not load chat '{session_id}': {error}")
        return None


def save_chat(chat):
    if not isinstance(chat, dict):
        raise ValueError("Chat data must be a dictionary.")

    session_id = chat.get("session_id")
    chat_file = get_chat_file(session_id)
    messages = chat.get("messages", [])

    if not isinstance(messages, list):
        raise ValueError("Chat messages must be a list.")

    for message in messages:
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
        ):
            raise ValueError("Chat contains an invalid message.")

    _atomic_write_json(chat_file, chat)


def set_active_session(session_id):
    if load_chat(session_id) is None:
        return False

    _atomic_write_json(
        ACTIVE_SESSION_FILE,
        {"session_id": session_id},
    )
    return True


def get_active_session():
    try:
        with ACTIVE_SESSION_FILE.open("r", encoding="utf-8") as file:
            active = json.load(file)

        if not isinstance(active, dict):
            active = {}

        session_id = active.get("session_id")

        if (
            isinstance(session_id, str)
            and any(
                item.get("session_id") == session_id
                for item in load_index()
            )
            and load_chat(session_id) is not None
        ):
            return session_id

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        AttributeError,
    ):
        pass

    for item in reversed(load_index()):
        session_id = item.get("session_id")

        if load_chat(session_id) is not None:
            try:
                set_active_session(session_id)
            except OSError as error:
                print(f"WOS: Could not update active session: {error}")

            return session_id

    return None


def _index_entry(chat):
    entry = {
        "session_id": chat["session_id"],
        "title": chat["title"],
        "created": chat["created"],
        "updated": chat["updated"],
    }

    for key in ("provider", "model", "character_id"):
        if key in chat:
            entry[key] = chat[key]

    return entry


def _enforce_chat_limit(index, protected_session_id=None):
    while len(index) > MAX_CHATS:
        removable = next(
            (
                item for item in index
                if item.get("session_id") != protected_session_id
            ),
            None,
        )

        if removable is None:
            break

        delete_chat(removable["session_id"])
        index = load_index()

    return index


def create_chat(
    title=None,
    provider=None,
    model=None,
    character_id=None,
):
    index = load_index()
    session_id = get_next_session_id(index)
    timestamp = get_timestamp()

    if title is None:
        number = int(session_id.split("_")[1])
        title = f"Chat {number}"

    chat = {
        "session_id": session_id,
        "title": title,
        "created": timestamp,
        "updated": timestamp,
        "messages": [],
    }

    if provider is not None:
        chat["provider"] = provider
    if model is not None:
        chat["model"] = model
    if character_id is not None:
        chat["character_id"] = character_id

    save_chat(chat)
    index.append(_index_entry(chat))
    save_index(index)
    set_active_session(session_id)

    _enforce_chat_limit(index, protected_session_id=session_id)

    return chat


def update_chat(chat):
    chat["updated"] = get_timestamp()
    save_chat(chat)

    index = load_index()
    found = False

    for position, item in enumerate(index):
        if item.get("session_id") == chat["session_id"]:
            updated_entry = _index_entry(chat)

            for key in ("provider", "model", "character_id"):
                if key not in updated_entry and key in item:
                    updated_entry[key] = item[key]

            index[position] = updated_entry
            found = True
            break

    if not found:
        index.append(_index_entry(chat))

    save_index(index)


def delete_chat(session_id):
    chat_file = get_chat_file(session_id)
    index = load_index()

    if not any(
        item.get("session_id") == session_id for item in index
    ):
        return False

    if not chat_file.exists():
        return False

    chat_file.unlink()

    index = [
        item for item in index
        if item.get("session_id") != session_id
    ]
    save_index(index)

    try:
        active_session_id = get_active_session()
    except OSError as error:
        print(f"WOS: Could not check active session: {error}")
        active_session_id = None

    if active_session_id == session_id:
        if index:
            set_active_session(index[-1]["session_id"])
        else:
            try:
                ACTIVE_SESSION_FILE.unlink(missing_ok=True)
            except OSError as error:
                print(f"WOS: Could not clear active session: {error}")

    return True


def _load_old_conversation():
    if not OLD_CONVERSATION_FILE.exists():
        return []

    try:
        with OLD_CONVERSATION_FILE.open("r", encoding="utf-8") as file:
            messages = json.load(file)

        if not isinstance(messages, list):
            return []

        return [
            message for message in messages
            if isinstance(message, dict)
            and isinstance(message.get("role"), str)
            and isinstance(message.get("content"), str)
        ]

    except (json.JSONDecodeError, OSError) as error:
        print(f"WOS: Could not load previous conversation: {error}")
        return []


def initialize_active_chat(
    provider=None,
    model=None,
    character_id=None,
):
    active_id = get_active_session()

    if active_id is not None:
        chat = load_chat(active_id)

        if chat is not None:
            changed = False

            for key, value in (
                ("provider", provider),
                ("model", model),
                ("character_id", character_id),
            ):
                if key not in chat and value is not None:
                    chat[key] = value
                    changed = True

            if changed:
                update_chat(chat)

            return chat

    index = load_index()

    if not index:
        old_messages = _load_old_conversation()

        if old_messages:
            chat = create_chat(
                title="Previous Chat",
                provider=provider,
                model=model,
                character_id=character_id,
            )
            chat["messages"] = old_messages
            update_chat(chat)
            return chat

    return create_chat(
        provider=provider,
        model=model,
        character_id=character_id,
    )


def load_conversation(session_id=None):
    if session_id is not None:
        chat = load_chat(session_id)
        return chat.get("messages", []) if chat else []

    chat = initialize_active_chat()
    return chat.get("messages", [])


def save_conversation(messages, session_id=None):
    if session_id is None:
        session_id = get_active_session()

    chat = load_chat(session_id) if session_id else None

    if chat is None:
        chat = initialize_active_chat()

    chat["messages"] = messages
    update_chat(chat)
    set_active_session(chat["session_id"])