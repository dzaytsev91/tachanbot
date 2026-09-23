from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.handlers.meme_handler import process_meme


class TestProcessMeme(TestCase):
    @patch("app.handlers.meme_handler.save_meme_to_db")
    def test_copies_markup_once_without_reapplying_identical_markup(self, save_meme):
        bot = MagicMock()
        bot.copy_message.side_effect = [
            SimpleNamespace(message_id=101),
            SimpleNamespace(message_id=102),
            SimpleNamespace(message_id=103),
        ]
        message = SimpleNamespace(
            id=42,
            photo=[],
            chat=SimpleNamespace(id=-1001),
            from_user=SimpleNamespace(first_name="Alice"),
        )
        conn = MagicMock()

        process_meme(
            bot,
            conn,
            message,
            memes_thread_id=10,
            flood_thread_id=11,
            external_channel_chat_id=-1002,
            memes_chat_id=-1001,
        )

        self.assertEqual(bot.copy_message.call_count, 3)
        for copy_call in bot.copy_message.call_args_list:
            self.assertIsNotNone(copy_call.kwargs["reply_markup"])
        save_meme.assert_called_once_with(conn, message, 102, 101, 103, "")
        bot.delete_message.assert_called_once_with(-1001, 42)
        bot.edit_message_reply_markup.assert_not_called()
