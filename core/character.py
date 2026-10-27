
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = PROJECT_ROOT / "characters"

CHARACTER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

SUPPORTED_TERMINAL_COLORS = {
    "white",
    "cyan",
    "green",
    "magenta",
    "blue",
    "yellow",
    "red",
}


def validate_character_id(character_id):
    if not isinstance(character_id, str):
        raise ValueError("Auralis: Character ID must be a string.")

    if not CHARACTER_ID_PATTERN.fullmatch(character_id):
        raise ValueError(
            f"Auralis: Invalid character ID '{character_id}'. "
            "Use only letters, numbers, underscores, and hyphens."
        )


def validate_character(character_id, character):
    if not isinstance(character, dict):
        raise ValueError(
            f"Auralis: Character '{character_id}' must contain a JSON object."
        )

    name = character.get("name")
    personality = character.get("personality")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"Auralis: Character '{character_id}' must have a "
            "non-empty string for 'name'."
        )

    if isinstance(personality, str):
        if not personality.strip():
            raise ValueError(
                f"Auralis: Character '{character_id}' must have a "
                "non-empty string or object for 'personality'."
            )

    elif isinstance(personality, dict):
        core = personality.get("core")

        if not isinstance(core, str) or not core.strip():
            raise ValueError(
                f"Auralis: Character '{character_id}' must have a "
                "non-empty string for 'personality.core'."
            )

    else:
        raise ValueError(
            f"Auralis: Character '{character_id}' must have a "
            "non-empty string or object for 'personality'."
        )

    for field in (
        "metadata",
        "identity",
        "behavior",
        "appearance",
        "preferences",
        "terminal",
    ):
        value = character.get(field)

        if value is not None and not isinstance(value, dict):
            raise ValueError(
                f"Auralis: Character '{character_id}' field '{field}' "
                "must be a JSON object."
            )

    terminal = character.get("terminal", {})
    name_color = terminal.get("name_color", "magenta")

    if (
        not isinstance(name_color, str)
        or name_color.lower() not in SUPPORTED_TERMINAL_COLORS
    ):
        supported = ", ".join(sorted(SUPPORTED_TERMINAL_COLORS))
        raise ValueError(
            f"Auralis: Character '{character_id}' has an unsupported "
            f"terminal name color. Choose from: {supported}."
        )

    if "greeting" in character:
        greeting = character["greeting"]

        if not isinstance(greeting, str):
            raise ValueError(
                f"Auralis: Character '{character_id}' field 'greeting' "
                "must be a string."
            )

    return character


def load_character(character_id):
    validate_character_id(character_id)

    character_path = CHARACTERS_DIR / f"{character_id}.json"

    try:
        # utf-8-sig also accepts files saved with a BOM (some Windows editors).
        with character_path.open("r", encoding="utf-8-sig") as file:
            character = json.load(file)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"Auralis: Character '{character_id}' was not found."
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Auralis: Character '{character_id}' contains invalid JSON "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    return validate_character(character_id, character)


def list_characters():
    characters = []

    if not CHARACTERS_DIR.is_dir():
        return characters

    for character_path in sorted(CHARACTERS_DIR.glob("*.json")):
        character_id = character_path.stem

        try:
            character = load_character(character_id)
        except (OSError, ValueError):
            continue

        characters.append({
            "id": character_id,
            "name": character["name"],
        })

    return characters


def list_skipped_characters():
    """Explain why files in the characters folder cannot be used.

    Returns (file name, reason) pairs, sorted by file name. A file is only
    reported if it looks like a character file: it is a .json file that fails
    to load, or its name contains ".json" but does not end with it (such as
    "aria.json.txt"). Other files, such as Thumbs.db or notes, are ignored.
    """
    skipped = []

    if not CHARACTERS_DIR.is_dir():
        return skipped

    json_files = set(CHARACTERS_DIR.glob("*.json"))

    for path in sorted(CHARACTERS_DIR.iterdir()):
        name = path.name

        if name.startswith(".") or not path.is_file():
            continue

        if path not in json_files:
            if ".json" in name.lower():
                skipped.append((name, (
                    "not a .json file - rename it so the name ends with "
                    ".json (Windows can hide the real ending)."
                )))

            continue

        character_id = path.stem

        if not CHARACTER_ID_PATTERN.fullmatch(character_id):
            skipped.append((name, (
                "invalid file name - use only letters, numbers, "
                "underscores, and hyphens before .json."
            )))
            continue

        try:
            load_character(character_id)

        except UnicodeDecodeError:
            reason = (
                "not saved as UTF-8 text - save the file again as UTF-8."
            )

        except (OSError, ValueError) as error:
            reason = _skip_reason(error, character_id)

        else:
            continue

        skipped.append((name, reason))

    return skipped


def _skip_reason(error, character_id):
    """Turn a load error into a short reason that follows the file name."""
    if isinstance(error, OSError):
        return f"could not be read ({error.strerror or error})."

    message = str(error)

    if message.startswith("Auralis: "):
        message = message[len("Auralis: "):]

    prefix = f"Character '{character_id}' "

    if message.startswith(prefix):
        message = message[len(prefix):]

    return message
