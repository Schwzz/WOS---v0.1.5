import json


def load_character(character_id):
    try:
        with open(
            f"characters/{character_id}.json",
            "r",
            encoding="utf-8"
        ) as file:
            character = json.load(file)

    except FileNotFoundError:
        print(f"WLLM: Character '{character_id}' was not found.")
        exit()

    except json.JSONDecodeError:
        print(f"WLLM: Character '{character_id}' contains invalid JSON.")
        exit()

    if not isinstance(character, dict):
        print(f"WLLM: Character '{character_id}' must contain a JSON object.")
        exit()

    if not character.get("name"):
        print(f"WLLM: Character '{character_id}' is missing a name.")
        exit()

    if not character.get("personality"):
        print(f"WLLM: Character '{character_id}' is missing a personality.")
        exit()

    return character