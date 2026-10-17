import json
import unittest

from tests.helpers import Sandbox

from core import conversation
from core.conversation import ChatLimitError


def make_chats(count):
    return [conversation.create_chat()["session_id"] for _ in range(count)]


class ChatLimitTests(unittest.TestCase):
    def test_reaching_the_limit_blocks_creation_and_deletes_nothing(self):
        with Sandbox(max_chats=3) as sandbox:
            ids = make_chats(3)
            files_before = sandbox.chat_files()
            index_before = conversation.load_index()

            with self.assertRaises(ChatLimitError) as caught:
                conversation.create_chat()

            self.assertIn("Chat limit reached (3", str(caught.exception))
            self.assertEqual(sandbox.chat_files(), files_before)
            self.assertEqual(conversation.load_index(), index_before)
            self.assertEqual(
                [item["session_id"] for item in conversation.load_index()],
                ids,
            )

    def test_creating_many_chats_never_removes_older_ones(self):
        with Sandbox(max_chats=2) as sandbox:
            ids = make_chats(2)

            for _ in range(5):
                with self.assertRaises(ChatLimitError):
                    conversation.create_chat()

            self.assertEqual(
                sandbox.chat_files(), [f"{name}.json" for name in ids]
            )

    def test_chat_content_survives_a_blocked_attempt(self):
        with Sandbox(max_chats=1) as sandbox:
            chat = conversation.create_chat()
            chat["messages"] = [{"role": "user", "content": "keep me"}]
            conversation.update_chat(chat)

            with self.assertRaises(ChatLimitError):
                conversation.create_chat()

            saved = sandbox.read_chat(chat["session_id"])
            self.assertEqual(saved["messages"][0]["content"], "keep me")

    def test_creation_works_again_after_the_user_deletes_a_chat(self):
        with Sandbox(max_chats=2) as sandbox:
            first, second = make_chats(2)

            with self.assertRaises(ChatLimitError):
                conversation.create_chat()

            self.assertTrue(conversation.delete_chat(first))
            created = conversation.create_chat()

            self.assertEqual(
                sandbox.chat_files(),
                sorted([f"{second}.json", f"{created['session_id']}.json"]),
            )

    def test_lowering_the_limit_deletes_nothing(self):
        with Sandbox(max_chats=5) as sandbox:
            make_chats(3)

            from unittest import mock

            with mock.patch.object(conversation, "MAX_CHATS", 1):
                with self.assertRaises(ChatLimitError):
                    conversation.create_chat()

            self.assertEqual(len(sandbox.chat_files()), 3)

    def test_index_entries_with_no_file_do_not_count(self):
        with Sandbox(max_chats=2) as sandbox:
            first, second = make_chats(2)
            (sandbox.chats_dir / f"{first}.json").unlink()

            # The orphaned index entry must not block creating a chat.
            created = conversation.create_chat()

            self.assertIn(
                f"{created['session_id']}.json", sandbox.chat_files()
            )


class SessionNewChatLimitTests(unittest.TestCase):
    def test_new_chat_at_the_limit_raises_and_keeps_the_session_intact(self):
        with Sandbox(max_chats=2) as sandbox:
            session = sandbox.make_session()
            session.new_chat()
            current_id = session.session_id
            session.change_model("gemini-x")
            files_before = sandbox.chat_files()

            with self.assertRaises(ChatLimitError):
                session.new_chat()

            self.assertEqual(session.session_id, current_id)
            self.assertEqual(session.model, "gemini-x")
            self.assertEqual(sandbox.chat_files(), files_before)
            active = json.loads(
                (sandbox.chats_dir / "active_session.json").read_text("utf-8")
            )
            self.assertEqual(active["session_id"], current_id)


if __name__ == "__main__":
    unittest.main()
