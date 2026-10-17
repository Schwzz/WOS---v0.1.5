"""A UTF-8 BOM (added by some Windows editors) must not break the JSON files
people edit by hand: config.json, settings.json and character files."""
import json
import unittest

from tests.helpers import Sandbox, DEFAULT_CONFIG, DEFAULT_SETTINGS
from tests.test_start_integration import IntegrationTestCase

from core import character, config
from core.character import list_characters, list_skipped_characters

BOM = b"\xef\xbb\xbf"
GOOD = {"name": "Aria", "personality": "Cheerful and curious."}


def with_bom(data):
    text = json.dumps(data, indent=4) if not isinstance(data, str) else data

    return BOM + text.encode("utf-8")


class ConfigBomTests(unittest.TestCase):
    def test_config_with_a_bom_loads_like_one_without(self):
        with Sandbox() as sandbox:
            plain = config.load_config()
            sandbox.config_path.write_bytes(with_bom(DEFAULT_CONFIG))

            self.assertEqual(config.load_config(), plain)

    def test_settings_with_a_bom_load_like_ones_without(self):
        with Sandbox() as sandbox:
            settings = json.loads(json.dumps(DEFAULT_SETTINGS))
            settings["user_name"] = "Sam"
            sandbox.settings_path.write_text(json.dumps(settings),
                                             encoding="utf-8")
            plain = config.load_settings()

            sandbox.settings_path.write_bytes(with_bom(settings))

            self.assertEqual(config.load_settings(), plain)
            self.assertEqual(config.load_settings()["user_name"], "Sam")

    def test_a_bom_does_not_hide_real_problems_or_change_their_messages(self):
        bad_configs = [
            '{"provider": "cloud",}',                       # JSON typo
            '{"provider":"x","model":"m","character":"nexis"}',
            '{"provider":"cloud","model":"<model_name>","character":"nexis"}',
            '[]',
        ]

        for text in bad_configs:
            with self.subTest(config=text):
                messages = []

                for raw in (text.encode("utf-8"), BOM + text.encode("utf-8")):
                    with Sandbox() as sandbox:
                        sandbox.config_path.write_bytes(raw)

                        with self.assertRaises(ValueError) as caught:
                            config.load_config()

                        messages.append(str(caught.exception))

                self.assertEqual(messages[0], messages[1])

    def test_a_typo_after_a_bom_reports_its_real_position(self):
        with Sandbox() as sandbox:
            sandbox.settings_path.write_bytes(BOM + b'{"user_name": "x",}')

            with self.assertRaises(ValueError) as caught:
                config.load_settings()

        # Not "line 1, column 1", which is what a BOM used to cause.
        self.assertNotIn("column 1)", str(caught.exception))

    def test_saving_over_a_bom_file_writes_clean_valid_json(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_bytes(with_bom(DEFAULT_CONFIG))

            config.save_config({**config.load_config(), "model": "new-model"})

            raw = sandbox.config_path.read_bytes()
            self.assertFalse(raw.startswith(BOM))
            self.assertEqual(json.loads(raw)["model"], "new-model")

    def test_files_without_a_bom_are_unaffected(self):
        with Sandbox():
            self.assertEqual(config.load_config(), DEFAULT_CONFIG)
            self.assertEqual(config.load_settings()["sessions"]["max_chats"], 5)


class CharacterBomTests(unittest.TestCase):
    def test_a_character_with_a_bom_loads_like_one_without(self):
        with Sandbox() as sandbox:
            (sandbox.characters_dir / "plain.json").write_text(
                json.dumps(GOOD), encoding="utf-8")
            (sandbox.characters_dir / "bom.json").write_bytes(with_bom(GOOD))

            self.assertEqual(character.load_character("bom"),
                             character.load_character("plain"))

    def test_a_character_with_a_bom_is_listed_and_not_reported(self):
        with Sandbox() as sandbox:
            (sandbox.characters_dir / "aria.json").write_bytes(with_bom(GOOD))

            self.assertIn({"id": "aria", "name": "Aria"}, list_characters())
            self.assertEqual(list_skipped_characters(), [])

    def test_the_default_character_file_may_have_a_bom(self):
        with Sandbox() as sandbox:
            path = sandbox.characters_dir / "nexis.json"
            path.write_bytes(BOM + path.read_bytes())

            self.assertEqual(sandbox.make_session().character_name, "Nexis")

    def test_a_bom_character_with_a_mistake_gets_the_real_reason(self):
        with Sandbox() as sandbox:
            (sandbox.characters_dir / "aria.json").write_bytes(
                with_bom('{"name": "Aria"}'))

            reason = dict(list_skipped_characters())["aria.json"]

            self.assertIn("'personality'", reason)
            self.assertNotIn("invalid JSON", reason)


class WholeProgramTests(IntegrationTestCase):
    """start.py run for real, with BOM files and broken characters."""

    def add_bom(self, *relative_paths):
        for relative in relative_paths:
            path = self.wos.project / relative
            path.write_bytes(BOM + path.read_bytes())

    def test_wos_starts_when_every_hand_edited_file_has_a_bom(self):
        self.add_bom("config.json", "settings.json", "characters/nexis.json")

        result = self.wos.run("/status\n/exit\n")

        self.assertNoCrash(result)
        self.assertNotIn("Could not start", result.stdout)
        self.assertRegex(result.stdout, r"Character:\s+Nexis")

    def test_defaults_can_still_be_changed_on_a_bom_config(self):
        self.add_bom("config.json")

        result = self.wos.run("/defaults model another-model\n/exit\n")

        self.assertNoCrash(result)
        self.assertIn("Default settings saved.", result.stdout)
        self.assertEqual(
            json.loads(self.wos.config_path.read_text("utf-8"))["model"],
            "another-model",
        )

    def test_a_custom_character_with_a_bom_can_be_used(self):
        (self.wos.project / "characters" / "aria.json").write_bytes(
            with_bom(GOOD))

        result = self.wos.run(
            "/character list\n/character switch aria\n/status\n/exit\n")

        self.assertNoCrash(result)
        self.assertIn("aria: Aria", result.stdout)
        self.assertNotIn("Skipped files", result.stdout)
        self.assertRegex(result.stdout, r"Character:\s+Aria")


class CharacterListCommandTests(IntegrationTestCase):
    def add(self, name, content):
        path = self.wos.project / "characters" / name
        path.write_bytes(content if isinstance(content, bytes)
                         else content.encode("utf-8"))

    def listing(self):
        result = self.wos.run("/character list\n/exit\n")
        self.assertNoCrash(result)

        return result.stdout

    def test_skipped_files_are_listed_with_their_reasons(self):
        self.add("trailing.json", '{"name": "T", "personality": "x",}')
        self.add("nopers.json", '{"name": "N"}')
        self.add("Aria Two.json", json.dumps(GOOD))
        self.add("cute.json.txt", json.dumps(GOOD))

        out = self.listing()

        self.assertIn("Skipped files (they cannot be used until fixed):", out)
        self.assertIn("trailing.json: contains invalid JSON (line 1, column",
                      out)
        self.assertIn("nopers.json: must have a non-empty string or object "
                      "for 'personality'.", out)
        self.assertIn("Aria Two.json: invalid file name", out)
        self.assertIn("cute.json.txt: not a .json file", out)

    def test_valid_characters_still_list_as_before(self):
        self.add("aria.json", json.dumps(GOOD))
        self.add("broken.json", "{")

        out = self.listing()

        self.assertIn("Available Characters\n--------------------\n"
                      "aria: Aria\nnexis: Nexis (active)\n", out)
        self.assertNotIn("No valid characters found.", out)

    def test_nothing_is_added_when_every_file_is_fine(self):
        self.add("aria.json", json.dumps(GOOD))
        self.add("Thumbs.db", "x")
        self.add("notes.txt", "x")

        out = self.listing()

        self.assertNotIn("Skipped files", out)
        self.assertIn("aria: Aria", out)

    def test_skipped_files_are_not_offered_in_the_switch_menu(self):
        self.add("aria.json", json.dumps(GOOD))
        self.add("broken.json", "{")

        result = self.wos.run("/character switch\n0\n/exit\n")

        self.assertNoCrash(result)
        self.assertIn("1. aria: Aria", result.stdout)
        self.assertIn("2. nexis: Nexis (active)", result.stdout)
        self.assertNotIn("broken", result.stdout)

    def test_switching_to_a_broken_character_still_explains_itself(self):
        self.add("trailing.json", '{"name": "T", "personality": "x",}')

        result = self.wos.run("/character switch trailing\n/exit\n")

        self.assertNoCrash(result)
        self.assertIn("Couldn't switch character", result.stdout)
        self.assertIn("contains invalid JSON", result.stdout)

    def test_help_mentions_the_skipped_file_report(self):
        result = self.wos.run("/help character\n/exit\n")

        self.assertIn("says which file and why",
                      " ".join(result.stdout.split()))


if __name__ == "__main__":
    unittest.main()
