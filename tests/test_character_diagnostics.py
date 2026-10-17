import json
import unittest
from unittest import mock

from tests.helpers import Sandbox

from core import character
from core.character import list_characters, list_skipped_characters

GOOD = {"name": "Aria", "personality": "Cheerful and curious."}


def write(sandbox, name, content):
    path = sandbox.characters_dir / name

    if isinstance(content, bytes):
        path.write_bytes(content)
    elif isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(json.dumps(content), encoding="utf-8")

    return path


def reasons(sandbox):
    return dict(list_skipped_characters())


class ValidCharactersTests(unittest.TestCase):
    def test_valid_characters_are_listed_and_never_reported(self):
        with Sandbox() as sandbox:
            write(sandbox, "aria.json", GOOD)

            self.assertEqual(
                [c["id"] for c in list_characters()],
                ["aria", "nexis", "tester"],
            )
            self.assertEqual(list_skipped_characters(), [])

    def test_the_listing_format_is_unchanged(self):
        with Sandbox():
            self.assertEqual(
                list_characters(),
                [{"id": "nexis", "name": "Nexis"},
                 {"id": "tester", "name": "Tester"}],
            )

    def test_a_bad_file_does_not_stop_the_good_ones_from_listing(self):
        with Sandbox() as sandbox:
            write(sandbox, "broken.json", "{")

            self.assertEqual(
                [c["id"] for c in list_characters()], ["nexis", "tester"]
            )
            self.assertEqual(list(reasons(sandbox)), ["broken.json"])


class SkipReasonTests(unittest.TestCase):
    # (file name, content, text the reason must contain)
    CASES = [
        # invalid JSON
        ("trailing.json", '{"name": "A", "personality": "x",}',
         "contains invalid JSON (line 1, column"),
        ("empty.json", "", "contains invalid JSON"),
        ("truncated.json", '{"name": "A"', "contains invalid JSON"),
        ("array.json", "[]", "must contain a JSON object"),
        # missing required fields
        ("noname.json", {"personality": "x"}, "'name'"),
        ("blankname.json", {"name": "  ", "personality": "x"}, "'name'"),
        ("nopers.json", {"name": "A"}, "'personality'"),
        ("emptypers.json", {"name": "A", "personality": " "}, "'personality'"),
        ("nocore.json", {"name": "A", "personality": {"style": "x"}},
         "'personality.core'"),
        # invalid values
        ("color.json", {**GOOD, "terminal": {"name_color": "pink"}},
         "unsupported terminal name color"),
        ("greeting.json", {**GOOD, "greeting": 5}, "'greeting'"),
        ("meta.json", {**GOOD, "metadata": "text"},
         "field 'metadata' must be a JSON object"),
        # invalid file names
        ("Aria Two.json", GOOD, "invalid file name"),
        ("aria!.json", GOOD, "invalid file name"),
        ("my.char.json", GOOD, "invalid file name"),
        ("caf\u00e9.json", GOOD, "invalid file name"),
        # not a .json file at all (Windows hides the real ending)
        ("aria.json.txt", GOOD, "not a .json file"),
        ("aria.json.bak", GOOD, "not a .json file"),
        # saved as Windows ANSI instead of UTF-8
        ("ansi.json", '{"name":"Zo\u00e9","personality":"x"}'.encode("cp1252"),
         "not saved as UTF-8"),
    ]

    def test_every_problem_is_reported_with_a_clear_reason(self):
        for file_name, content, expected in self.CASES:
            with self.subTest(file=file_name):
                with Sandbox() as sandbox:
                    write(sandbox, file_name, content)

                    found = reasons(sandbox)

                    self.assertIn(file_name, found)
                    self.assertIn(expected, found[file_name])

    def test_reported_files_are_never_listed_as_usable(self):
        for file_name, content, _ in self.CASES:
            with self.subTest(file=file_name):
                with Sandbox() as sandbox:
                    write(sandbox, file_name, content)

                    ids = [c["id"] for c in list_characters()]

                    self.assertEqual(ids, ["nexis", "tester"])

    def test_reasons_are_plain_text_for_the_user(self):
        with Sandbox() as sandbox:
            for file_name, content, _ in self.CASES:
                write(sandbox, file_name, content)

            for file_name, reason in list_skipped_characters():
                with self.subTest(file=file_name):
                    self.assertNotIn("WLLM", reason)
                    self.assertNotIn("Character '", reason)
                    self.assertNotIn("\n", reason)
                    self.assertTrue(reason.strip())

    def test_an_unreadable_file_is_explained(self):
        with Sandbox() as sandbox:
            write(sandbox, "locked.json", GOOD)

            with mock.patch.object(
                character, "load_character",
                side_effect=PermissionError(13, "Permission denied"),
            ):
                found = reasons(sandbox)

            self.assertIn("could not be read (Permission denied).",
                          found["locked.json"])

    def test_each_file_is_reported_once_and_in_a_stable_order(self):
        with Sandbox() as sandbox:
            for name in ("zeta.json", "alpha.json", "mid.json"):
                write(sandbox, name, "{")

            first = list_skipped_characters()
            second = list_skipped_characters()

            self.assertEqual([n for n, _ in first],
                             ["alpha.json", "mid.json", "zeta.json"])
            self.assertEqual(first, second)


class IgnoredFilesTests(unittest.TestCase):
    def test_files_that_are_not_character_attempts_are_ignored(self):
        with Sandbox() as sandbox:
            for name in ("Thumbs.db", "desktop.ini", "notes.txt",
                         "README.md", ".DS_Store", ".hidden.json"):
                write(sandbox, name, "anything")

            (sandbox.characters_dir / "folder").mkdir()
            (sandbox.characters_dir / "folder.json").mkdir()

            self.assertEqual(list_skipped_characters(), [])

    def test_a_missing_characters_folder_gives_an_empty_report(self):
        with Sandbox() as sandbox:
            for path in sandbox.characters_dir.iterdir():
                path.unlink()
            sandbox.characters_dir.rmdir()

            self.assertEqual(list_skipped_characters(), [])
            self.assertEqual(list_characters(), [])

    def test_reporting_never_changes_the_files(self):
        with Sandbox() as sandbox:
            write(sandbox, "broken.json", "{")
            before = {p.name: p.read_bytes()
                      for p in sandbox.characters_dir.iterdir()}

            list_skipped_characters()

            after = {p.name: p.read_bytes()
                     for p in sandbox.characters_dir.iterdir()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
