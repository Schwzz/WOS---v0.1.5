# WaifuOS (WOS)

A terminal-based AI companion. Chats and memories are saved locally in a `data/` folder, which WOS creates on first run.

## Requirements

- Python 3.8 or newer
- Packages: `requests`, `python-dotenv`, `google-genai`

```
pip install requests python-dotenv google-genai
```

All three are needed whichever provider you use, because both provider modules are loaded at startup.

## First-time setup

1. Install the packages above.
2. Choose a provider in `config.json` (`"cloud"` for Gemini or `"ollama"`). The default character is `nexis`.
3. Set up the provider you chose (see below).
4. Start WOS from this folder:

```
python start.py
```

Type `/help` to see all commands.

### Cloud provider (Gemini)

WOS reads your API key from a file named `.env` in this folder. The key is not included, and `.env.txt` is only a template.

1. Copy the template:
   - Windows: `copy .env.txt .env`
   - macOS / Linux: `cp .env.txt .env`
2. Open `.env` and replace `your_api_key_here` with your own Gemini API key.
3. Restart WOS. The key is read at startup.

Never share or commit `.env`. The included `.gitignore` excludes it.

### Ollama (local)

1. Install and start Ollama (WOS connects to `http://localhost:11434`).
2. Download a model, for example `ollama pull <model-name>`.
3. Before the first launch, set `"provider": "ollama"` and `"model": "<model-name>"` in `config.json`.

If you have already started WOS, each saved chat keeps its own provider and model. Use `/provider ollama` and `/model <model-name>` to change the current chat.

## Customization

- `config.json`: default provider, model, and character. You can also change the provider and model with `/defaults`.
- `settings.json`: terminal colors, number of saved chats, and context limits. Restart WOS after editing it.
- `characters/`: one JSON file per character. A character needs at least a `name` and a `personality` (see `characters/nexis.json` for a full example). Use `/character list` and `/character switch <id>` to change characters.
