import json
import os
from datetime import datetime


CHATS_DIR = "data/chats"
INDEX_FILE = os.path.join(CHATS_DIR, "index.json")
OLD_CONVERSATION_FILE = "data/conversation.json"


def get_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def ensure_chat_directory():
    os.makedirs(CHATS_DIR, exist_ok=True)


def load_index():
    ensure_chat_directory()

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as file:
            index = json.load(file)

            if not isinstance(index, list):
                return []

            return index

    except FileNotFoundError:
        return []

    except json.JSONDecodeError:
        return []


def save_index(index):
    ensure_chat_directory()

    with open(INDEX_FILE, "w", encoding="utf-8") as file:
        json.dump(index, file, indent=4, ensure_ascii=False)


def get_next_session_id(index):
    if not index:
        return "session_001"

    numbers = []

    for chat in index:
        session_id = chat.get("session_id", "")

        if session_id.startswith("session_"):
            try:
                numbers.append(int(session_id.split("_")[1]))
            except (IndexError, ValueError):
                pass

    next_number = max(numbers, default=0) + 1

    return f"session_{next_number:03d}"


def get_chat_file(session_id):
    return os.path.join(
        CHATS_DIR,
        f"{session_id}.json"
    )


def load_chat(session_id):
    chat_file = get_chat_file(session_id)

    try:
        with open(chat_file, "r", encoding="utf-8") as file:
            chat = json.load(file)

            if not isinstance(chat, dict):
                return None

            return chat

    except FileNotFoundError:
        return None

    except json.JSONDecodeError:
        return None


def save_chat(chat):
    ensure_chat_directory()

    session_id = chat["session_id"]
    chat_file = get_chat_file(session_id)

    with open(chat_file, "w", encoding="utf-8") as file:
        json.dump(chat, file, indent=4, ensure_ascii=False)


def create_chat(title=None):
    index = load_index()

    session_id = get_next_session_id(index)
    timestamp = get_timestamp()

    if title is None:
        title = f"Chat {len(index) + 1}"

    chat = {
        "session_id": session_id,
        "title": title,
        "created": timestamp,
        "updated": timestamp,
        "messages": []
    }

    save_chat(chat)

    index.append({
        "session_id": session_id,
        "title": title,
        "created": timestamp,
        "updated": timestamp
    })

    save_index(index)

    return chat


def update_chat(chat):
    chat["updated"] = get_timestamp()

    save_chat(chat)

    index = load_index()

    for item in index:
        if item.get("session_id") == chat["session_id"]:
            item["title"] = chat["title"]
            item["updated"] = chat["updated"]
            break

    save_index(index)


def delete_chat(session_id):
    index = load_index()

    chat_file = get_chat_file(session_id)

    if os.path.exists(chat_file):
        os.remove(chat_file)

    index = [
        item
        for item in index
        if item.get("session_id") != session_id
    ]

    save_index(index)


def load_conversation(session_id=None):
    """
    Temporary compatibility function.

    If a session ID is supplied, load that session.

    If no session exists yet, migrate the old conversation.json
    into the first chat session.
    """

    if session_id is not None:
        chat = load_chat(session_id)

        if chat is None:
            return []

        return chat.get("messages", [])

    index = load_index()

    if index:
        latest = index[-1]
        chat = load_chat(latest["session_id"])

        if chat:
            return chat.get("messages", [])

    if not os.path.exists(OLD_CONVERSATION_FILE):
        return []

    try:
        with open(
            OLD_CONVERSATION_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            old_conversation = json.load(file)

            if not isinstance(old_conversation, list):
                return []

    except (json.JSONDecodeError, OSError):
        return []

    if not old_conversation:
        return []

    chat = create_chat("Previous Chat")
    chat["messages"] = old_conversation

    update_chat(chat)

    return old_conversation


def save_conversation(messages, session_id=None):
    """
    Temporary compatibility function.

    Saves messages into the supplied session.
    """

    if session_id is None:
        index = load_index()

        if index:
            session_id = index[-1]["session_id"]
        else:
            chat = create_chat()
            session_id = chat["session_id"]

    chat = load_chat(session_id)

    if chat is None:
        chat = create_chat()

        chat["session_id"] = session_id

    chat["messages"] = messages

    update_chat(chat)