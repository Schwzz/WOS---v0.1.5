"""Shared helpers for the WOS tests.

The tests use only the standard library. Every file WOS reads or writes is
redirected into a temporary folder, so your real config.json, characters and
saved chats are never touched, and no API key or network is needed.
"""
import json
import shutil
import sys
import tempfile
import types as pytypes
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_google_stub_if_needed():
    """Provide a fake google.genai when the real package is not installed,
    so the provider modules can be imported without it."""
    try:
        from google import genai  # noqa: F401
        from google.genai import types  # noqa: F401
        return
    except ImportError:
        pass

    google = pytypes.ModuleType("google")
    google.__path__ = []
    genai = pytypes.ModuleType("google.genai")
    genai.__path__ = []
    genai.Client = object
    genai_types = pytypes.ModuleType("google.genai.types")

    google.genai = genai
    genai.types = genai_types

    sys.modules["google"] = google
    sys.modules["google.genai"] = genai
    sys.modules["google.genai.types"] = genai_types


_install_google_stub_if_needed()

from core import character, config, conversation, memory  # noqa: E402

DEFAULT_CONFIG = {
    "provider": "cloud",
    "model": "gemini-3.5-flash-lite",
    "character": "nexis",
}

DEFAULT_SETTINGS = {
    "user_name": "",
    "terminal": {"default_name_color": "cyan"},
    "sessions": {"max_chats": 5},
    "context": {
        "max_context_messages": 20,
        "max_historical_chats": 4,
        "max_history_chars": 10000,
    },
}


class Sandbox:
    """A temporary WOS project folder with all module paths redirected to it."""

    def __init__(self, max_chats=5, config_data=None):
        self.max_chats = max_chats
        self.config_data = dict(config_data or DEFAULT_CONFIG)

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

        self.characters_dir = self.root / "characters"
        self.characters_dir.mkdir()
        shutil.copy(
            PROJECT_ROOT / "characters" / "nexis.json",
            self.characters_dir / "nexis.json",
        )

        second = json.loads(
            (PROJECT_ROOT / "characters" / "nexis.json").read_text("utf-8")
        )
        second["id"] = "tester"
        second["name"] = "Tester"
        (self.characters_dir / "tester.json").write_text(
            json.dumps(second), encoding="utf-8"
        )

        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(self.config_data, indent=4) + "\n", encoding="utf-8"
        )

        self.settings_path = self.root / "settings.json"
        self.settings_path.write_text(
            json.dumps(DEFAULT_SETTINGS), encoding="utf-8"
        )

        self.data_dir = self.root / "data"
        self.chats_dir = self.data_dir / "chats"

        self._stack = ExitStack()
        patch = self._stack.enter_context
        patch(mock.patch.object(config, "CONFIG_PATH", self.config_path))
        patch(mock.patch.object(config, "SETTINGS_PATH", self.settings_path))
        patch(mock.patch.object(character, "CHARACTERS_DIR", self.characters_dir))
        patch(mock.patch.object(conversation, "DATA_DIR", self.data_dir))
        patch(mock.patch.object(conversation, "CHATS_DIR", self.chats_dir))
        patch(mock.patch.object(
            conversation, "INDEX_FILE", self.chats_dir / "index.json"
        ))
        patch(mock.patch.object(
            conversation, "ACTIVE_SESSION_FILE",
            self.chats_dir / "active_session.json",
        ))
        patch(mock.patch.object(
            conversation, "OLD_CONVERSATION_FILE",
            self.data_dir / "conversation.json",
        ))
        patch(mock.patch.object(conversation, "MAX_CHATS", self.max_chats))
        patch(mock.patch.object(
            memory, "MEMORY_PATH", self.data_dir / "memory.json"
        ))
        patch(mock.patch.object(memory, "_MEMORY_FILE_INVALID", False))

        return self

    def __exit__(self, *exc_info):
        self._stack.close()
        self._tmp.cleanup()
        return False

    def read_config(self):
        return json.loads(self.config_path.read_text("utf-8"))

    def read_chat(self, session_id):
        path = self.chats_dir / f"{session_id}.json"
        return json.loads(path.read_text("utf-8"))

    def chat_files(self):
        return sorted(p.name for p in self.chats_dir.glob("session_*.json"))

    def make_session(self):
        from core.session import Session

        return Session()
