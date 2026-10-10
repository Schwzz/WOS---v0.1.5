
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = PROJECT_ROOT / "characters"


def load_character(character_id):
    character_path = CHARACTERS_DIR / f"{character_id}.json"

    try:
        with character_path.open("r", encoding="utf-8") as file:
            character = json.load(file)

    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"WLLM: Character '{character_id}' was not found at "
            f"{character_path}."
        ) from error

    except json.JSONDecodeError as error:
        raise ValueError(
            f"WLLM: Character '{character_id}' contains invalid JSON "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    if not isinstance(character, dict):
        raise ValueError(
            f"WLLM: Character '{character_id}' must contain a JSON object."
        )

    if not character.get("name"):
        raise ValueError(
            f"WLLM: Character '{character_id}' is missing a name."
        )

    if not character.get("personality"):
        raise ValueError(
            f"WLLM: Character '{character_id}' is missing a personality."
        )

    return character