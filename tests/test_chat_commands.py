"""End-to-end tests for /chat and its compatibility aliases, plus /help.

Each test starts Auralis as a real subprocess in a throwaway copy of the project.
Most feed commands through stdin (where the input simply ends, which is EOF).
Tests that need a real Ctrl+C use run_scripted(), which raises
KeyboardInterrupt at a chosen prompt.
"""
import json
import re
import unittest

from tests.test_start_integration import IntegrationTestCase


def lines(*commands):
    return "\n".join(commands) + "\n"


class ChatTestCase(IntegrationTestCase):
    """Adds helpers for building chats and checking what was saved."""

    def make_chats(self, total):
        """Create chats so that session_001..session_00N exist. The last
        one created is the active chat."""
        self.wos.run(lines(*(["/new"] * (total - 1)), "/exit"))

    def title(self, session_id):
        return self.wos.read_chat(session_id)["title"]

    def active_id(self):
        path = self.wos.chats_dir / "active_session.json"

        return json.loads(path.read_text("utf-8"))["session_id"]

    def seed_messages(self, session_id, count=2):
        """Put saved messages into a chat file (the AI is never called)."""
        path = self.wos.chats_dir / f"{session_id}.json"
        chat = json.loads(path.read_text("utf-8"))
        chat["messages"] = [
            {"role": "user" if n % 2 == 0 else "assistant",
             "content": f"message {n}"}
            for n in range(count)
        ]
        path.write_text(json.dumps(chat), encoding="utf-8")

    def message_count(self, session_id):
        return len(self.wos.read_chat(session_id)["messages"])


# ------------------------------------------------------------------
# /chat menu and /chat list
# ------------------------------------------------------------------

