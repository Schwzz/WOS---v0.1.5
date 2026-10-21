"""Discover provider models without putting credentials in URLs or errors."""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import requests

from core import config
from core.conversation import _atomic_write_json
from core.providers.ollama import list_installed_model_details, OllamaUnavailable

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
CACHE_SECONDS = 600


class ModelDiscoveryError(Exception):
    pass


def gemini_key():
    value = os.getenv("GEMINI_API_KEY", "").strip()
    return value if value and not value.lower().startswith("your_") else None


def list_gemini_models(get=None, api_key=None):
    """Fetch every page, retaining models that support generateContent."""
    key = api_key or gemini_key()
    if not key:
        raise ModelDiscoveryError("Set GEMINI_API_KEY in .env and restart WOS to discover models.")
    get = get or requests.get
    found, seen, page = {}, set(), None
    for _ in range(100):
        params = {"pageSize": 1000}
        if page:
            params["pageToken"] = page
        try:
            response = get(MODELS_URL, headers={"x-goog-api-key": key},
                           params=params, timeout=(3, 10))
            status = response.status_code
            if status != 200:
                reason = {401: "API key rejected", 403: "API key rejected or access denied",
                          429: "model discovery rate limited"}.get(status, "model discovery failed")
                raise ModelDiscoveryError(f"Gemini: {reason} (HTTP {status}).")
            data = response.json()
        except ModelDiscoveryError:
            raise
        except Exception as error:
            raise ModelDiscoveryError(f"Gemini model discovery failed ({type(error).__name__}).") from None
        if not isinstance(data, dict) or not isinstance(data.get("models", []), list):
            raise ModelDiscoveryError("Gemini returned an invalid model list.")
        for model in data.get("models", []):
            if not isinstance(model, dict):
                continue
            actions = model.get("supportedGenerationMethods")
            if not isinstance(actions, list) or "generateContent" not in actions:
                continue
            try:
                name = model.get("name", "")
                if isinstance(name, str) and name.startswith("models/"):
                    name = name[7:]
                name = config.validate_model_name(name)
            except (ValueError, AttributeError):
                continue
            label = model.get("displayName")
            found[name] = {"id": name, "label": label if isinstance(label, str) else name}
        page = data.get("nextPageToken")
        if not page:
            return sorted(found.values(), key=lambda item: item["id"])
        if not isinstance(page, str) or page in seen:
            raise ModelDiscoveryError("Gemini returned an invalid pagination token.")
        seen.add(page)
    raise ModelDiscoveryError("Gemini returned too many model pages.")


class ModelCatalog:
    def __init__(self, cache_path=None):
        self.path = Path(cache_path) if cache_path else config.PROJECT_ROOT / "data" / "model_catalog.json"
        self._lock = threading.Lock()

    def list(self, provider, known=(), refresh=False):
        with self._lock:
            return self._list(provider, known, refresh)

    def _list(self, provider, known, refresh):
        fallback = [{"id": name, "label": name} for name in dict.fromkeys(known)]
        if provider == "ollama":
            try:
                models = [{"id": name, "label": name, "size": size}
                          for name, size in list_installed_model_details()]
                return {"models": models, "source": "live", "warning": None}
            except OllamaUnavailable as error:
                return {"models": fallback, "source": "saved", "warning": str(error)}
        key = gemini_key()
        fingerprint = hashlib.sha256(key.encode()).hexdigest() if key else None
        cached = None
        try:
            record = json.loads(self.path.read_text("utf-8"))
            if fingerprint and record.get("key_hash") == fingerprint:
                cached = record
                if not isinstance(cached.get("models"), list) or any(
                    not isinstance(m, dict) or not isinstance(m.get("id"), str)
                    or not isinstance(m.get("label"), str) for m in cached["models"]
                ):
                    cached = None
        except (OSError, ValueError, AttributeError):
            pass
        if cached and not refresh and isinstance(cached.get("at"), (int, float)) and 0 <= time.time() - cached["at"] < CACHE_SECONDS:
            return {"models": cached["models"], "source": "cached", "warning": None}
        try:
            models = list_gemini_models(api_key=key)
            try:
                _atomic_write_json(self.path, {"key_hash": fingerprint, "at": time.time(), "models": models})
            except OSError:
                pass  # Discovery still works when the cache cannot be saved.
            return {"models": models, "source": "live", "warning": None}
        except ModelDiscoveryError as error:
            return {"models": cached["models"] if cached else fallback,
                    "source": "cached" if cached else "saved", "warning": str(error)}
