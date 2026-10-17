import contextlib
import io
import unittest
from unittest import mock

from tests import helpers  # noqa: F401  (sets up import paths)

from core.cli import select_option


class ScriptedReader:
    """Returns the scripted answers in order. An answer that is an exception
    is raised instead, which simulates Ctrl+C or the end of input."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)

        if not self.answers:
            raise AssertionError("The menu asked for more input than expected.")

        answer = self.answers.pop(0)

        if isinstance(answer, BaseException):
            raise answer

        return answer


class MenuTestCase(unittest.TestCase):
    def setUp(self):
        # read_input prints a blank line when input is cancelled; hide it.
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.addCleanup(stack.close)

    def choose(self, options, *answers, **kwargs):
        reader = ScriptedReader(*answers)
        lines = []
        result = select_option(
            options,
            reader=reader,
            writer=lambda text="": lines.append(text),
            **kwargs,
        )
        return result, reader, lines


class ValidSelectionTests(MenuTestCase):
    def test_selecting_by_number_returns_the_zero_based_index(self):
        for answer, expected in (("1", 0), ("2", 1), ("3", 2)):
            with self.subTest(answer=answer):
                result, _, _ = self.choose(["a", "b", "c"], answer)

                self.assertEqual(result, expected)

    def test_surrounding_spaces_and_leading_zeros_are_accepted(self):
        for answer in (" 2 ", "02", "\t2\n"):
            with self.subTest(answer=repr(answer)):
                result, _, _ = self.choose(["a", "b", "c"], answer)

                self.assertEqual(result, 1)

    def test_the_caller_can_use_the_index_to_find_the_item(self):
        options = ["first", "second", "third"]

        result, _, _ = self.choose(options, "3")

        self.assertEqual(options[result], "third")

    def test_a_single_option_can_be_selected(self):
        result, _, _ = self.choose(["only"], "1")

        self.assertEqual(result, 0)

    def test_large_menus_work(self):
        options = [f"item {n}" for n in range(1, 13)]

        result, _, _ = self.choose(options, "12")

        self.assertEqual(result, 11)

    def test_accepts_any_iterable_and_does_not_change_the_input(self):
        options = ("a", "b")

        result, _, _ = self.choose(options, "2")
        generated, _, _ = self.choose((x for x in "ab"), "1")

        self.assertEqual(result, 1)
        self.assertEqual(generated, 0)
        self.assertEqual(options, ("a", "b"))

    def test_only_one_question_is_asked_when_the_first_answer_is_valid(self):
        _, reader, _ = self.choose(["a", "b"], "1")

        self.assertEqual(len(reader.prompts), 1)


class DisplayTests(MenuTestCase):
    def test_lists_numbered_options_under_an_underlined_title(self):
        _, _, lines = self.choose(
            ["Alpha", "Beta"], "1", title="Pick One"
        )

        self.assertEqual(lines, [
            "", "Pick One", "--------", "1. Alpha", "2. Beta", "",
        ])

    def test_title_is_optional(self):
        _, _, lines = self.choose(["Alpha"], "1")

        self.assertEqual(lines, ["", "1. Alpha", ""])

    def test_numbers_line_up_when_there_are_ten_or_more_options(self):
        _, _, lines = self.choose([f"x{n}" for n in range(1, 11)], "1")

        self.assertIn(" 1. x1", lines)
        self.assertIn("10. x10", lines)

    def test_labels_are_flattened_to_one_line_and_converted_to_text(self):
        _, _, lines = self.choose(["two\nlines\tand   gaps", 42, None], "1")

        self.assertIn("1. two lines and gaps", lines)
        self.assertIn("2. 42", lines)
        self.assertIn("3. None", lines)

    def test_default_prompt_explains_how_to_choose_and_cancel(self):
        _, reader, _ = self.choose(["a", "b", "c"], "1")

        self.assertEqual(
            reader.prompts[0],
            "WOS: Enter a number (1-3, Enter or 0 to cancel): ",
        )

    def test_prompt_for_a_single_option_does_not_show_a_range(self):
        _, reader, _ = self.choose(["a"], "1")

        self.assertIn("(1, Enter or 0 to cancel)", reader.prompts[0])

    def test_prompt_without_cancel_does_not_mention_cancelling(self):
        _, reader, _ = self.choose(["a", "b"], "1", allow_cancel=False)

        self.assertEqual(reader.prompts[0], "WOS: Enter a number (1-2): ")

    def test_custom_prompt_is_used(self):
        _, reader, _ = self.choose(
            ["a", "b"], "1", prompt="WOS: Which chat? "
        )

        self.assertEqual(reader.prompts, ["WOS: Which chat? "])


class InvalidInputTests(MenuTestCase):
    def test_invalid_input_explains_and_asks_again(self):
        bad_answers = [
            "abc", "9", "4", "-1", "1.5", "1 2", "0x1",
            "\u00b2",       # superscript two looks like a digit but is not one
            "\u0663",       # Arabic-Indic digit three
            "one", "+1",
        ]

        result, reader, lines = self.choose(["a", "b", "c"], *bad_answers, "2")

        self.assertEqual(result, 1)
        self.assertEqual(len(reader.prompts), len(bad_answers) + 1)

        messages = [l for l in lines if l.startswith("WOS: Please enter")]
        self.assertEqual(len(messages), len(bad_answers))
        self.assertTrue(
            all(m == "WOS: Please enter a number from 1 to 3." for m in messages)
        )

    def test_invalid_input_never_returns_a_choice(self):
        result, _, _ = self.choose(["a", "b"], "7", "x", "")

        # The empty answer at the end is what finally cancels.
        self.assertIsNone(result)

    def test_message_for_a_single_option(self):
        _, _, lines = self.choose(["only"], "2", "1")

        self.assertIn("WOS: Please enter 1.", lines)

    def test_zero_is_not_a_choice_when_cancelling_is_not_allowed(self):
        result, reader, lines = self.choose(
            ["a", "b"], "0", "", "  ", "2", allow_cancel=False
        )

        self.assertEqual(result, 1)
        self.assertEqual(len(reader.prompts), 4)
        self.assertEqual(
            lines.count("WOS: Please enter a number from 1 to 2."), 3
        )


class CancellationTests(MenuTestCase):
    def test_enter_cancels(self):
        for answer in ("", "   ", "\n"):
            with self.subTest(answer=repr(answer)):
                result, reader, _ = self.choose(["a", "b"], answer)

                self.assertIsNone(result)
                self.assertEqual(len(reader.prompts), 1)

    def test_zero_cancels(self):
        for answer in ("0", " 0 ", "00"):
            with self.subTest(answer=repr(answer)):
                result, _, _ = self.choose(["a", "b"], answer)

                self.assertIsNone(result)

    def test_cancelling_after_an_invalid_attempt_still_works(self):
        result, reader, _ = self.choose(["a", "b"], "nope", "0")

        self.assertIsNone(result)
        self.assertEqual(len(reader.prompts), 2)

    def test_nothing_to_choose_from_returns_none_without_asking(self):
        for options in ([], (), iter(())):
            with self.subTest(options=type(options).__name__):
                result, reader, lines = self.choose(options)

                self.assertIsNone(result)
                self.assertEqual(reader.prompts, [])
                self.assertEqual(
                    lines, ["WOS: There is nothing to choose from."]
                )


class InterruptTests(MenuTestCase):
    def test_ctrl_c_returns_none_instead_of_raising(self):
        result, _, _ = self.choose(["a", "b"], KeyboardInterrupt())

        self.assertIsNone(result)

    def test_eof_returns_none_instead_of_raising(self):
        result, _, _ = self.choose(["a", "b"], EOFError())

        self.assertIsNone(result)

    def test_ctrl_c_and_eof_work_after_an_invalid_attempt(self):
        for error in (KeyboardInterrupt(), EOFError()):
            with self.subTest(error=type(error).__name__):
                result, reader, _ = self.choose(["a", "b"], "zzz", error)

                self.assertIsNone(result)
                self.assertEqual(len(reader.prompts), 2)

    def test_ctrl_c_and_eof_still_end_the_menu_when_cancel_is_disabled(self):
        for error in (KeyboardInterrupt(), EOFError()):
            with self.subTest(error=type(error).__name__):
                result, _, _ = self.choose(
                    ["a", "b"], error, allow_cancel=False
                )

                self.assertIsNone(result)

    def test_other_errors_are_not_hidden(self):
        reader = ScriptedReader(RuntimeError("boom"))

        with self.assertRaises(RuntimeError):
            select_option(["a"], reader=reader, writer=lambda text="": None)


class DefaultInputOutputTests(MenuTestCase):
    def test_uses_input_and_print_when_none_are_given(self):
        output = io.StringIO()

        with mock.patch("builtins.input", return_value="2") as fake_input:
            with contextlib.redirect_stdout(output):
                result = select_option(["a", "b"], title="Choices")

        self.assertEqual(result, 1)
        fake_input.assert_called_once()
        self.assertIn("Choices", output.getvalue())
        self.assertIn("1. a", output.getvalue())
        self.assertIn("2. b", output.getvalue())

    def test_default_input_handles_ctrl_c_and_eof(self):
        for error in (KeyboardInterrupt, EOFError):
            with self.subTest(error=error.__name__):
                with mock.patch("builtins.input", side_effect=error):
                    result = select_option(["a", "b"])

                self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
