import json
import os
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

SUPPORTED_PROVIDERS = {"cloud", "ollama"}


def load_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Configuration file was not found: {CONFIG_PATH}"
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            f"config.json contains invalid JSON "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    if not isinstance(config, dict):
        raise ValueError("config.json must contain a JSON object.")

    provider = config.get("provider")
    model = config.get("model")
    character = config.get("character")

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )

    if not isinstance(model, str) or not model.strip():
        raise ValueError("The configured model must be a non-empty string.")

    if not isinstance(character, str) or not character.strip():
        raise ValueError("The configured character must be a non-empty string.")

    return config


def save_config(config):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary.")

    provider = config.get("provider")
    model = config.get("model")
    character = config.get("character")

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )

    if not isinstance(model, str) or not model.strip():
        raise ValueError("The configured model must be a non-empty string.")

    if not isinstance(character, str) or not character.strip():
        raise ValueError("The configured character must be a non-empty string.")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_PATH.parent,
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(config, file, indent=4)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, CONFIG_PATH)

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


SETTINGS_PATH = PROJECT_ROOT / "settings.json"

DEFAULT_SETTINGS = {
    "terminal": {
        "default_name_color": "white"
    },
    "sessions": {
        "max_chats": 5
    },
    "context": {
        "max_context_messages": 20,
        "max_historical_chats": 4,
        "max_history_chars": 10000
    }
}


def load_settings():
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as file:
            saved_settings = json.load(file)
    except FileNotFoundError:
        save_settings(settings)
        return settings
    except json.JSONDecodeError as error:
        raise ValueError(
            f"settings.json contains invalid JSON "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    if not isinstance(saved_settings, dict):
        raise ValueError("settings.json must contain a JSON object.")

    for section, values in DEFAULT_SETTINGS.items():
        saved_section = saved_settings.get(section, {})

        if not isinstance(saved_section, dict):
            raise ValueError(
                f"The '{section}' setting must be a JSON object."
            )

        settings[section].update(saved_section)

    color = settings["terminal"]["default_name_color"]
    if color not in {
        "white", "cyan", "green", "magenta",
        "blue", "yellow", "red"
    }:
        raise ValueError(
            f"Unsupported default terminal color: {color}"
        )

    for key in (
        "max_chats",
    ):
        value = settings["sessions"][key]
        if type(value) is not int or value < 1:
            raise ValueError(f"sessions.{key} must be a positive integer.")

    for key in (
        "max_context_messages",
        "max_historical_chats",
        "max_history_chars",
    ):
        value = settings["context"][key]
        if type(value) is not int or value < 1:
            raise ValueError(f"context.{key} must be a positive integer.")

    return settings


def save_settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary.")

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=SETTINGS_PATH.parent,
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(settings, file, indent=4)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, SETTINGS_PATH)

    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
