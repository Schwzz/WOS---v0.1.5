from core.providers.ollama import chat as ollama_chat
from core.providers.cloud import chat as cloud_chat


def chat(provider, model, messages):
    if provider == "ollama":
        return ollama_chat(model, messages)

    if provider == "cloud":
        return cloud_chat(model, messages)

    print(f"WLLM: Unknown provider '{provider}'.")
    return None