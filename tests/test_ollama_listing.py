"""list_installed_models() against a real local HTTP server, so the real
`requests` code is exercised. No Ollama is needed."""
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tests import helpers  # noqa: F401  (sets up import paths)

from core.providers import ollama
from core.providers.ollama import OllamaUnavailable, list_installed_models


class FakeOllama:
    """A tiny HTTP server answering /api/tags with a chosen response."""

    def __init__(self, status=200, body=b"", delay=0.0):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.paths.append(self.path)

                if delay:
                    time.sleep(delay)

                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass  # the client gave up waiting

            def log_message(self, *args):
                pass

        self.paths = []
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/tags"
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc_info):
        self.server.shutdown()
        self.server.server_close()


def tags(*names, key="name"):
    return json.dumps({"models": [{key: n} for n in names]}).encode()


class ListInstalledModelsTests(unittest.TestCase):
    def test_returns_installed_models_sorted_without_duplicates(self):
        body = tags("qwen2.5-coder:7b", "Llama3:latest", "gemma3:4b",
                    "gemma3:4b")

        with FakeOllama(body=body) as server:
            names = list_installed_models(server.url)

        self.assertEqual(
            names, ["gemma3:4b", "Llama3:latest", "qwen2.5-coder:7b"]
        )
        self.assertEqual(server.paths, ["/api/tags"])

    def test_falls_back_to_the_model_key(self):
        with FakeOllama(body=tags("llama3:latest", key="model")) as server:
            self.assertEqual(list_installed_models(server.url),
                             ["llama3:latest"])

    def test_no_models_installed_is_an_empty_list_not_an_error(self):
        with FakeOllama(body=tags()) as server:
            self.assertEqual(list_installed_models(server.url), [])

    def test_entries_without_a_usable_name_are_skipped(self):
        body = json.dumps({"models": [
            {"name": "ok:1b"}, {"name": ""}, {"name": 5}, {}, "text", None,
            {"name": "  spaced:2b  "},
        ]}).encode()

        with FakeOllama(body=body) as server:
            self.assertEqual(list_installed_models(server.url),
                             ["ok:1b", "spaced:2b"])

    def test_uses_the_tags_endpoint_of_the_chat_url(self):
        self.assertEqual(
            ollama.OLLAMA_TAGS_URL, "http://localhost:11434/api/tags"
        )

    def test_not_running_is_reported_clearly(self):
        with FakeOllama() as server:
            url = server.url

        # The server is stopped now, so nothing is listening on that port.
        with self.assertRaises(OllamaUnavailable) as caught:
            list_installed_models(url, timeout=2)

        self.assertEqual(str(caught.exception), "Ollama is not running.")

    def test_slow_answer_times_out(self):
        with FakeOllama(body=tags("a:1"), delay=1.5) as server:
            with self.assertRaises(OllamaUnavailable) as caught:
                list_installed_models(server.url, timeout=0.2)

        self.assertIn("too long", str(caught.exception))

    def test_http_errors_are_reported(self):
        with FakeOllama(status=500, body=b"{}") as server:
            with self.assertRaises(OllamaUnavailable) as caught:
                list_installed_models(server.url)

        self.assertIn("Ollama returned an error", str(caught.exception))

    def test_unreadable_answers_are_reported(self):
        bodies = {
            "not json": b"this is not json",
            "json but not an object": b"[1, 2, 3]",
            "models is not a list": b'{"models": "none"}',
            "models missing": b"{}",
            "empty body": b"",
        }

        for label, body in bodies.items():
            with self.subTest(case=label):
                with FakeOllama(body=body) as server:
                    with self.assertRaises(OllamaUnavailable) as caught:
                        list_installed_models(server.url)

                self.assertIn("could not read", str(caught.exception))


class InstalledModelSizeTests(unittest.TestCase):
    def details(self, items):
        body = json.dumps({"models": items}).encode()

        with FakeOllama(body=body) as server:
            return ollama.list_installed_model_details(server.url)

    def test_returns_name_and_size_pairs_sorted_by_name(self):
        pairs = self.details([
            {"name": "qwen:7b", "size": 4_700_000_000},
            {"name": "Llama3:latest", "size": 4_661_224_676},
            {"name": "gemma3:4b", "size": 3_338_801_804},
        ])

        self.assertEqual(pairs, [
            ("gemma3:4b", 3_338_801_804),
            ("Llama3:latest", 4_661_224_676),
            ("qwen:7b", 4_700_000_000),
        ])

    def test_missing_or_unusable_sizes_become_none(self):
        pairs = dict(self.details([
            {"name": "a:1"},
            {"name": "b:1", "size": None},
            {"name": "c:1", "size": "big"},
            {"name": "d:1", "size": True},
            {"name": "e:1", "size": -4},
            {"name": "f:1", "size": 0},
        ]))

        self.assertEqual(pairs, {
            "a:1": None, "b:1": None, "c:1": None, "d:1": None,
            "e:1": None, "f:1": 0,
        })

    def test_duplicate_names_are_listed_once(self):
        pairs = self.details([{"name": "a:1", "size": 5}, {"name": "a:1"}])

        self.assertEqual(pairs, [("a:1", 5)])

    def test_names_only_function_is_unchanged(self):
        body = json.dumps({"models": [
            {"name": "b:1", "size": 7}, {"name": "a:1"},
        ]}).encode()

        with FakeOllama(body=body) as server:
            self.assertEqual(list_installed_models(server.url), ["a:1", "b:1"])

    def test_failures_are_reported_the_same_way(self):
        with FakeOllama(body=b"not json") as server:
            with self.assertRaises(OllamaUnavailable):
                ollama.list_installed_model_details(server.url)


if __name__ == "__main__":
    unittest.main()
