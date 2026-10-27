"""Choosing and checking models for /provider and /model.

This module only works on plain data. It never talks to Ollama or the
network itself, so it is easy to test. start.py fetches the installed
models and passes them in.
"""
import difflib


OTHER_LABEL = "Other (type a model name)"

# How many installed models to list inside an error message.
_MAX_LISTED = 5


def normalize_ollama_name(name):
    """Ollama treats 'llama3' and 'llama3:latest' as the same model."""
    name = (name or "").strip()

    if name.endswith(":latest"):
        name = name[: -len(":latest")]

    return name


def is_installed(model, installed):
    wanted = normalize_ollama_name(model)

    return any(normalize_ollama_name(name) == wanted for name in installed)


def check_ollama_model(model, installed):
    """Return a clear problem message if the model is not among the installed
    Ollama models, or None if it is installed.

    `installed` is the list of installed names, or None when Ollama could not
    be asked. In that case nothing can be checked, so there is no problem to
    report here.
    """
    if installed is None or is_installed(model, installed):
        return None

    message = f"Model '{model}' is not installed in Ollama."

    # Compare without ":latest" so a near miss like "lama3" still finds
    # "llama3:latest", but suggest the full installed name.
    by_short_name = {normalize_ollama_name(name): name for name in installed}
    close = difflib.get_close_matches(
        normalize_ollama_name(model), list(by_short_name), n=1, cutoff=0.6
    )

    if close:
        message += f" Did you mean '{by_short_name[close[0]]}'?"

    if installed:
        shown = ", ".join(installed[:_MAX_LISTED])
        extra = len(installed) - _MAX_LISTED

        if extra > 0:
            shown += f", and {extra} more"

        message += f" Installed models: {shown}."
    else:
        message += " No models are installed yet."

    return message + f" To install it, run: ollama pull {model}"


def menu_models(provider, installed, known):
    """The model names to offer in a menu.

    For Ollama, the models really installed on this computer, if they could
    be fetched. Otherwise (and for every other provider) the model names Auralis
    already knows about.
    """
    if provider == "ollama" and installed is not None:
        return list(installed)

    return list(known)


def format_size(num_bytes):
    """A model size as people read it, for example '4.7 GB'. Returns None if
    the size is not known."""
    if isinstance(num_bytes, bool) or not isinstance(num_bytes, int):
        return None

    if num_bytes < 0:
        return None

    size = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB"):
        if size < 1000:
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"

        size /= 1000

    return f"{size:.1f} TB"


def label_model(model, provider, current_provider, current_model,
                default_provider, default_model, size_bytes=None):
    """The text shown for one model in a menu."""
    def same(a, b):
        if provider == "ollama":
            return normalize_ollama_name(a) == normalize_ollama_name(b)

        return a == b

    notes = []

    if provider == current_provider and same(model, current_model):
        notes.append("current")

    if provider == default_provider and same(model, default_model):
        notes.append("default for new chats")

    size = format_size(size_bytes)
    name = f"{model} - {size}" if size else model

    return f"{name} ({', '.join(notes)})" if notes else name
