
import builtins
import ctypes
import os
import sys

from core.session import Session
from core.character import list_characters, load_character
from core.memory import (
    show_memory,
    edit_memory,
    forget_memory,
    clear_memory,
)
from core.conversation import (
    load_index,
    load_chat,
    update_chat,
    delete_chat,
)
from core.config import SUPPORTED_PROVIDERS, load_settings


# ------------------------------
# Terminal colors
# ------------------------------

RESET = "\033[0m"
WHITE = "\033[97m"
CYAN = "\033[96m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[90m"

CHARACTER_COLORS = {
    "white": WHITE,
    "cyan": CYAN,
    "green": GREEN,
    "magenta": MAGENTA,
    "blue": BLUE,
    "yellow": YELLOW,
    "red": RED,
}

COLORS_ENABLED = False


def enable_terminal_colors():
    """Enable ANSI colors on supported Windows terminals."""
    global COLORS_ENABLED

    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            stdout_handle = kernel32.GetStdHandle(-11)

            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(
                stdout_handle,
                ctypes.byref(mode),
            ):
                ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                if kernel32.SetConsoleMode(
                    stdout_handle,
                    mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
                ):
                    COLORS_ENABLED = True
        except (AttributeError, OSError):
            COLORS_ENABLED = False
    else:
        COLORS_ENABLED = sys.stdout.isatty()


def get_default_name_color():
    """Get the default character-name color from settings.json."""
    try:
        settings = load_settings()
        color_name = (
            settings.get("terminal", {})
            .get("default_name_color", "white")
        )

        if isinstance(color_name, str):
            return CHARACTER_COLORS.get(
                color_name.lower(),
                WHITE,
            )

    except (OSError, ValueError, AttributeError, TypeError):
        pass

    return WHITE


def get_character_name_color():
    """Prefer the active character's color, then the global default."""
    default_color = get_default_name_color()
    active_session = globals().get("session")

    if active_session is None:
        return default_color

    character_id = getattr(active_session, "character_id", None)

    if not character_id:
        return default_color

    try:
        character = load_character(character_id)
        terminal = character.get("terminal", {})
        color_name = terminal.get("name_color")

        if isinstance(color_name, str):
            color = CHARACTER_COLORS.get(color_name.lower())

            if color:
                return color

    except (OSError, ValueError, AttributeError, TypeError):
        pass

    return default_color


def color_for_line(line):
    """Choose colors for WOS output."""
    stripped = line.strip()
    lowered = stripped.lower()

    if not stripped:
        return None

    error_phrases = (
        "error:",
        "failed",
        "could not",
        "couldn't",
        "not found",
        "did not return",
        "unsupported provider",
        "unknown provider",
        "invalid ",
    )

    if stripped.startswith("You:"):
        return GREEN

    active_session = globals().get("session")
    character_name = getattr(active_session, "character_name", "Nexis")

    if stripped.startswith(f"{character_name}:"):
        return "CHARACTER"

    if stripped.startswith("WLLM:"):
        return YELLOW

    if stripped.startswith("WOS:"):
        return (
            RED
            if any(phrase in lowered for phrase in error_phrases)
            else BLUE
        )

    if any(phrase in lowered for phrase in error_phrases):
        return RED

    if (
        stripped == "WOS"
        or stripped.startswith("===")
        or stripped.startswith("---")
        or stripped in (
            "Saved Chats",
            "WOS commands:",
            "Memory phrases:",
            "WOS Status",
            "WOS Context",
            "WOS Default Settings",
            "Available Characters",
        )
    ):
        return CYAN

    if stripped.startswith((
        "Character:",
        "Provider:",
        "Model:",
        "Memory:",
        "Session:",
        "Saved messages:",
        "Messages in context:",
        "Context limit:",
        "Saved chats:",
        "Saved memories:",
        "Default provider:",
        "Default model:",
        "Default character:",
    )):
        return DIM

    return None


