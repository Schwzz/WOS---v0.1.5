import requests


OLLAMA_URL = "http://localhost:11434/api/chat"


def chat(model, messages):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": messages,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()
        return data["message"]["content"]

    except requests.exceptions.ConnectionError:
        print("WLLM: Could not connect to Ollama. Is Ollama running?")
        return None

    except requests.exceptions.Timeout:
        print("WLLM: The model took too long to respond.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"WLLM: Ollama returned an error: {e}")
        return None

    except (KeyError, ValueError):
        print("WLLM: I received an invalid response from Ollama.")
        return None