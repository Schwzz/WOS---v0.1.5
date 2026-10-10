import threading
import tkinter as tk

import customtkinter as ctk

from core.session import Session
from core.conversation import load_conversation
from core.memory import save_memory


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


session = Session()

app = ctk.CTk()

app.title("WaifuOS")
app.geometry("1000x650")
app.minsize(800, 550)


# =========================
# Drawer State
# =========================

drawer = None
drawer_open = False
main_frame = None


# =========================
# Screen Helpers
# =========================

def clear_screen():
    global drawer
    global main_frame

    drawer = None
    main_frame = None

    for widget in app.winfo_children():
        widget.destroy()


def start_waifuos():
    show_chat()


# =========================
# Drawer
# =========================

def create_drawer():
    global drawer
    global drawer_open

    drawer_open = False

    drawer = ctk.CTkFrame(
        app,
        width=220,
        corner_radius=0
    )

    drawer.pack(
        side="left",
        fill="y"
    )

    drawer.pack_propagate(False)

    title = ctk.CTkLabel(
        drawer,
        text="WaifuOS",
        font=ctk.CTkFont(
            size=24,
            weight="bold"
        )
    )

    title.pack(
        pady=(30, 10)
    )

    character_label = ctk.CTkLabel(
        drawer,
        text=session.character_name,
        font=ctk.CTkFont(
            size=16,
            weight="bold"
        )
    )

    character_label.pack(
        pady=(0, 30)
    )

    chat_button = ctk.CTkButton(
        drawer,
        text="Chat",
        height=40,
        command=show_chat
    )

    chat_button.pack(
        fill="x",
        padx=20,
        pady=5
    )

    memory_button = ctk.CTkButton(
        drawer,
        text="Memory",
        height=40,
        command=show_memory
    )

    memory_button.pack(
        fill="x",
        padx=20,
        pady=5
    )

    settings_button = ctk.CTkButton(
        drawer,
        text="Settings",
        height=40,
        command=show_settings
    )

    settings_button.pack(
        fill="x",
        padx=20,
        pady=5
    )

    drawer.pack_forget()


def toggle_drawer():
    global drawer_open

    if drawer is None or main_frame is None:
        return

    if drawer_open:
        drawer.pack_forget()
        drawer_open = False

    else:
        drawer.pack(
            side="left",
            fill="y",
            before=main_frame
        )

        drawer_open = True


def create_top_bar(parent, title_text):
    top_bar = ctk.CTkFrame(
        parent,
        height=60,
        corner_radius=0,
        fg_color="transparent"
    )

    top_bar.pack(
        fill="x",
        padx=20,
        pady=(15, 0)
    )

    top_bar.pack_propagate(False)

    menu_button = ctk.CTkButton(
        top_bar,
        text="☰",
        width=45,
        height=40,
        font=ctk.CTkFont(
            size=22
        ),
        command=toggle_drawer
    )

    menu_button.pack(
        side="left"
    )

    title = ctk.CTkLabel(
        top_bar,
        text=title_text,
        font=ctk.CTkFont(
            size=24,
            weight="bold"
        )
    )

    title.pack(
        side="left",
        padx=15
    )

    return top_bar


# =========================
# Chat Screen
# =========================