def print(*values, sep=" ", end="\n", file=None, flush=False):
    """Color WOS output while preserving normal print behavior."""
    destination = file if file is not None else sys.stdout
    text = sep.join(str(value) for value in values)

    if not COLORS_ENABLED or destination is not sys.stdout:
        builtins.print(
            text,
            end=end,
            file=destination,
            flush=flush,
        )
        return

    lines = text.split("\n")
    colored_lines = []

    active_session = globals().get("session")
    character_name = getattr(active_session, "character_name", "Nexis")
    character_prefix = f"{character_name}:"

    # Detect a character response that spans multiple lines.
    is_character_response = (
        bool(lines)
        and lines[0].lstrip().startswith(character_prefix)
    )

    for index, line in enumerate(lines):
        if is_character_response:
            if index == 0:
                position = line.find(character_prefix)

                if position >= 0:
                    prefix_end = position + len(character_prefix)
                    prefix = line[position:prefix_end]
                    response = line[prefix_end:]
                    name_color = get_character_name_color()

                    colored_lines.append(
                        f"{line[:position]}"
                        f"{name_color}{prefix}{RESET}"
                        f"{WHITE}{response}{RESET}"
                    )
                else:
                    colored_lines.append(f"{WHITE}{line}{RESET}")
            else:
                colored_lines.append(f"{WHITE}{line}{RESET}")

            continue

        color = color_for_line(line)

        if color:
            colored_lines.append(f"{color}{line}{RESET}")
        else:
            colored_lines.append(line)

    builtins.print(
        "\n".join(colored_lines),
        end=end,
        file=destination,
        flush=flush,
    )


def input(prompt=""):
    """Color interactive prompts."""
    if not COLORS_ENABLED:
        return builtins.input(prompt)

    color = GREEN if prompt.startswith("You:") else BLUE

    sys.stdout.write(f"{color}{prompt}")
    sys.stdout.flush()

    try:
        result = builtins.input()
    finally:
        sys.stdout.write(RESET)
        sys.stdout.flush()

    return result


enable_terminal_colors()


# ------------------------------
# Help
# ------------------------------

def show_help():
    print()
    print("WOS commands:")
    print("/new                         Start a new chat")
    print("/chats                       List saved chats")
    print("/switch <id>                 Switch to a saved chat")
    print("/rename <id> <name>          Rename a saved chat")
    print("/delete <id>                 Delete a saved chat")
    print("/clear                       Clear the current conversation")
    print("/character                   Show the active character")
    print("/character list              List available characters")
    print("/character switch <id>       Switch the current chat's character")
    print("/provider                    Show or change the provider")
    print("/model                       Show or change the model")
    print("/defaults                    Show default provider/model")
    print("/defaults provider <name>    Change default provider")
    print("/defaults model <name>       Change default model")
    print("/memory                      Show saved memories")
    print("/memory edit <key> <value>   Edit a saved memory")
    print("/memory delete <key>         Delete a saved memory")
    print("/memory clear                Clear all saved memories")
    print("/forget <memory>             Forget a saved memory")
    print("/context                     Show current context usage")
    print("/status                      Show current WOS status")
    print("/restart                     Restart WOS")
    print("/help                        Show available commands")
    print("/exit                        Close WOS")
    print()
    print("Memory phrases:")
    print("Remember that ...")
    print("Keep in mind that ...")
    print("Don't forget that ...")
    print("Forget that ...")
    print("Forget about ...")
    print()


# ------------------------------
# Initialize WOS
# ------------------------------

try:
    session = Session()
except (ValueError, FileNotFoundError, KeyError) as error:
    print(f"WOS: Could not start: {error}")
    raise SystemExit(1)


def show_header():
    print()
    print("==============================")
    print("             WOS")
    print("==============================")
    print(f"Character: {session.character_name}")
    print(f"Provider:  {session.provider}")
    print(f"Model:     {session.model}")
    print(f"Memory:    {len(session.memory)} item(s)")
    print(f"Session:   {session.session_id}")
    print("==============================")
    print("Type /help for commands.")
    print()


