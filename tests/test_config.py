import json
import unittest

from tests.helpers import Sandbox, DEFAULT_CONFIG

from core import config


VALID_MODELS = [
    "gemini-3.5-flash-lite",
    "llama3.2:3b",
    "qwen2.5-coder:7b-instruct-q4_K_M",
    "hf.co/user/model:Q4_K_M",
    "models/some-model",
]

# Each of these must be rejected: empty, placeholders, malformed, unsafe.
INVALID_MODELS = [
    "",
    "   ",
    None,
    123,
    ["llama3"],
    "<model_name>",
    "<name>",
    "<n>",
    "{model}",
    "[model]",
    "model_name",
    "your_model",
    "Your-Model-Name",
    "gemini 3 flash",
    "model\nname",
    "../../etc",
    "a/../b",
    "-leading-dash",
    "bad!name",
    "x" * (config.MAX_MODEL_NAME_LENGTH + 1),
]


class ValidateModelNameTests(unittest.TestCase):
    def test_accepts_real_model_names(self):
        for model in VALID_MODELS:
            with self.subTest(model=model):
                self.assertEqual(config.validate_model_name(model), model)

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(
            config.validate_model_name("  llama3  "), "llama3"
        )

    def test_rejects_invalid_names(self):
        for model in INVALID_MODELS:
            label = repr(model)[:40]
            with self.subTest(model=label):
                with self.assertRaises(ValueError):
                    config.validate_model_name(model)

    def test_placeholder_message_is_clear(self):
        with self.assertRaises(ValueError) as caught:
            config.validate_model_name("<model_name>")

        self.assertIn("placeholder", str(caught.exception))


class ProviderModelDefaultsTests(unittest.TestCase):
    def test_default_models_are_for_supported_providers_and_valid(self):
        for provider, model in config.DEFAULT_PROVIDER_MODELS.items():
            with self.subTest(provider=provider):
                self.assertIn(provider, config.SUPPORTED_PROVIDERS)
                self.assertEqual(config.validate_model_name(model), model)

    def test_provider_list_is_generated_from_supported_providers(self):
        listed = config.format_provider_list().split(", ")

        self.assertEqual(listed, sorted(config.SUPPORTED_PROVIDERS))


class SaveConfigTests(unittest.TestCase):
    def test_invalid_input_never_overwrites_valid_config(self):
        with Sandbox() as sandbox:
            before = sandbox.config_path.read_bytes()

            bad_configs = [
                {**DEFAULT_CONFIG, "model": model}
                for model in INVALID_MODELS
            ]
            bad_configs += [
                {**DEFAULT_CONFIG, "provider": "nope"},
                {**DEFAULT_CONFIG, "character": "does_not_exist"},
                {**DEFAULT_CONFIG, "character": "../nexis"},
                {**DEFAULT_CONFIG, "character": ""},
                {**DEFAULT_CONFIG, "character": None},
                "not a dict",
            ]

            for bad in bad_configs:
                with self.subTest(config=repr(bad)[:70]):
                    with self.assertRaises(ValueError):
                        config.save_config(bad)

                    self.assertEqual(
                        sandbox.config_path.read_bytes(), before
                    )

            leftovers = list(sandbox.root.glob("*.tmp"))
            self.assertEqual(leftovers, [])

    def test_saves_valid_config_and_keeps_extra_keys(self):
        with Sandbox() as sandbox:
            saved = config.save_config({
                "provider": "ollama",
                "model": "  llama3  ",
                "character": "tester",
                "note": "kept",
            })

            self.assertEqual(saved["model"], "llama3")
            self.assertEqual(sandbox.read_config(), {
                "provider": "ollama",
                "model": "llama3",
                "character": "tester",
                "note": "kept",
            })

    def test_does_not_modify_the_dict_it_was_given(self):
        with Sandbox():
            original = {**DEFAULT_CONFIG, "model": "  llama3  "}
            config.save_config(original)

            self.assertEqual(original["model"], "  llama3  ")

    def test_nonexistent_character_message_points_to_character_list(self):
        with Sandbox():
            with self.assertRaises(ValueError) as caught:
                config.save_config({**DEFAULT_CONFIG, "character": "ghost"})

            self.assertIn("was not found", str(caught.exception))
            self.assertNotIn("WLLM", str(caught.exception))


class LoadConfigTests(unittest.TestCase):
    def test_existing_valid_configuration_still_loads(self):
        with Sandbox():
            self.assertEqual(config.load_config(), DEFAULT_CONFIG)

    def test_rejects_placeholder_model_in_the_file(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_text(
                json.dumps({**DEFAULT_CONFIG, "model": "<model_name>"}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                config.load_config()

    def test_rejects_unsupported_provider_and_bad_json(self):
        with Sandbox() as sandbox:
            sandbox.config_path.write_text(
                json.dumps({**DEFAULT_CONFIG, "provider": "x"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                config.load_config()

            sandbox.config_path.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                config.load_config()


if __name__ == "__main__":
    unittest.main()
