from core.providers.ollama import chat as ollama_chat
from core.providers.cloud import chat as cloud_chat


def chat(provider, model, messages):
    if not isinstance(provider, str):
        print("WLLM: Provider name must be a string.")
        return None

    provider = provider.strip().lower()

    try:
        if provider == "ollama":
            return ollama_chat(model, messages)

        if provider == "cloud":
            return cloud_chat(model, messages)

        print(f"WLLM: Unknown provider '{provider}'.")
        return None

    except Exception as error:
        print(
            f"WLLM: Unexpected error from provider "
            f"'{provider}': {error}"
        )
        return None