def show_chats():
    chats = load_index()

    print()
    print("Saved Chats")
    print("-----------")

    if not chats:
        print("No saved chats.")
        print()
        return

    for chat_info in chats:
        chat_id = chat_info.get("session_id", "Unknown")
        title = chat_info.get("title", "Untitled")
        provider = chat_info.get("provider", "unknown")
        model = chat_info.get("model", "unknown")
        active = " (active)" if chat_id == session.session_id else ""
        print(f"{chat_id}: {title} [{provider} / {model}]{active}")

    print()


def show_character():
    print(
        f"WOS: Active character: "
        f"{session.character_name} ({session.character_id})"
    )


def show_characters():
    characters = list_characters()

    print()
    print("Available Characters")
    print("--------------------")

    if not characters:
        print("No valid characters found.")
        print()
        return

    for character in characters:
        active = " (active)" if character["id"] == session.character_id else ""
        print(f'{character["id"]}: {character["name"]}{active}')

    print()


def manage_character(arguments):
    arguments = arguments.strip()

    if not arguments:
        show_character()
        return

    action, separator, remainder = arguments.partition(" ")
    action = action.lower()
    remainder = remainder.strip()

    if action == "list" and not separator:
        show_characters()
        return

    if action == "switch":
        if not separator or not remainder or " " in remainder:
            print("WOS: Usage: /character switch <character_id>")
            print("Use /character list to see available characters.")
            return

        result = session.switch_character(remainder)
        print(f"WOS: {result}")
        return

    print("WOS: Unknown character command.")
    print("Use /character, /character list, or /character switch <id>.")


def rename_chat(arguments):
    parts = arguments.split(maxsplit=1)

    if len(parts) != 2 or not parts[1].strip():
        print("WOS: Usage: /rename <session_id> <new_name>")
        return

    target_id, new_name = parts[0], parts[1].strip()
    chat_data = load_chat(target_id)

    if chat_data is None:
        print(f"WOS: Chat '{target_id}' was not found.")
        return

    chat_data["title"] = new_name

    try:
        update_chat(chat_data)
    except (OSError, ValueError) as error:
        print(f"WOS: Could not rename chat: {error}")
        return

    if target_id == session.session_id:
        session.chat = chat_data

    print(f"WOS: Renamed {target_id} to '{new_name}'.")


def remove_chat(target_id):
    if load_chat(target_id) is None:
        print(f"WOS: Chat '{target_id}' was not found.")
        return

    confirmation = input(
        f"WOS: Delete '{target_id}' permanently? (y/n): "
    ).strip().lower()

    if confirmation not in ("y", "yes"):
        print("WOS: Deletion cancelled.")
        return

    was_active = target_id == session.session_id

    try:
        deleted = delete_chat(target_id)
    except (OSError, ValueError) as error:
        print(f"WOS: Could not delete chat: {error}")
        return

    if deleted is False:
        print(f"WOS: Chat '{target_id}' could not be deleted.")
        return

    print(f"WOS: Deleted {target_id}.")

    if was_active:
        remaining_chats = load_index()

        if remaining_chats:
            next_id = remaining_chats[-1].get("session_id")

            if not next_id or not session.switch_chat(next_id):
                session.new_chat()
        else:
            session.new_chat()

        print(f"WOS: Active session is now {session.session_id}.")


def show_context():
    info = session.context_info()

    print()
    print("WOS Context")
    print("-----------")
    print(f"Session:             {info['session_id']}")
    print(f"Saved messages:      {info['saved_messages']}")
    print(f"Messages in context: {info['messages_in_context']}")
    print(f"Context limit:       {info['context_limit']}")
    print()


