import unittest

from tests import helpers  # noqa: F401  (sets up import paths)

from core import models


class NormalizeTests(unittest.TestCase):
    def test_latest_tag_is_ignored(self):
        self.assertEqual(models.normalize_ollama_name("llama3:latest"), "llama3")
        self.assertEqual(models.normalize_ollama_name("llama3"), "llama3")

    def test_other_tags_are_kept(self):
        self.assertEqual(models.normalize_ollama_name("llama3:8b"), "llama3:8b")
        self.assertEqual(
            models.normalize_ollama_name("hf.co/u/m:Q4_K_M"), "hf.co/u/m:Q4_K_M"
        )

    def test_blank_and_none_are_safe(self):
        self.assertEqual(models.normalize_ollama_name(None), "")
        self.assertEqual(models.normalize_ollama_name("  x  "), "x")


class IsInstalledTests(unittest.TestCase):
    def test_name_with_and_without_latest_both_match(self):
        installed = ["llama3:latest", "qwen2.5-coder:7b"]

        self.assertTrue(models.is_installed("llama3", installed))
        self.assertTrue(models.is_installed("llama3:latest", installed))
        self.assertTrue(models.is_installed("qwen2.5-coder:7b", installed))

    def test_a_different_tag_is_a_different_model(self):
        installed = ["llama3:latest"]

        self.assertFalse(models.is_installed("llama3:8b", installed))
        self.assertFalse(models.is_installed("llama", installed))

    def test_installed_name_without_tag_matches_latest(self):
        self.assertTrue(models.is_installed("llama3:latest", ["llama3"]))


class CheckOllamaModelTests(unittest.TestCase):
    def test_installed_model_has_no_problem(self):
        self.assertIsNone(
            models.check_ollama_model("llama3", ["llama3:latest"])
        )

    def test_unknown_installed_list_means_nothing_can_be_reported(self):
        self.assertIsNone(models.check_ollama_model("anything", None))

    def test_missing_model_is_explained_and_install_command_given(self):
        message = models.check_ollama_model("mistral", ["llama3:latest"])

        self.assertIn("'mistral' is not installed in Ollama", message)
        self.assertIn("Installed models: llama3:latest.", message)
        self.assertIn("ollama pull mistral", message)

    def test_near_miss_gets_a_suggestion_with_the_full_name(self):
        message = models.check_ollama_model(
            "lama3", ["llama3:latest", "qwen2.5-coder:7b"]
        )

        self.assertIn("Did you mean 'llama3:latest'?", message)

    def test_unrelated_name_gets_no_suggestion(self):
        message = models.check_ollama_model("zzzzzz", ["llama3:latest"])

        self.assertNotIn("Did you mean", message)

    def test_empty_installed_list_says_so(self):
        message = models.check_ollama_model("llama3", [])

        self.assertIn("No models are installed yet.", message)
        self.assertIn("ollama pull llama3", message)

    def test_long_lists_are_shortened(self):
        installed = [f"model{n}:1b" for n in range(1, 9)]

        message = models.check_ollama_model("other", installed)

        self.assertIn("model1:1b", message)
        self.assertIn("model5:1b", message)
        self.assertNotIn("model6:1b", message)
        self.assertIn("and 3 more", message)


class MenuModelsTests(unittest.TestCase):
    def test_ollama_with_a_list_shows_only_installed_models(self):
        shown = models.menu_models("ollama", ["a:1", "b:2"], ["known:1"])

        self.assertEqual(shown, ["a:1", "b:2"])

    def test_ollama_without_a_list_falls_back_to_known_models(self):
        shown = models.menu_models("ollama", None, ["known:1"])

        self.assertEqual(shown, ["known:1"])

    def test_an_empty_installed_list_is_respected(self):
        self.assertEqual(models.menu_models("ollama", [], ["known:1"]), [])

    def test_other_providers_always_use_known_models(self):
        shown = models.menu_models("cloud", ["ignored"], ["known-1", "known-2"])

        self.assertEqual(shown, ["known-1", "known-2"])

    def test_the_inputs_are_not_modified(self):
        installed = ["a", "b"]

        models.menu_models("ollama", installed, []).append("c")

        self.assertEqual(installed, ["a", "b"])


class LabelTests(unittest.TestCase):
    def label(self, model, provider="cloud", current=("cloud", "m1"),
              default=("cloud", "m1")):
        return models.label_model(model, provider, *current, *default)

    def test_current_and_default_are_marked(self):
        self.assertEqual(
            self.label("m1"), "m1 (current, default for new chats)"
        )

    def test_current_only(self):
        self.assertEqual(
            self.label("m1", default=("cloud", "other")), "m1 (current)"
        )

    def test_default_only(self):
        self.assertEqual(
            self.label("m1", current=("cloud", "other")),
            "m1 (default for new chats)",
        )

    def test_unmarked_models_have_a_plain_label(self):
        self.assertEqual(self.label("m2"), "m2")

    def test_the_same_model_name_under_another_provider_is_not_marked(self):
        self.assertEqual(
            self.label("m1", provider="ollama"), "m1"
        )

    def test_ollama_latest_is_treated_as_the_same_model(self):
        label = self.label(
            "llama3:latest", provider="ollama",
            current=("ollama", "llama3"), default=("cloud", "x"),
        )

        self.assertEqual(label, "llama3:latest (current)")


class FormatSizeTests(unittest.TestCase):
    def test_sizes_are_shown_the_way_ollama_shows_them(self):
        cases = {
            0: "0 B", 999: "999 B", 1000: "1.0 KB", 1_500_000: "1.5 MB",
            3_338_801_804: "3.3 GB", 4_661_224_676: "4.7 GB",
            12_000_000_000_000: "12.0 TB",
        }

        for size, expected in cases.items():
            with self.subTest(size=size):
                self.assertEqual(models.format_size(size), expected)

    def test_unknown_or_unusable_sizes_give_none(self):
        for size in (None, True, False, -1, "5", 1.5, [], {}):
            with self.subTest(size=repr(size)):
                self.assertIsNone(models.format_size(size))


class LabelWithSizeTests(unittest.TestCase):
    def test_size_follows_the_name_and_notes_come_last(self):
        label = models.label_model(
            "llama3:latest", "ollama", "ollama", "llama3", "cloud", "x",
            size_bytes=4_661_224_676,
        )

        self.assertEqual(label, "llama3:latest - 4.7 GB (current)")

    def test_no_size_leaves_the_label_as_before(self):
        for size in (None, -5, "big"):
            with self.subTest(size=size):
                label = models.label_model(
                    "m1", "cloud", "cloud", "m1", "cloud", "m1",
                    size_bytes=size,
                )

                self.assertEqual(label, "m1 (current, default for new chats)")

    def test_size_without_notes(self):
        label = models.label_model(
            "m2", "ollama", "cloud", "x", "cloud", "x", size_bytes=1_000_000
        )

        self.assertEqual(label, "m2 - 1.0 MB")


if __name__ == "__main__":
    unittest.main()