class ChatMenuTests(ChatTestCase):
    def test_menu_lists_every_action_as_a_numbered_choice(self):
        result = self.wos.run(lines("/chat", "0", "/exit"))

        self.assertNoCrash(result)
        for line in ("Chat Actions",
                     "1. List saved chats",
                     "2. Switch to another chat",
                     "3. Rename a chat",
                     "4. Delete a chat",
                     "5. Clear the current chat"):
            with self.subTest(line=line):
                self.assertIn(line, result.stdout)

        self.assertIn("(Enter or 0 to cancel)", result.stdout)

    def test_zero_and_enter_cancel_the_menu(self):
        for answer in ("0", ""):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("Cancelled. Nothing was changed.", result.stdout)

    def test_choosing_list_shows_the_saved_chats(self):
        result = self.wos.run(lines("/chat", "1", "/exit"))

        self.assertNoCrash(result)
        self.assertIn(
            "session_001: Chat 1 [cloud / gemini-3.5-flash-lite] (active)",
            result.stdout,
        )

    def test_choosing_switch_continues_into_the_chat_list(self):
        self.make_chats(2)

        result = self.wos.run(lines("/chat", "2", "1", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Switched to session_001", result.stdout)

    def test_invalid_choices_ask_again(self):
        result = self.wos.run(lines("/chat", "9", "abc", "-1", "1", "/exit"))

        self.assertNoCrash(result)
        self.assertEqual(
            result.stdout.count("Please enter a number from 1 to 5."), 3
        )
        self.assertIn("Saved Chats", result.stdout)

    def test_eof_at_the_menu_is_safe(self):
        result = self.wos.run("/chat\n")  # input ends at the menu prompt

        self.assertNoCrash(result)
        self.assertIn("Cancelled. Nothing was changed.", result.stdout)

    def test_ctrl_c_at_the_menu_is_safe_and_wos_keeps_running(self):
        result = self.wos.run_scripted(
            ["/chat", "<CTRL-C>", "/status", "/exit"]
        )

        self.assertNoCrash(result)
        self.assertIn("Cancelled. Nothing was changed.", result.stdout)
        self.assertIn("Auralis Status", result.stdout)

    def test_subcommands_and_the_command_itself_ignore_case(self):
        result = self.wos.run(lines("/CHAT LIST", "/Chat List", "/exit"))

        self.assertNoCrash(result)
        self.assertEqual(
            result.stdout.count("session_001: Chat 1"), 2
        )

    def test_unknown_subcommand_is_an_error_with_a_suggestion(self):
        result = self.wos.run(lines("/chat swich", "/chat zzzz", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Unknown command '/chat swich'", result.stdout)
        self.assertIn("Did you mean /chat switch?", result.stdout)
        self.assertIn("Unknown command '/chat zzzz'", result.stdout)
        self.assertIn("/help chat", result.stdout)
        self.assertNotIn("fake genai", result.stdout)  # never sent to the AI

    def test_list_and_clear_reject_extra_arguments(self):
        self.seed_after_first_run()

        result = self.wos.run(lines("/chat list now", "/chat clear all", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("'/chat list' does not take any arguments", result.stdout)
        self.assertIn("'/chat clear' does not take any arguments", result.stdout)
        self.assertEqual(self.message_count("session_001"), 2)

    def seed_after_first_run(self):
        self.wos.run("/exit\n")
        self.seed_messages("session_001")


class ChatListTests(ChatTestCase):
    def listing(self, command):
        result = self.wos.run(lines(command, "/exit"))
        self.assertNoCrash(result)

        return [
            line for line in result.stdout.splitlines()
            if re.match(r"session_\d+: ", line)
        ]

    def test_list_shows_every_chat_and_marks_the_active_one(self):
        self.make_chats(3)

        listing = self.listing("/chat list")

        self.assertEqual(len(listing), 3)
        self.assertTrue(listing[2].endswith("(active)"))
        self.assertFalse(listing[0].endswith("(active)"))

    def test_chats_alias_gives_the_same_list(self):
        self.make_chats(3)

        self.assertEqual(self.listing("/chats"), self.listing("/chat list"))

    def test_list_format_is_unchanged(self):
        listing = self.listing("/chats")

        self.assertEqual(listing, [
            "session_001: Chat 1 [cloud / gemini-3.5-flash-lite] (active)"
        ])


# ------------------------------------------------------------------
# /chat switch
# ------------------------------------------------------------------

class ChatSwitchTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.make_chats(3)  # session_003 is active

    def test_numbered_menu_switches_to_the_chosen_chat(self):
        result = self.wos.run(lines("/chat switch", "1", "/status", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("1. session_001: Chat 1", result.stdout)
        self.assertIn("3. session_003: Chat 3", result.stdout)
        self.assertIn("Switched to session_001", result.stdout)
        self.assertRegex(result.stdout, r"Session:\s+session_001")
        self.assertEqual(self.active_id(), "session_001")

    def test_switch_by_id_needs_no_menu(self):
        result = self.wos.run(lines("/chat switch session_002", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Switched to session_002", result.stdout)
        self.assertNotIn("Number of the chat", result.stdout)
        self.assertEqual(self.active_id(), "session_002")

    def test_the_menu_marks_the_active_chat(self):
        result = self.wos.run(lines("/chat switch", "0", "/exit"))

        self.assertIn("3. session_003: Chat 3 "
                      "[cloud / gemini-3.5-flash-lite] (active)",
                      result.stdout)

    def test_enter_and_zero_cancel_without_switching(self):
        for answer in ("", "0"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat switch", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn(
                    "Switch cancelled. You are still in session_003",
                    result.stdout,
                )
                self.assertNotIn("Switched to", result.stdout)
                self.assertEqual(self.active_id(), "session_003")

    def test_invalid_numbers_ask_again_and_never_switch(self):
        result = self.wos.run(lines("/chat switch", "7", "x", "2", "/exit"))

        self.assertNoCrash(result)
        self.assertEqual(
            result.stdout.count("Please enter a number from 1 to 3."), 2
        )
        self.assertIn("Switched to session_002", result.stdout)

    def test_eof_does_not_switch(self):
        result = self.wos.run("/chat switch\n")

        self.assertNoCrash(result)
        self.assertNotIn("Switched to", result.stdout)
        self.assertEqual(self.active_id(), "session_003")

    def test_ctrl_c_does_not_switch_and_wos_keeps_running(self):
        result = self.wos.run_scripted(
            ["/chat switch", "<CTRL-C>", "/status", "/exit"]
        )

        self.assertNoCrash(result)
        self.assertNotIn("Switched to", result.stdout)
        self.assertRegex(result.stdout, r"Session:\s+session_003")
        self.assertEqual(self.active_id(), "session_003")

    def test_unknown_id_explains_how_to_get_a_list(self):
        result = self.wos.run(lines("/chat switch session_099", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Chat 'session_099' was not found.", result.stdout)
        self.assertIn("type /chat switch on its own", result.stdout)
        self.assertEqual(self.active_id(), "session_003")

    def test_chat_keeps_its_own_settings_when_switched_to(self):
        self.wos.run(lines("/provider ollama llama3", "/exit"))  # session_003

        result = self.wos.run(
            lines("/chat switch", "1", "/status", "/chat switch", "3",
                  "/status", "/exit")
        )

        # Read only the /status blocks; the startup header and the
        # "Switched to" message print the same fields.
        statuses = re.findall(
            r"Auralis Status\n-+\nCharacter:.*\nProvider:\s+(\w+)\n"
            r"Model:\s+(\S+)",
            result.stdout,
        )
        self.assertEqual(statuses, [
            ("cloud", "gemini-3.5-flash-lite"),
            ("ollama", "llama3"),
        ])

    def test_switch_alias_works_with_and_without_an_id(self):
        interactive = self.wos.run(lines("/switch", "2", "/exit"))
        direct = self.wos.run(lines("/switch session_001", "/exit"))

        self.assertNoCrash(interactive)
        self.assertIn("Switched to session_002", interactive.stdout)
        self.assertNoCrash(direct)
        self.assertIn("Switched to session_001", direct.stdout)


# ------------------------------------------------------------------
# /chat rename
# ------------------------------------------------------------------

class ChatRenameTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.make_chats(3)

    def test_menu_then_title_prompt_renames_the_chat(self):
        result = self.wos.run(
            lines("/chat rename", "2", "Python practice", "/chats", "/exit")
        )

        self.assertNoCrash(result)
        self.assertIn("1. session_001: Chat 1", result.stdout)
        self.assertIn("New title for 'Chat 2'", result.stdout)
        self.assertIn("Renamed session_002 to 'Python practice'", result.stdout)
        self.assertIn("session_002: Python practice [cloud", result.stdout)
        self.assertEqual(self.title("session_002"), "Python practice")
        self.assertEqual(self.title("session_001"), "Chat 1")
        self.assertEqual(self.title("session_003"), "Chat 3")

    def test_id_without_a_title_asks_for_the_title(self):
        result = self.wos.run(
            lines("/chat rename session_001", "My first chat", "/exit")
        )

        self.assertNoCrash(result)
        self.assertNotIn("Number of the chat", result.stdout)
        self.assertIn("New title for 'Chat 1'", result.stdout)
        self.assertEqual(self.title("session_001"), "My first chat")

    def test_id_and_title_rename_directly(self):
        result = self.wos.run(
            lines("/chat rename session_001 A  longer   title here", "/exit")
        )

        self.assertNoCrash(result)
        self.assertNotIn("New title for", result.stdout)
        self.assertEqual(self.title("session_001"), "A  longer   title here")

    def test_titles_are_saved_in_the_chat_file_and_the_list(self):
        self.wos.run(lines("/chat rename session_003 Active one", "/exit"))

        result = self.wos.run(lines("/chats", "/exit"))  # after a restart

        self.assertIn("session_003: Active one [cloud", result.stdout)
        self.assertEqual(self.title("session_003"), "Active one")

    def test_cancelling_the_menu_renames_nothing(self):
        for answer in ("", "0"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat rename", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("Rename cancelled", result.stdout)
                self.assertNotIn("New title for", result.stdout)

        self.assertEqual(
            [self.title(f"session_00{n}") for n in (1, 2, 3)],
            ["Chat 1", "Chat 2", "Chat 3"],
        )

    def test_cancelling_the_title_prompt_renames_nothing(self):
        for answer in ("", "   "):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(
                    lines("/chat rename session_001", answer, "/exit")
                )

                self.assertNoCrash(result)
                self.assertIn("Rename cancelled", result.stdout)
                self.assertEqual(self.title("session_001"), "Chat 1")

    def test_eof_at_the_menu_or_title_prompt_renames_nothing(self):
        for script in ("/chat rename\n", "/chat rename\n1\n",
                       "/chat rename session_001\n"):
            with self.subTest(script=script):
                result = self.wos.run(script)

                self.assertNoCrash(result)
                self.assertEqual(self.title("session_001"), "Chat 1")

    def test_ctrl_c_at_the_menu_or_title_prompt_renames_nothing(self):
        for answers in (["/chat rename", "<CTRL-C>", "/status", "/exit"],
                        ["/chat rename", "1", "<CTRL-C>", "/status", "/exit"]):
            with self.subTest(answers=answers):
                result = self.wos.run_scripted(answers)

                self.assertNoCrash(result)
                self.assertIn("Rename cancelled", result.stdout)
                self.assertIn("Auralis Status", result.stdout)
                self.assertEqual(self.title("session_001"), "Chat 1")

    def test_unknown_id_is_reported_and_nothing_changes(self):
        result = self.wos.run(
            lines("/chat rename session_099 New name", "/exit")
        )

        self.assertNoCrash(result)
        self.assertIn("Chat 'session_099' was not found.", result.stdout)
        self.assertIn("type /chat rename on its own", result.stdout)

    def test_rename_alias_works_in_both_forms(self):
        interactive = self.wos.run(lines("/rename", "1", "Via alias", "/exit"))
        direct = self.wos.run(
            lines("/rename session_002 Direct alias", "/exit")
        )

        self.assertNoCrash(interactive)
        self.assertNoCrash(direct)
        self.assertEqual(self.title("session_001"), "Via alias")
        self.assertEqual(self.title("session_002"), "Direct alias")


# ------------------------------------------------------------------
# /chat delete
# ------------------------------------------------------------------

class ChatDeleteTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.make_chats(3)  # session_003 is active

    def test_menu_selection_and_confirmation_delete_the_chat(self):
        result = self.wos.run(lines("/chat delete", "2", "y", "/exit"))

        self.assertNoCrash(result)
        self.assertIn(
            "Delete 'Chat 2' (session_002) permanently? (y/n)", result.stdout
        )
        self.assertIn("Deleted session_002", result.stdout)
        self.assertEqual(self.wos.chat_ids(), ["session_001", "session_003"])

    def test_declining_keeps_the_chat(self):
        for answer in ("n", "no", "", "maybe", "yy"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat delete", "2", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("Deletion cancelled", result.stdout)
                self.assertEqual(
                    self.wos.chat_ids(),
                    ["session_001", "session_002", "session_003"],
                )

    def test_cancelling_the_menu_deletes_nothing(self):
        for answer in ("", "0"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat delete", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("Deletion cancelled", result.stdout)
                self.assertNotIn("permanently", result.stdout)
                self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_eof_never_deletes(self):
        for script in ("/chat delete\n", "/chat delete\n2\n",
                       "/chat delete session_002\n"):
            with self.subTest(script=script):
                result = self.wos.run(script)

                self.assertNoCrash(result)
                self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_ctrl_c_never_deletes_and_wos_keeps_running(self):
        for answers in (["/chat delete", "<CTRL-C>", "/status", "/exit"],
                        ["/chat delete", "2", "<CTRL-C>", "/status", "/exit"],
                        ["/chat delete session_002", "<CTRL-C>", "/status",
                         "/exit"]):
            with self.subTest(answers=answers):
                result = self.wos.run_scripted(answers)

                self.assertNoCrash(result)
                self.assertIn("Auralis Status", result.stdout)
                self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_invalid_numbers_ask_again_and_delete_nothing(self):
        result = self.wos.run(lines("/chat delete", "9", "zero", "0", "/exit"))

        self.assertNoCrash(result)
        self.assertEqual(
            result.stdout.count("Please enter a number from 1 to 3."), 2
        )
        self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_delete_by_id_still_asks_for_confirmation(self):
        declined = self.wos.run(lines("/chat delete session_001", "n", "/exit"))
        accepted = self.wos.run(lines("/chat delete session_001", "y", "/exit"))

        self.assertIn("Deletion cancelled", declined.stdout)
        self.assertIn("Deleted session_001", accepted.stdout)
        self.assertEqual(self.wos.chat_ids(), ["session_002", "session_003"])

    def test_deleting_the_active_chat_moves_to_another_saved_chat(self):
        result = self.wos.run(
            lines("/chat delete", "3", "y", "/status", "/exit")
        )

        self.assertNoCrash(result)
        self.assertIn("Deleted session_003", result.stdout)
        self.assertIn("Active session is now session_002", result.stdout)
        self.assertEqual(self.active_id(), "session_002")

    def test_deleting_the_last_chat_starts_a_fresh_one(self):
        self.wos.run(lines("/chat delete session_001", "y",
                           "/chat delete session_002", "y", "/exit"))

        result = self.wos.run(
            lines("/chat delete session_003", "y", "/exit")
        )

        self.assertNoCrash(result)
        self.assertEqual(len(self.wos.chat_ids()), 1)
        self.assertIn("Active session is now", result.stdout)

    def test_too_many_arguments_shows_usage(self):
        result = self.wos.run(lines("/chat delete session_001 session_002",
                                    "/exit"))

        self.assertIn("Usage: /chat delete [session_id]", result.stdout)
        self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_unknown_id_is_reported(self):
        result = self.wos.run(lines("/chat delete session_099", "/exit"))

        self.assertIn("Chat 'session_099' was not found.", result.stdout)
        self.assertIn("type /chat delete on its own", result.stdout)
        self.assertEqual(len(self.wos.chat_ids()), 3)

    def test_delete_alias_works_in_both_forms(self):
        interactive = self.wos.run(lines("/delete", "1", "y", "/exit"))
        direct = self.wos.run(lines("/delete session_002", "y", "/exit"))

        self.assertNoCrash(interactive)
        self.assertNoCrash(direct)
        self.assertEqual(self.wos.chat_ids(), ["session_003"])


# ------------------------------------------------------------------
# /chat clear
# ------------------------------------------------------------------

class ChatClearTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        self.wos.run("/exit\n")
        self.seed_messages("session_001", 4)

    def test_confirmation_prompt_names_the_chat_and_the_message_count(self):
        result = self.wos.run(lines("/chat clear", "n", "/exit"))

        self.assertIn(
            "Clear all 4 message(s) in 'Chat 1' (session_001)? "
            "This cannot be undone. (y/n)",
            result.stdout,
        )

    def test_yes_clears_the_messages_and_keeps_the_chat(self):
        result = self.wos.run(lines("/chat clear", "y", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Conversation cleared", result.stdout)
        self.assertEqual(self.message_count("session_001"), 0)
        self.assertEqual(self.wos.chat_ids(), ["session_001"])
        self.assertEqual(self.title("session_001"), "Chat 1")

    def test_cleared_chat_stays_cleared_after_a_restart(self):
        self.wos.run(lines("/chat clear", "yes", "/exit"))

        result = self.wos.run(lines("/chat clear", "/exit"))

        self.assertIn("no messages to clear", result.stdout)
        self.assertEqual(self.message_count("session_001"), 0)

    def test_anything_but_yes_keeps_the_messages(self):
        for answer in ("n", "no", "", "  ", "maybe", "yy", "ye"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(lines("/chat clear", answer, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("Clear cancelled", result.stdout)
                self.assertEqual(self.message_count("session_001"), 4)

    def test_eof_keeps_the_messages(self):
        result = self.wos.run("/chat clear\n")

        self.assertNoCrash(result)
        self.assertEqual(self.message_count("session_001"), 4)

    def test_ctrl_c_keeps_the_messages_and_wos_keeps_running(self):
        result = self.wos.run_scripted(
            ["/chat clear", "<CTRL-C>", "/status", "/exit"]
        )

        self.assertNoCrash(result)
        self.assertIn("Clear cancelled", result.stdout)
        self.assertIn("Auralis Status", result.stdout)
        self.assertEqual(self.message_count("session_001"), 4)

    def test_an_empty_chat_is_not_cleared_and_nothing_is_asked(self):
        self.wos.run(lines("/new", "/exit"))  # session_002, empty

        result = self.wos.run(lines("/chat clear", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("This chat has no messages to clear", result.stdout)
        self.assertNotIn("(y/n)", result.stdout)

    def test_only_the_active_chat_is_cleared(self):
        self.wos.run(lines("/new", "/exit"))  # session_002 becomes active
        self.seed_messages("session_002", 2)

        self.wos.run(lines("/chat clear", "y", "/exit"))

        self.assertEqual(self.message_count("session_002"), 0)
        self.assertEqual(self.message_count("session_001"), 4)

    def test_clear_alias_now_asks_for_confirmation_too(self):
        declined = self.wos.run(lines("/clear", "n", "/exit"))
        self.assertIn("Clear cancelled", declined.stdout)
        self.assertEqual(self.message_count("session_001"), 4)

        accepted = self.wos.run(lines("/clear", "y", "/exit"))
        self.assertIn("Conversation cleared", accepted.stdout)
        self.assertEqual(self.message_count("session_001"), 0)

    def test_clear_alias_eof_and_ctrl_c_keep_the_messages(self):
        eof = self.wos.run("/clear\n")
        ctrl_c = self.wos.run_scripted(["/clear", "<CTRL-C>", "/exit"])

        self.assertNoCrash(eof)
        self.assertNoCrash(ctrl_c)
        self.assertEqual(self.message_count("session_001"), 4)


# ------------------------------------------------------------------
# Chat limit and persistence still behave as before
# ------------------------------------------------------------------

class ChatLimitStillWorksTests(ChatTestCase):
    max_chats = 2

    def test_new_chat_is_still_blocked_at_the_limit(self):
        result = self.wos.run(lines("/new", "/new", "0", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Chat limit reached (2 saved chats)", result.stdout)
        self.assertEqual(self.wos.chat_ids(), ["session_001", "session_002"])

    def test_new_chat_after_choosing_a_chat_to_delete(self):
        result = self.wos.run(lines("/new", "/new", "1", "y", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("Deleted session_001", result.stdout)
        self.assertEqual(self.wos.chat_ids(), ["session_002", "session_003"])

    def test_chat_delete_frees_a_slot_for_new(self):
        self.make_chats(2)

        result = self.wos.run(
            lines("/chat delete session_001", "y", "/new", "/exit")
        )

        self.assertNoCrash(result)
        self.assertEqual(len(self.wos.chat_ids()), 2)


# ------------------------------------------------------------------
# /character switch uses the same numbered menu
# ------------------------------------------------------------------

class CharacterSwitchMenuTests(ChatTestCase):
    def setUp(self):
        super().setUp()
        path = self.wos.project / "characters" / "nexis.json"
        second = json.loads(path.read_text("utf-8"))
        second["id"] = "tester"
        second["name"] = "Tester"
        (self.wos.project / "characters" / "tester.json").write_text(
            json.dumps(second), encoding="utf-8"
        )

    def test_menu_switches_the_character(self):
        result = self.wos.run(
            lines("/character switch", "2", "/status", "/exit")
        )

        self.assertNoCrash(result)
        self.assertIn("1. nexis: Nexis (active)", result.stdout)
        self.assertIn("2. tester: Tester", result.stdout)
        self.assertRegex(result.stdout, r"Character:\s+Tester")
        self.assertEqual(
            self.wos.read_chat("session_001")["character_id"], "tester"
        )

    def test_cancelling_does_not_change_the_character(self):
        for answer in ("", "0"):
            with self.subTest(answer=repr(answer)):
                result = self.wos.run(
                    lines("/character switch", answer, "/exit")
                )

                self.assertNoCrash(result)
                self.assertIn("Character was not changed", result.stdout)
                self.assertEqual(
                    self.wos.read_chat("session_001")["character_id"],
                    "nexis",
                )

    def test_eof_and_ctrl_c_do_not_change_the_character(self):
        eof = self.wos.run("/character switch\n")
        ctrl_c = self.wos.run_scripted(
            ["/character switch", "<CTRL-C>", "/status", "/exit"]
        )

        self.assertNoCrash(eof)
        self.assertNoCrash(ctrl_c)
        self.assertIn("Auralis Status", ctrl_c.stdout)
        self.assertEqual(
            self.wos.read_chat("session_001")["character_id"], "nexis"
        )

    def test_switch_by_id_still_works(self):
        result = self.wos.run(lines("/character switch tester", "/exit"))

        self.assertNoCrash(result)
        self.assertNotIn("Number of the character", result.stdout)
        self.assertEqual(
            self.wos.read_chat("session_001")["character_id"], "tester"
        )


# ------------------------------------------------------------------
# /help
# ------------------------------------------------------------------

class HelpCommandTests(ChatTestCase):
    def overview(self):
        result = self.wos.run(lines("/help", "/exit"))
        self.assertNoCrash(result)

        out = result.stdout.splitlines()
        start = out.index("Auralis commands:") + 1
        entries = []

        for line in out[start:]:
            if not line.strip():
                break

            entries.append(line)

        return result.stdout, entries

    def test_help_lists_commands_alphabetically(self):
        _, entries = self.overview()
        names = [entry.split()[0] for entry in entries]

        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertIn("/chat", names)
        self.assertEqual(names[0], "/character")
        self.assertEqual(names[-1], "/switch")

    def test_help_lists_every_command_with_a_summary(self):
        from core.cli import KNOWN_COMMANDS

        _, entries = self.overview()
        names = [entry.split()[0] for entry in entries]

        self.assertEqual(sorted(names), sorted(KNOWN_COMMANDS))
        self.assertTrue(all(len(entry.split()) > 1 for entry in entries))

    def test_help_shows_old_commands_as_aliases(self):
        _, entries = self.overview()
        text = "\n".join(entries)

        self.assertRegex(text, r"/switch\s+Alias for /chat switch")
        self.assertRegex(text, r"/rename\s+Alias for /chat rename")
        self.assertRegex(text, r"/delete\s+Alias for /chat delete")
        self.assertRegex(text, r"/clear\s+Alias for /chat clear")
        self.assertRegex(text, r"/chats\s+Alias for /chat list")

    def test_help_points_to_command_help(self):
        out, _ = self.overview()

        self.assertIn("/help <command>", out)

    def test_help_chat_explains_the_command(self):
        result = self.wos.run(lines("/help chat", "/exit"))

        self.assertNoCrash(result)
        flat = " ".join(result.stdout.split())  # undo line wrapping
        for text in ("/chat - Manage saved chats", "Purpose:", "Usage:",
                     "Subcommands:", "/chat switch [id]",
                     "/chat rename [id] [new title]", "Older commands",
                     "Press Enter or type 0 to cancel"):
            with self.subTest(text=text):
                self.assertIn(text, flat)

    def test_help_model_and_provider(self):
        result = self.wos.run(lines("/help model", "/help provider", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("/model - Show or change the model", result.stdout)
        self.assertIn("/model <model>", result.stdout)
        self.assertIn("/provider - Show or change the provider", result.stdout)
        self.assertIn("/provider <provider> [model]", result.stdout)

    def test_help_accepts_a_leading_slash_and_any_case(self):
        plain = self.wos.run(lines("/help chat", "/exit")).stdout
        for form in ("/help /chat", "/HELP CHAT", "/help   Chat"):
            with self.subTest(form=form):
                result = self.wos.run(lines(form, "/exit"))

                self.assertNoCrash(result)
                self.assertIn("/chat - Manage saved chats", result.stdout)
        self.assertIn("/chat - Manage saved chats", plain)

    def test_help_for_a_subcommand(self):
        result = self.wos.run(lines("/help chat clear", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("/chat clear", result.stdout)
        self.assertIn("Saved memories are kept", " ".join(result.stdout.split()))

    def test_help_for_an_alias_points_to_the_canonical_command(self):
        result = self.wos.run(lines("/help switch", "/exit"))

        self.assertIn("/switch - Alias for /chat switch", result.stdout)
        self.assertIn("See also: /help chat", result.stdout)

    def test_help_for_every_listed_command_works(self):
        from core.cli import KNOWN_COMMANDS

        script = lines(*(f"/help {name}" for name in KNOWN_COMMANDS), "/exit")
        result = self.wos.run(script)

        self.assertNoCrash(result)
        self.assertNotIn("No help is available", result.stdout)
        for name in KNOWN_COMMANDS:
            with self.subTest(command=name):
                self.assertIn(f"{name} - ", result.stdout)

    def test_unknown_help_topic_suggests_a_command(self):
        result = self.wos.run(lines("/help chta", "/help zzzz", "/exit"))

        self.assertNoCrash(result)
        self.assertIn("No help is available for 'chta'", result.stdout)
        self.assertIn("Did you mean /help chat?", result.stdout)
        self.assertIn("No help is available for 'zzzz'", result.stdout)
        self.assertIn("Type /help to see all commands", result.stdout)
        self.assertNotIn("fake genai", result.stdout)


# ------------------------------------------------------------------
# Regression: older behavior that must not change
# ------------------------------------------------------------------

class RegressionTests(ChatTestCase):
    def test_other_commands_still_work(self):
        result = self.wos.run(lines(
            "/status", "/context", "/memory", "/defaults", "/provider", "0",
            "/model", "0", "/character", "/character list", "/exit",
        ))

        self.assertNoCrash(result)
        for text in ("Auralis Status", "Default provider:",
                     "Current provider: cloud",
                     "Current model: gemini-3.5-flash-lite",
                     "Active character: Nexis", "Available Characters"):
            with self.subTest(text=text):
                self.assertIn(text, result.stdout)

    def test_unknown_commands_are_still_blocked_from_the_ai(self):
        result = self.wos.run(lines("/foobar", "/chats extra", "/exit"))

        self.assertIn("Unknown command '/foobar'", result.stdout)
        self.assertIn("'/chats' was not used correctly", result.stdout)
        self.assertNotIn("fake genai", result.stdout)

    def test_normal_text_still_reaches_the_ai(self):
        result = self.wos.run(lines("hello there", "/exit"))

        self.assertIn("GEMINI_API_KEY", result.stdout)

    def test_new_chat_still_uses_the_defaults(self):
        result = self.wos.run(lines(
            "/defaults provider ollama llama3", "/new", "/status", "/exit"
        ))

        self.assertNoCrash(result)
        self.assertRegex(result.stdout, r"Provider:\s+ollama\s+Model:\s+llama3")

    def test_chat_files_keep_their_format(self):
        self.make_chats(2)
        self.wos.run(lines("/chat rename session_001 Renamed", "/exit"))

        chat = self.wos.read_chat("session_001")

        self.assertEqual(
            set(chat),
            {"session_id", "title", "created", "updated", "messages",
             "provider", "model", "character_id"},
        )
        self.assertEqual(chat["title"], "Renamed")


if __name__ == "__main__":
    unittest.main()