def show_status():
    info = session.context_info()

    print()
    print("WOS Status")
    print("----------")
    print(f"Character:      {session.character_name}")
    print(f"Provider:       {session.provider}")
    print(f"Model:          {session.model}")
    print(f"Session:        {session.session_id}")
    print(f"Saved chats:    {len(load_index())}")
    print(f"Saved memories: {len(session.memory)} item(s)")
    print(
        f"Context:        {info['messages_in_context']}"
        f"/{info['context_limit']} messages"
    )
    print()


def refresh_memory_context():
    session.refresh_system_prompt()
    session.messages = session.create_messages()


def manage_memory(arguments):
    arguments = arguments.strip()

    if not arguments:
        show_memory(session.memory)
        return

    action, separator, remainder = arguments.partition(" ")
    action = action.lower()
    remainder = remainder.strip()

    if action == "edit":
        if not separator or not remainder:
            print("WOS: Usage: /memory edit <key> <new_value>")
            print("Use /memory to view saved memory keys.")
            return

        matches = []

        for item in session.memory:
            key = item.get("key", "")
            displayed_key = key.replace("_", " ")

            if remainder.startswith(displayed_key + " "):
                value = remainder[len(displayed_key):].strip()

                if value:
                    matches.append((key, value))

        if matches:
            key, new_value = max(
                matches,
                key=lambda match: len(match[0]),
            )
        else:
            parts = remainder.split(maxsplit=1)

            if len(parts) != 2 or not parts[1].strip():
                print("WOS: Usage: /memory edit <key> <new_value>")
                print("Use /memory to view saved memory keys.")
                return

            key, new_value = parts[0], parts[1].strip()

        result = edit_memory(session.memory, key, new_value)
        print(f"WOS: {result}")

        if result == "Memory updated successfully.":
            refresh_memory_context()

        return

    if action == "delete":
        if not separator or not remainder:
            print("WOS: Usage: /memory delete <key>")
            print("Use /memory to view saved memory keys.")
            return

        target = remainder

        confirmation = input(
            f"WOS: Delete memory '{target}' permanently? (y/n): "
        ).strip().lower()

        if confirmation not in ("y", "yes"):
            print("WOS: Deletion cancelled.")
            return

        result = forget_memory(session.memory, f"forget that {target}")
        print(f"WOS: {result}")

        failed = (
            result is None
            or "couldn't find" in result.lower()
            or "couldn't save" in result.lower()
        )

        if not failed:
            refresh_memory_context()

        return

    if action == "clear":
        confirmation = input(
            "WOS: Delete ALL saved memories permanently? (y/n): "
        ).strip().lower()

        if confirmation not in ("y", "yes"):
            print("WOS: Memory clearing cancelled.")
            return

        result = clear_memory(session.memory, confirmed=True)
        print(f"WOS: {result}")

        if result == "All saved memories have been cleared.":
            refresh_memory_context()

        return

    print("WOS: Unknown memory command.")
    print("Use /memory, /memory edit, /memory delete, or /memory clear.")


def manage_provider(arguments):
    arguments = arguments.strip()

    if not arguments:
        print(f"WOS: Current provider: {session.provider}")
        print("Available providers: cloud, ollama")
        print("Usage: /provider <name>")
        return

    result = session.change_provider(arguments)
    print(f"WOS: {result}")


def manage_model(arguments):
    arguments = arguments.strip()

    if not arguments:
        print(f"WOS: Current model: {session.model}")
        print(f"Provider: {session.provider}")
        print("Usage: /model <model_name>")
        return

    result = session.change_model(arguments)
    print(f"WOS: {result}")


