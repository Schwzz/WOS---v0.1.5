import unittest
from unittest import mock

from tests import helpers  # noqa: F401  (sets up import paths)

from core import cli, help_text

# start.py paints any output line containing one of these phrases red, as an
# error. Help text must never contain them by accident. Keep this list in sync
# with color_for_line() in start.py.
RED_PHRASES = (
    "error:", "failed", "could not", "couldn't", "not found",
    "did not return", "unsupported provider", "unknown provider",
    "unknown command", "limit reached", "invalid ", "is not installed",
)


class HelpTableTests(unittest.TestCase):
    def test_help_covers_exactly_the_known_commands(self):
        self.assertEqual(
            set(help_text.HELP_TOPICS), set(cli.KNOWN_COMMANDS)
        )

    def test_every_entry_has_the_required_fields(self):
        for name, entry in help_text.HELP_TOPICS.items():
            with self.subTest(command=name):
                self.assertTrue(entry["summary"].strip())
                self.assertTrue(entry["purpose"].strip())
                self.assertTrue(entry["usage"])
                self.assertTrue(entry["examples"])
                self.assertIsInstance(entry["subcommands"], list)

                for example in entry["examples"]:
                    self.assertTrue(example.startswith("/"), example)

                for usage in entry["usage"]:
                    self.assertTrue(usage.startswith("/"), usage)

    def test_every_subcommand_appears_in_the_usage_list(self):
        for name, entry in help_text.HELP_TOPICS.items():
            for sub_name, usage, description in entry["subcommands"]:
                with self.subTest(command=name, subcommand=sub_name):
                    self.assertIn(usage, entry["usage"])
                    self.assertTrue(usage.startswith(f"{name} {sub_name}"))
                    self.assertTrue(description.strip())

    def test_aliases_point_to_real_commands(self):
        for name, entry in help_text.HELP_TOPICS.items():
            canonical = entry.get("canonical")

            if canonical is None:
                continue

            with self.subTest(alias=name):
                self.assertIn(canonical.split()[0], help_text.HELP_TOPICS)
                self.assertIn(canonical, entry["summary"])

    def test_chat_documents_every_old_command_as_an_alias(self):
        chat = help_text.HELP_TOPICS["/chat"]
        documented = dict(chat["aliases"])

        self.assertEqual(documented, {
            "/chats": "/chat list",
            "/switch": "/chat switch",
            "/rename": "/chat rename",
            "/delete": "/chat delete",
            "/clear": "/chat clear",
        })

        for old, new in documented.items():
            with self.subTest(alias=old):
                self.assertIn(old, help_text.HELP_TOPICS)

    def test_chat_subcommands_match_the_canonical_list(self):
        names = [n for n, _, _ in help_text.HELP_TOPICS["/chat"]["subcommands"]]

        self.assertEqual(
            names, ["list", "switch", "rename", "delete", "clear"]
        )

    def test_help_text_never_triggers_the_red_error_coloring(self):
        everything = list(help_text.overview_lines())

        for name in help_text.HELP_TOPICS:
            everything += help_text.help_lines(name)

            for sub_name, _, _ in help_text.HELP_TOPICS[name]["subcommands"]:
                everything += help_text.help_lines(f"{name} {sub_name}")

        for line in everything:
            with self.subTest(line=line):
                lowered = line.lower()
                self.assertFalse(
                    any(phrase in lowered for phrase in RED_PHRASES)
                )

    def test_lines_fit_a_normal_terminal(self):
        for name in help_text.HELP_TOPICS:
            for line in help_text.help_lines(name):
                with self.subTest(command=name, line=line):
                    self.assertLessEqual(len(line), 79)