def show_chat():
    global main_frame

    clear_screen()
    create_drawer()

    main_frame = ctk.CTkFrame(
        app,
        corner_radius=0
    )

    main_frame.pack(
        side="left",
        fill="both",
        expand=True
    )

    create_top_bar(
        main_frame,
        session.character_name
    )

    chat_area = ctk.CTkScrollableFrame(
        main_frame,
        corner_radius=0
    )

    chat_area.pack(
        fill="both",
        expand=True,
        padx=40,
        pady=20
    )

    def scroll_to_bottom():
        app.after(
            10,
            lambda: chat_area._parent_canvas.yview_moveto(1.0)
        )

    def add_message(sender, message):
        is_user = sender == "You"

        row = ctk.CTkFrame(
            chat_area,
            fg_color="transparent"
        )

        row.pack(
            fill="x",
            pady=6
        )

        bubble = ctk.CTkFrame(
            row,
            corner_radius=12
        )

        if is_user:
            bubble.configure(
                fg_color="#5B3FA3"
            )

            bubble.pack(
                side="right",
                padx=(100, 10)
            )

        else:
            bubble.configure(
                fg_color="#2B2B2B"
            )

            bubble.pack(
                side="left",
                padx=(10, 100)
            )

        sender_label = ctk.CTkLabel(
            bubble,
            text=sender,
            font=ctk.CTkFont(
                size=12,
                weight="bold"
            ),
            text_color="#D0D0D0"
        )

        sender_label.pack(
            anchor="w",
            padx=12,
            pady=(8, 0)
        )

        # =========================
        # Selectable Message Text
        # =========================

        message_box = tk.Text(
            bubble,
            font=("Segoe UI", 14),
            width=62,
            height=1,
            wrap="word",
            bg="#5B3FA3" if is_user else "#2B2B2B",
            fg="white",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0
        )

        message_box.insert(
            "1.0",
            message
        )

        def copy_selected(event=None):
            try:
                selected_text = message_box.get(
                    "sel.first",
                    "sel.last"
                )

                app.clipboard_clear()
                app.clipboard_append(selected_text)
                app.update()

            except tk.TclError:
                pass

            return "break"

        def select_all(event=None):
            message_box.tag_add(
                "sel",
                "1.0",
                "end-1c"
            )

            return "break"

        def block_editing(event):
            if event.state & 0x4:
                return

            if event.keysym in (
                "Left",
                "Right",
                "Up",
                "Down",
                "Home",
                "End",
                "Prior",
                "Next"
            ):
                return

            return "break"

        message_box.bind(
            "<Control-c>",
            copy_selected
        )

        message_box.bind(
            "<Control-a>",
            select_all
        )

        message_box.bind(
            "<KeyPress>",
            block_editing
        )

        message_box.pack(
            padx=12,
            pady=(2, 10)
        )

        # Let Tkinter calculate the actual wrapped lines.
        message_box.update_idletasks()

        try:
            display_lines = message_box.count(
                "1.0",
                "end-1c",
                "displaylines"
            )

            line_count = int(display_lines[0])

        except (tk.TclError, IndexError, TypeError, ValueError):
            line_count = 1

        message_box.configure(
            height=max(1, line_count)
        )

        message_box.update_idletasks()

        scroll_to_bottom()

    # =========================
    # Load Conversation
    # =========================

    conversation = load_conversation()

    if conversation:
        for message in conversation:
            role = message.get("role")
            content = message.get("content", "")

            if role == "user":
                add_message(
                    "You",
                    content
                )

            elif role == "assistant":
                add_message(
                    session.character_name,
                    content
                )

    else:
        add_message(
            session.character_name,
            "Hello, Swartz."
        )

    # =========================
    # Message Input
    # =========================

    input_frame = ctk.CTkFrame(
        main_frame
    )

    input_frame.pack(
        fill="x",
        padx=40,
        pady=(0, 30)
    )

    message_entry = ctk.CTkEntry(
        input_frame,
        height=40,
        placeholder_text="Type a message..."
    )

    message_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=(10, 10),
        pady=10
    )

    send_button = ctk.CTkButton(
        input_frame,
        text="SEND",
        width=100,
        height=40
    )

    send_button.pack(
        side="right",
        padx=(0, 10),
        pady=10
    )

    # =========================
    # Thinking Indicator
    # =========================

    thinking_row = None

    def show_thinking():
        nonlocal thinking_row

        thinking_row = ctk.CTkFrame(
            chat_area,
            fg_color="transparent"
        )

        thinking_row.pack(
            fill="x",
            pady=6
        )

        bubble = ctk.CTkFrame(
            thinking_row,
            corner_radius=12,
            fg_color="#2B2B2B"
        )

        bubble.pack(
            side="left",
            padx=(10, 100)
        )

        label = ctk.CTkLabel(
            bubble,
            text=f"{session.character_name} is thinking...",
            font=ctk.CTkFont(
                size=13
            ),
            text_color="#A0A0A0"
        )

        label.pack(
            padx=12,
            pady=10
        )

        scroll_to_bottom()

    def remove_thinking():
        nonlocal thinking_row

        if thinking_row is not None:
            thinking_row.destroy()
            thinking_row = None

    # =========================
    # Response Handling
    # =========================

    def finish_response(reply):
        remove_thinking()

        if reply is None:
            add_message(
                "WaifuOS",
                "Failed to get a response."
            )

        else:
            add_message(
                session.character_name,
                reply
            )

        send_button.configure(
            state="normal",
            text="SEND"
        )

        message_entry.configure(
            state="normal"
        )

        message_entry.focus()

        scroll_to_bottom()

    def get_response(message):
        reply = session.send_message(message)

        app.after(
            0,
            lambda: finish_response(reply)
        )

    # =========================
    # Send Message
    # =========================

    def send_message():
        message = message_entry.get().strip()

        if not message:
            return

        message_entry.delete(
            0,
            "end"
        )

        add_message(
            "You",
            message
        )

        show_thinking()

        send_button.configure(
            state="disabled",
            text="..."
        )

        message_entry.configure(
            state="disabled"
        )

        threading.Thread(
            target=get_response,
            args=(message,),
            daemon=True
        ).start()

    send_button.configure(
        command=send_message
    )

    message_entry.bind(
        "<Return>",
        lambda event: send_message()
    )

    message_entry.focus()


# =========================
# Memory Screen
# =========================