def manage_defaults(arguments):
    arguments = arguments.strip()

    if not arguments:
        print("WOS Default Settings")
        print("--------------------")
        print(f"Default provider:  {session.default_provider}")
        print(f"Default model:     {session.default_model}")
        print(f"Default character: {session.default_character_id}")
        print("Usage: /defaults provider <name>")
        print("       /defaults model <name>")
        return

    action, separator, value = arguments.partition(" ")
    action = action.lower()
    value = value.strip()

    if not separator or not value:
        print("WOS: Usage: /defaults provider <name>")
        print("       /defaults model <name>")
        return

    if action == "provider":
        provider = value.lower()

        if provider not in SUPPORTED_PROVIDERS:
            print(
                "WOS: Unsupported provider. Choose: "
                + ", ".join(sorted(SUPPORTED_PROVIDERS))
            )
            return

        result = session.save_defaults(provider=provider)
        print(f"WOS: {result}")
        return

    if action == "model":
        result = session.save_defaults(model=value)
        print(f"WOS: {result}")
        return

    print("WOS: Usage: /defaults provider <name>")
    print("       /defaults model <name>")


# ------------------------------
# Main loop
# ------------------------------

show_header()

while True:
    try:
        message = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("WOS: Goodbye.")
        break

    if not message:
        continue

    command = message.lower()

    if command in ("/exit", "/quit"):
        print("WOS: Conversation saved.")
        break

    if command == "/help":
        show_help()
        continue

    if command == "/restart":
        print("WOS: Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    if command == "/new":
        session.new_chat()
        print(f"WOS: Started {session.session_id}.")
        continue

    if command == "/chats":
        show_chats()
        continue

    if command == "/character":
        manage_character("")
        continue

    if command.startswith("/character "):
        manage_character(message[len("/character "):])
        continue

    if command == "/switch":
        print("WOS: Usage: /switch <session_id>")
        print("Use /chats to see available session IDs.")
        continue

    if command.startswith("/switch "):
        target_id = message.split(maxsplit=1)[1].strip()

        if session.switch_chat(target_id):
            print(f"WOS: Switched to {session.session_id}.")
            print(f"Character: {session.character_name}")
            print(f"Provider: {session.provider}")
            print(f"Model: {session.model}")
        else:
            print(f"WOS: Chat '{target_id}' was not found.")

        continue

    if command == "/rename":
        print("WOS: Usage: /rename <session_id> <new_name>")
        continue

    if command.startswith("/rename "):
        rename_chat(message[len("/rename "):])
        continue

    if command == "/delete":
        print("WOS: Usage: /delete <session_id>")
        continue

    if command.startswith("/delete "):
        target_id = message.split(maxsplit=1)[1].strip()

        if " " in target_id:
            print("WOS: Usage: /delete <session_id>")
        else:
            remove_chat(target_id)

        continue

    if command == "/provider":
        manage_provider("")
        continue

    if command.startswith("/provider "):
        manage_provider(message[len("/provider "):])
        continue

    if command == "/model":
        manage_model("")
        continue

    if command.startswith("/model "):
        manage_model(message[len("/model "):])
        continue

    if command == "/defaults":
        manage_defaults("")
        continue

    if command.startswith("/defaults "):
        manage_defaults(message[len("/defaults "):])
        continue

    if command == "/forget":
        print("WOS: Usage: /forget <memory>")
        print("Example: /forget that I am learning Python")
        continue

    if command.startswith("/forget "):
        target = message[len("/forget "):].strip()

        if not target:
            print("WOS: Usage: /forget <memory>")
            continue

        if target.lower().startswith(("that ", "about ")):
            forget_request = f"Forget {target}"
        else:
            forget_request = f"Forget that {target}"

        reply = session.send_message(forget_request)

        if reply is None:
            print("WOS: The memory operation did not return a response.")
        else:
            print(f"{session.character_name}: {reply}")

        continue

    if command == "/memory":
        show_memory(session.memory)
        continue

    if command.startswith("/memory "):
        manage_memory(message[len("/memory "):])
        continue

    if command == "/status":
        show_status()
        continue

    if command == "/context":
        show_context()
        continue

    if command == "/clear":
        session.clear()
        print("WOS: Conversation cleared.")
        continue

    reply = session.send_message(message)

    if reply is None:
        print("WOS: The model did not return a response.")
        continue

    print(f"{session.character_name}: {reply}")
