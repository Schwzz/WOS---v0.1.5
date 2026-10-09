import json


def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as file:
            config = json.load(file)

            if not isinstance(config, dict):
                print("WLLM: config.json must contain an object.")
                exit()

            return config

    except FileNotFoundError:
        print("WLLM: config.json was not found.")
        exit()

    except json.JSONDecodeError:
        print("WLLM: config.json contains invalid JSON.")
        exit()