def show_memory():
    global main_frame

    clear_screen()
    create_drawer()

    main_frame = ctk.CTkFrame(
        app,
        corner_radius=0
    )

    main_frame.pack(
        side="left",
        fill="both",
        expand=True
    )

    create_top_bar(
        main_frame,
        "Memory"
    )

    memory_frame = ctk.CTkScrollableFrame(
        main_frame
    )

    memory_frame.pack(
        fill="both",
        expand=True,
        padx=50,
        pady=20
    )

    def delete_memory(memory_item):
        if memory_item in session.memory:
            session.memory.remove(memory_item)

            save_memory(
                session.memory
            )

            show_memory()

    memory = session.memory

    if not memory:
        empty_label = ctk.CTkLabel(
            memory_frame,
            text="No memories saved."
        )

        empty_label.pack(
            pady=40
        )

    else:
        for item in memory:
            key = item.get(
                "key",
                "Unknown"
            ).replace(
                "_",
                " "
            )

            value = item.get(
                "value",
                ""
            )

            memory_item = ctk.CTkFrame(
                memory_frame,
                corner_radius=10
            )

            memory_item.pack(
                fill="x",
                padx=10,
                pady=8
            )

            key_label = ctk.CTkLabel(
                memory_item,
                text=key.title(),
                font=ctk.CTkFont(
                    size=15,
                    weight="bold"
                )
            )

            key_label.pack(
                side="left",
                padx=(15, 10),
                pady=15
            )

            value_label = ctk.CTkLabel(
                memory_item,
                text=value,
                font=ctk.CTkFont(
                    size=14
                )
            )

            value_label.pack(
                side="left",
                padx=10,
                pady=15
            )

            delete_button = ctk.CTkButton(
                memory_item,
                text="DELETE",
                width=80,
                height=30,
                command=lambda memory_item=item: delete_memory(
                    memory_item
                )
            )

            delete_button.pack(
                side="right",
                padx=15,
                pady=10
            )


# =========================
# Settings Screen
# =========================

def show_settings():
    global main_frame

    clear_screen()
    create_drawer()

    main_frame = ctk.CTkFrame(
        app,
        corner_radius=0
    )

    main_frame.pack(
        side="left",
        fill="both",
        expand=True
    )

    create_top_bar(
        main_frame,
        "Settings"
    )

    placeholder = ctk.CTkLabel(
        main_frame,
        text="Settings will be available here."
    )

    placeholder.pack(
        pady=30
    )


# =========================
# Setup Screen
# =========================

def show_setup():
    clear_screen()

    title = ctk.CTkLabel(
        app,
        text="WaifuOS",
        font=ctk.CTkFont(
            size=36,
            weight="bold"
        )
    )

    title.pack(
        pady=(60, 5)
    )

    subtitle = ctk.CTkLabel(
        app,
        text="Personal AI Companion System",
        font=ctk.CTkFont(
            size=16
        )
    )

    subtitle.pack(
        pady=(0, 40)
    )

    setup_frame = ctk.CTkFrame(
        app,
        width=500
    )

    setup_frame.pack(
        padx=40,
        pady=10
    )

    # Character

    character_label = ctk.CTkLabel(
        setup_frame,
        text="Character"
    )

    character_label.grid(
        row=0,
        column=0,
        padx=20,
        pady=15,
        sticky="w"
    )

    character_menu = ctk.CTkOptionMenu(
        setup_frame,
        values=[session.character_name],
        width=250
    )

    character_menu.set(
        session.character_name
    )

    character_menu.grid(
        row=0,
        column=1,
        padx=20,
        pady=15
    )

    # Provider

    provider_label = ctk.CTkLabel(
        setup_frame,
        text="Provider"
    )

    provider_label.grid(
        row=1,
        column=0,
        padx=20,
        pady=15,
        sticky="w"
    )

    provider_menu = ctk.CTkOptionMenu(
        setup_frame,
        values=[session.provider],
        width=250
    )

    provider_menu.set(
        session.provider
    )

    provider_menu.grid(
        row=1,
        column=1,
        padx=20,
        pady=15
    )

    # Model

    model_label = ctk.CTkLabel(
        setup_frame,
        text="Model"
    )

    model_label.grid(
        row=2,
        column=0,
        padx=20,
        pady=15,
        sticky="w"
    )

    model_menu = ctk.CTkOptionMenu(
        setup_frame,
        values=[session.model],
        width=250
    )

    model_menu.set(
        session.model
    )

    model_menu.grid(
        row=2,
        column=1,
        padx=20,
        pady=15
    )

    # Start

    start_button = ctk.CTkButton(
        app,
        text="START",
        width=220,
        height=50,
        font=ctk.CTkFont(
            size=16,
            weight="bold"
        ),
        command=start_waifuos
    )

    start_button.pack(
        pady=40
    )


show_setup()
app.mainloop()