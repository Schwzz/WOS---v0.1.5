import requests


OLLAMA_URL = "http://localhost:11434/api/chat"

# Ollama lists the models installed on this computer here.
OLLAMA_TAGS_URL = OLLAMA_URL.rsplit("/api/", 1)[0] + "/api/tags"


class OllamaUnavailable(Exception):
    """Ollama could not be reached or did not give a usable answer."""


def list_installed_model_details(url=None, timeout=3):
    """Return (name, size_in_bytes) pairs for the models installed in Ollama,
    sorted by name. The size is None when Ollama does not report one.

    Raises OllamaUnavailable, with a message that is safe to show the user,
    if Ollama is not running or answers with something unexpected.
    """
    url = url or OLLAMA_TAGS_URL

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.ConnectionError:
        raise OllamaUnavailable("Ollama is not running.")

    except requests.exceptions.Timeout:
        raise OllamaUnavailable("Ollama took too long to answer.")

    except ValueError:
        # Must come before RequestException: in current versions of requests,
        # a body that is not JSON raises an error that is both.
        raise OllamaUnavailable("Ollama sent an answer Auralis could not read.")

    except requests.exceptions.RequestException as error:
        raise OllamaUnavailable(f"Ollama returned an error: {error}")

    models = data.get("models") if isinstance(data, dict) else None

    if not isinstance(models, list):
        raise OllamaUnavailable("Ollama sent an answer Auralis could not read.")

    names = {}

    for item in models:
        if not isinstance(item, dict):
            continue

        name = item.get("name") or item.get("model")

        if isinstance(name, str) and name.strip():
            size = item.get("size")

            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                size = None

            names.setdefault(name.strip(), size)

    return sorted(names.items(), key=lambda pair: pair[0].lower())


def list_installed_models(url=None, timeout=3):
    """Return the names of the models installed in Ollama, sorted.

    Raises OllamaUnavailable in the same cases as
    list_installed_model_details().
    """
    return [name for name, _ in list_installed_model_details(url, timeout)]


def chat(model, messages):
    if not isinstance(model, str) or not model.strip():
        print("Auralis: The Ollama model name cannot be empty.")
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
            print("Auralis: Ollama returned an invalid response.")
            return None

        message = data.get("message")

        if not isinstance(message, dict):
            print("Auralis: Ollama response is missing its message.")
            return None

        reply = message.get("content")

        if not isinstance(reply, str) or not reply.strip():
            print("Auralis: Ollama returned an empty response.")
            return None

        return reply.strip()

    except requests.exceptions.ConnectionError:
        print("Auralis: Could not connect to Ollama. Is Ollama running?")
        return None

    except requests.exceptions.Timeout:
        print("Auralis: The model took too long to respond.")
        return None

    except requests.exceptions.RequestException as error:
        print(f"Auralis: Ollama returned an error: {error}")
        return None

    except (ValueError, TypeError, KeyError) as error:
        print(f"Auralis: Ollama returned an invalid response: {error}")
        return None

    except Exception as error:
        print(f"Auralis: An unexpected Ollama error occurred: {error}")
        return None