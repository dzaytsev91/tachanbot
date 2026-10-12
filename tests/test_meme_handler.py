from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests
from PIL import Image
from telebot.apihelper import ApiTelegramException

from app.database.create_db_connection import init_db
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
        bot.delete_message.assert_called_once_with(-1001, 42, timeout=15)
        bot.edit_message_reply_markup.assert_not_called()

    def setUp(self):
        self.conn = init_db(":memory:")
        self.addCleanup(self.conn.close)
        self.message = SimpleNamespace(
            id=42,
            photo=[],
            chat=SimpleNamespace(id=-1001),
            from_user=SimpleNamespace(id=7, first_name="Alice"),
        )
        self.bot = MagicMock()
        self.bot.copy_message.side_effect = [
            SimpleNamespace(message_id=101),
            SimpleNamespace(message_id=102),
            SimpleNamespace(message_id=103),
        ]
        sleep = patch("app.handlers.meme_handler.time.sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def process(self):
        process_meme(self.bot, self.conn, self.message, 10, 11, -1002, -1001)

    def stored(self):
        return self.conn.execute(
            "SELECT memes_thread_message_id, flood_thread_message_id, "
            "channel_message_id, hash FROM memes_posts_v2 WHERE id=42"
        ).fetchone()

    def test_photo_timeout_recovers_and_keeps_hash(self):
        self.message.photo = [SimpleNamespace(file_id="photo")]
        image = Image.new("RGB", (8, 8), "white")
        image.putpixel((0, 0), (0, 0, 0))
        data = BytesIO()
        image.save(data, format="PNG")
        response = MagicMock(content=data.getvalue())
        with (
            patch(
                "app.handlers.meme_handler.requests.get",
                side_effect=[requests.ReadTimeout("secret-url"), response],
            ),
            self.assertLogs("app.handlers.meme_handler", level="WARNING") as logs,
        ):
            self.process()
        self.assertEqual(self.stored(), (101, 102, 103, "7fffffffffffffff"))
        self.assertNotIn("secret-url", " ".join(logs.output))
        self.bot.send_message.assert_not_called()

    def test_unavailable_photo_does_not_prevent_publication(self):
        self.message.photo = [SimpleNamespace(file_id="photo")]
        for failure in (
            requests.ConnectionError("secret-url"),
            ApiTelegramException(
                "getFile", None, {"error_code": 502, "description": "Bad Gateway"}
            ),
        ):
            with self.subTest(error=type(failure).__name__):
                self.conn.execute("DELETE FROM memes_posts_v2")
                self.bot.copy_message.side_effect = [
                    SimpleNamespace(message_id=i) for i in (101, 102, 103)
                ]
                self.bot.get_file_url.side_effect = failure
                with self.assertLogs("app.handlers.meme_handler", level="WARNING"):
                    self.process()
                self.assertEqual(self.stored(), (101, 102, 103, ""))

    def test_ambiguous_copy_failure_preserves_original_and_does_not_retry(self):
        for index, stage in enumerate(("copy_memes", "copy_flood", "copy_channel")):
            with self.subTest(stage=stage):
                self.bot.reset_mock()
                self.bot.copy_message.side_effect = [
                    SimpleNamespace(message_id=i) for i in range(101, 101 + index)
                ] + [requests.ReadTimeout("secret-url")]
                with self.assertLogs(
                    "app.handlers.meme_handler", level="ERROR"
                ) as logs:
                    self.process()
                self.assertIsNone(self.stored())
                self.bot.delete_message.assert_not_called()
                self.assertEqual(self.bot.copy_message.call_count, index + 1)
                self.assertIn("42", self.bot.send_message.call_args.args[1])
                text = " ".join(logs.output)
                self.assertIn(f"stage={stage}", text)
                self.assertIn("message=42", text)
                self.assertNotIn("secret-url", text)
                if index:
                    self.assertIn("101", text)

    def test_delete_timeout_then_not_found_is_success(self):
        self.bot.delete_message.side_effect = [
            requests.ReadTimeout(),
            ApiTelegramException(
                "deleteMessage",
                None,
                {
                    "error_code": 400,
                    "description": "Bad Request: message to delete not found",
                },
            ),
        ]
        self.process()
        self.assertEqual(self.stored()[:3], (101, 102, 103))
        self.bot.send_message.assert_not_called()

    def test_exhausted_delete_retries_keep_persisted_meme(self):
        self.bot.delete_message.side_effect = requests.ReadTimeout()
        with self.assertLogs("app.handlers.meme_handler", level="ERROR"):
            self.process()
        self.assertEqual(self.stored()[:3], (101, 102, 103))
        self.assertIn("Мем опубликован", self.bot.send_message.call_args.args[1])

    def test_delete_permission_error_is_not_mistaken_for_success(self):
        self.bot.delete_message.side_effect = ApiTelegramException(
            "deleteMessage", None, {"error_code": 403, "description": "Forbidden"}
        )
        with self.assertLogs("app.handlers.meme_handler", level="ERROR"):
            self.process()
        self.assertEqual(self.stored()[:3], (101, 102, 103))
        self.assertIn(
            "удалить исходник не удалось", self.bot.send_message.call_args.args[1]
        )

    def test_next_meme_is_processed_after_copy_failure(self):
        self.bot.copy_message.side_effect = requests.ReadTimeout()
        with self.assertLogs("app.handlers.meme_handler", level="ERROR"):
            self.process()
        self.assertIsNone(self.stored())
        self.message.id = 43
        self.bot.copy_message.side_effect = [
            SimpleNamespace(message_id=i) for i in (201, 202, 203)
        ]
        self.process()
        row = self.conn.execute(
            "SELECT id, memes_thread_message_id, flood_thread_message_id, "
            "channel_message_id FROM memes_posts_v2"
        ).fetchone()
        self.assertEqual(row, (43, 201, 202, 203))
        self.bot.delete_message.assert_called_once_with(-1001, 43, timeout=15)

    def test_notification_failure_is_logged_without_escaping(self):
        self.bot.copy_message.side_effect = ApiTelegramException(
            "copyMessage", None, {"error_code": 403, "description": "Forbidden"}
        )
        self.bot.send_message.side_effect = requests.ConnectionError("secret-url")
        with self.assertLogs("app.handlers.meme_handler", level="ERROR") as logs:
            self.process()
        self.assertIsNone(self.stored())
        self.bot.delete_message.assert_not_called()
        self.assertIn("stage=notify_failure", " ".join(logs.output))
        self.assertNotIn("secret-url", " ".join(logs.output))
