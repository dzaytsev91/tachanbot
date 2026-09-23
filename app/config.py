from __future__ import annotations

import os
from dataclasses import dataclass


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _required_int(name: str) -> int:
    value = _required(name)
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    memes_chat_id: int
    memes_thread_id: int
    flood_thread_id: int
    music_thread_id: int
    external_channel_chat_id: int
    chat_creator_id: int
    db_path: str
    backup_dir: str

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            bot_token=_required("BOT_TOKEN"),
            memes_chat_id=_required_int("MEMES_CHAT_ID"),
            memes_thread_id=_required_int("MEMES_THREAD_ID"),
            flood_thread_id=_required_int("FLOOD_THREAD_ID"),
            music_thread_id=_required_int("MUSIC_THREAD_ID"),
            external_channel_chat_id=_required_int("EXTERNAL_CHANNEL_CHAT_ID"),
            chat_creator_id=int(os.getenv("CHAT_CREATOR_ID", "43529628")),
            db_path=os.getenv("DB_PATH", "memes.db"),
            backup_dir=os.getenv("BACKUP_DIR", "/data/backups"),
        )