class OverviewTests(unittest.TestCase):
    def listed_commands(self):
        lines = help_text.overview_lines()
        start = lines.index("Auralis commands:") + 1
        commands = []

        for line in lines[start:]:
            if not line.strip():
                break

            commands.append(line.split()[0])

        return commands

    def test_commands_are_listed_alphabetically(self):
        commands = self.listed_commands()

        self.assertEqual(commands, sorted(commands, key=str.lower))
        self.assertEqual(commands, help_text.command_names())

    def test_sorting_does_not_depend_on_the_order_of_the_table(self):
        # The real table happens to be written alphabetically, so prove the
        # list is sorted by feeding it a scrambled one (mixed case included).
        entry = {"summary": "x"}
        scrambled = {
            "/zebra": entry, "/Mango": entry, "/apple": entry,
            "/banana": entry, "/Cherry": entry,
        }

        with mock.patch.object(help_text, "HELP_TOPICS", scrambled):
            lines = help_text.overview_lines()

        start = lines.index("Auralis commands:") + 1
        names = [line.split()[0] for line in lines[start:] if line.strip()][:5]

        self.assertEqual(
            names, ["/apple", "/banana", "/Cherry", "/Mango", "/zebra"]
        )

    def test_every_command_is_listed_once(self):
        commands = self.listed_commands()

        self.assertEqual(len(commands), len(set(commands)))
        self.assertEqual(set(commands), set(cli.KNOWN_COMMANDS))

    def test_each_line_has_a_summary(self):
        lines = help_text.overview_lines()
        start = lines.index("Auralis commands:") + 1

        for line in lines[start:]:
            if not line.strip():
                break

            name = line.split()[0]
            self.assertIn(help_text.HELP_TOPICS[name]["summary"], line)

    def test_points_the_user_at_command_help(self):
        self.assertTrue(
            any("/help <command>" in line
                for line in help_text.overview_lines())
        )

    def test_columns_line_up(self):
        lines = help_text.overview_lines()
        start = lines.index("Auralis commands:") + 1
        columns = set()

        for line in lines[start:]:
            if not line.strip():
                break

            name = line.split()[0]
            summary = help_text.HELP_TOPICS[name]["summary"]
            columns.add(line.index(summary))

        self.assertEqual(len(columns), 1)


class CommandHelpTests(unittest.TestCase):
    def text(self, arguments):
        return "\n".join(help_text.help_lines(arguments))

    def test_chat_help_explains_purpose_usage_and_subcommands(self):
        text = self.text("chat")

        self.assertIn("/chat - Manage saved chats", text)
        self.assertIn("Purpose:", text)
        self.assertIn("Usage:", text)
        self.assertIn("Subcommands:", text)
        self.assertIn("Examples:", text)

        for usage in ("/chat list", "/chat switch [id]",
                      "/chat rename [id] [new title]",
                      "/chat delete [id]", "/chat clear"):
            with self.subTest(usage=usage):
                self.assertIn(usage, text)

    def test_chat_help_lists_the_older_commands(self):
        text = self.text("chat")

        self.assertIn("Older commands that still work:", text)
        self.assertIn("/switch", text)
        self.assertIn("same as /chat switch", text)

    def test_model_and_provider_help(self):
        model = self.text("model")
        provider = self.text("provider")

        self.assertIn("/model <model>", model)
        self.assertIn("current chat only", model)
        self.assertIn("/provider <provider> [model]", provider)
        self.assertIn("/defaults", model)

    def test_topic_matching_ignores_case_and_leading_slash(self):
        expected = self.text("chat")

        for form in ("chat", "/chat", "CHAT", "/Chat", "  chat  "):
            with self.subTest(form=form):
                self.assertEqual(self.text(form), expected)

    def test_subcommand_help(self):
        text = self.text("chat switch")

        self.assertIn("/chat switch [id]", text)
        self.assertIn("numbered list", text)
        self.assertNotIn("Subcommands:", text)

    def test_every_command_and_subcommand_has_help(self):
        for name, entry in help_text.HELP_TOPICS.items():
            with self.subTest(command=name):
                self.assertTrue(help_text.help_lines(name))

            for sub_name, _, _ in entry["subcommands"]:
                with self.subTest(command=name, subcommand=sub_name):
                    self.assertTrue(help_text.help_lines(f"{name} {sub_name}"))

    def test_alias_help_names_the_canonical_command(self):
        for alias, canonical in (("switch", "/chat switch"),
                                 ("rename", "/chat rename"),
                                 ("delete", "/chat delete"),
                                 ("clear", "/chat clear"),
                                 ("chats", "/chat list"),
                                 ("quit", "/exit")):
            with self.subTest(alias=alias):
                text = self.text(alias)

                self.assertIn(f"Alias for {canonical}", text)
                self.assertIn("See also: /help", text)

    def test_unknown_topics_return_none(self):
        for arguments in ("", "   ", "nonsense", "/nope",
                          "chat nosuchsub", "chat list extra words",
                          "model switch"):
            with self.subTest(arguments=arguments):
                self.assertIsNone(help_text.help_lines(arguments))


class SuggestionTests(unittest.TestCase):
    def test_close_misspellings_are_suggested(self):
        self.assertEqual(help_text.suggest_topic("chta"), "/chat")
        self.assertEqual(help_text.suggest_topic("/modle"), "/model")
        self.assertEqual(help_text.suggest_topic("provder"), "/provider")

    def test_unrelated_text_gets_no_suggestion(self):
        self.assertIsNone(help_text.suggest_topic("zzzzzz"))
        self.assertIsNone(help_text.suggest_topic(""))


if __name__ == "__main__":
    unittest.main()
