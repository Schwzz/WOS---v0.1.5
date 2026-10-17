import json
import unittest

from tests.helpers import Sandbox, DEFAULT_CONFIG

from core import config
from core.config import DEFAULT_PROVIDER_MODELS, get_suggested_models


class SuggestedModelsConfigTests(unittest.TestCase):
    def test_returns_the_models_listed_for_a_provider(self):
        cfg = {"suggested_models": {"cloud": ["model-a", "model-b"],
                                    "ollama": ["llama3:8b"]}}

        self.assertEqual(get_suggested_models(cfg, "cloud"),
                         ["model-a", "model-b"])
        self.assertEqual(get_suggested_models(cfg, "ollama"), ["llama3:8b"])

    def test_missing_or_malformed_settings_give_an_empty_list(self):
        for cfg in ({}, {"suggested_models": None},
                    {"suggested_models": "text"},
                    {"suggested_models": ["a"]},
                    {"suggested_models": {"cloud": "model-a"}},
                    {"suggested_models": {"other": ["x"]}},
                    "not a dict", None):
            with self.subTest(config=repr(cfg)):
                self.assertEqual(get_suggested_models(cfg, "cloud"), [])

    def test_invalid_entries_are_ignored_and_duplicates_removed(self):
        cfg = {"suggested_models": {"cloud": [
            "good-1", "<model_name>", "has space", "", None, 7,
            "good-1", "  good-2  ",
        ]}}

        self.assertEqual(get_suggested_models(cfg, "cloud"),
                         ["good-1", "good-2"])

    def test_extra_config_keys_survive_save_config(self):
        with Sandbox() as sandbox:
            data = {**DEFAULT_CONFIG,
                    "suggested_models": {"cloud": ["model-a"]}}
            config.save_config(data)

            self.assertEqual(
                sandbox.read_config()["suggested_models"],
                {"cloud": ["model-a"]},
            )

    def test_a_config_with_suggestions_still_loads(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_text(json.dumps(
                {**DEFAULT_CONFIG, "suggested_models": {"cloud": ["m"]}}
            ), encoding="utf-8")

            self.assertEqual(config.load_config()["suggested_models"],
                             {"cloud": ["m"]})


class KnownModelsTests(unittest.TestCase):
    def test_a_fresh_install_knows_only_the_shipped_default(self):
        with Sandbox() as sandbox:
            session = sandbox.make_session()

            self.assertEqual(session.known_models("cloud"),
                             [DEFAULT_CONFIG["model"]])
            self.assertEqual(session.known_models("ollama"), [])

    def test_nothing_is_invented_for_ollama(self):
        self.assertNotIn("ollama", DEFAULT_PROVIDER_MODELS)

    def test_every_name_comes_from_a_real_source(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_text(json.dumps({
                **DEFAULT_CONFIG,
                "suggested_models": {"cloud": ["from-config"]},
            }), encoding="utf-8")
            session = sandbox.make_session()
            session.change_model("current-model")
            session.new_chat()
            session.change_model("used-in-a-chat")
            session._provider_models["cloud"] = "remembered"

            known = session.known_models("cloud")

        sources = {"current-model", "from-config", "used-in-a-chat",
                   "remembered", DEFAULT_CONFIG["model"]}
        self.assertEqual(set(known), sources)

    def test_current_model_comes_first_then_the_default(self):
        with Sandbox() as sandbox:
            session = sandbox.make_session()
            session.change_model("current-model")

            known = session.known_models("cloud")

            self.assertEqual(known[0], "current-model")
            self.assertEqual(known[1], DEFAULT_CONFIG["model"])

    def test_names_are_listed_once(self):
        with Sandbox() as sandbox:
            session = sandbox.make_session()
            session.change_model(DEFAULT_CONFIG["model"])
            session.new_chat()

            known = session.known_models("cloud")

            self.assertEqual(known, [DEFAULT_CONFIG["model"]])

    def test_models_from_saved_chats_are_offered_for_that_provider_only(self):
        with Sandbox() as sandbox:
            session = sandbox.make_session()
            session.change_provider("ollama", "llama3")
            session.save_defaults(provider="cloud")
            session.new_chat()

            self.assertIn("llama3", session.known_models("ollama"))
            self.assertNotIn("llama3", session.known_models("cloud"))

    def test_invalid_names_are_never_offered(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_text(json.dumps({
                **DEFAULT_CONFIG,
                "suggested_models": {"cloud": ["<model_name>", "a b"]},
            }), encoding="utf-8")
            session = sandbox.make_session()

            self.assertEqual(session.known_models("cloud"),
                             [DEFAULT_CONFIG["model"]])

    def test_defaults_for_another_provider_are_not_offered(self):
        with Sandbox() as sandbox:
            session = sandbox.make_session()
            session.save_defaults(provider="ollama", model="llama3")

            self.assertIn("llama3", session.known_models("ollama"))
            self.assertNotIn("llama3", session.known_models("cloud"))


if __name__ == "__main__":
    unittest.main()
