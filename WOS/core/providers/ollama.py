import requests


OLLAMA_URL = "http://localhost:11434/api/chat"


def chat(model, messages):
    if not isinstance(model, str) or not model.strip():
        print("WLLM: The Ollama model name cannot be empty.")
        return None

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model.strip(),
                "messages": messages,
                "stream": False,
            },
            timeout=120,
        )

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            print("WLLM: Ollama returned an invalid response.")
            return None

        message = data.get("message")

        if not isinstance(message, dict):
            print("WLLM: Ollama response is missing its message.")
            return None

        reply = message.get("content")

        if not isinstance(reply, str) or not reply.strip():
            print("WLLM: Ollama returned an empty response.")
            return None

        return reply.strip()

    except requests.exceptions.ConnectionError:
        print("WLLM: Could not connect to Ollama. Is Ollama running?")
        return None

    except requests.exceptions.Timeout:
        print("WLLM: The model took too long to respond.")
        return None

    except requests.exceptions.RequestException as error:
        print(f"WLLM: Ollama returned an error: {error}")
        return None

    except (ValueError, TypeError, KeyError) as error:
        print(f"WLLM: Ollama returned an invalid response: {error}")
        return None

    except Exception as error:
        print(f"WLLM: An unexpected Ollama error occurred: {error}")
        return None