import contextlib
import io
import unittest

from tests import helpers  # noqa: F401  (sets up import paths)

from core import cli


def reader_returning(text):
    return lambda prompt: text


def reader_raising(error):
    def reader(prompt):
        raise error

    return reader


class QuietTestCase(unittest.TestCase):
    """Hide the blank line read_input prints when input is cancelled."""

    def setUp(self):
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(stack.close)


class ReadInputTests(QuietTestCase):
    def test_returns_the_typed_text(self):
        self.assertEqual(cli.read_input("? ", reader_returning("hi")), "hi")

    def test_ctrl_c_returns_none_instead_of_raising(self):
        reader = reader_raising(KeyboardInterrupt())
        self.assertIsNone(cli.read_input("? ", reader))

    def test_eof_returns_none_instead_of_raising(self):
        reader = reader_raising(EOFError())
        self.assertIsNone(cli.read_input("? ", reader))


class ConfirmTests(QuietTestCase):
    def test_only_explicit_yes_confirms(self):
        for answer in ("y", "Y", "yes", " YES "):
            with self.subTest(answer=answer):
                self.assertTrue(cli.confirm("? ", reader_returning(answer)))

    def test_everything_else_declines(self):
        for answer in ("n", "no", "", "  ", "maybe", "yy", "ye"):
            with self.subTest(answer=answer):
                self.assertFalse(cli.confirm("? ", reader_returning(answer)))

    def test_ctrl_c_and_eof_decline_safely(self):
        for error in (KeyboardInterrupt(), EOFError()):
            with self.subTest(error=type(error).__name__):
                self.assertFalse(
                    cli.confirm("? ", reader_raising(error))
                )


class UnrecognizedCommandTests(unittest.TestCase):
    def test_unknown_command_gets_an_error(self):
        message = cli.check_unrecognized_command("/foobar something")

        self.assertIn("Unknown command '/foobar'", message)
        self.assertIn("/help", message)

    def test_typo_gets_a_suggestion(self):
        message = cli.check_unrecognized_command("/modle gemini")

        self.assertIn("Did you mean /model?", message)

    def test_command_matching_is_case_insensitive(self):
        message = cli.check_unrecognized_command("/MODLE x")

        self.assertIn("'/modle'", message)

    def test_known_command_with_unexpected_arguments_is_reported(self):
        for text in ("/new please", "/chats all", "/exit now", "/help me"):
            with self.subTest(text=text):
                message = cli.check_unrecognized_command(text)

                self.assertIn("was not used correctly", message)

    def test_normal_chat_is_not_treated_as_a_command(self):
        for text in (
            "hello there",
            "what does /usr/bin/python do?",
            "/usr/bin/python",
            "/ hello",
            "//",
            "see /help for more",
            "",
        ):
            with self.subTest(text=text):
                self.assertIsNone(cli.check_unrecognized_command(text))

    def test_every_known_command_is_a_valid_command_word(self):
        for command in cli.KNOWN_COMMANDS:
            with self.subTest(command=command):
                self.assertTrue(cli._COMMAND_WORD.fullmatch(command))


if __name__ == "__main__":
    unittest.main()
