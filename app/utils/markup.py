from telebot import types


def generate_markup(
    message_id: int,
    username: str,
    up_votes: int = 0,
    down_votes: int = 0,
    old_hat_votes: int = 0,
    callback_prefix: str = "vote",
):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "👍 " + (str(up_votes) if up_votes else ""),
            callback_data="{}_up|{}".format(callback_prefix, message_id),
        ),
        types.InlineKeyboardButton(
            "👎 " + (str(down_votes) if down_votes else ""),
            callback_data="{}_down|{}".format(callback_prefix, message_id),
        ),
        types.InlineKeyboardButton(
            username + "🪗 " + (str(old_hat_votes) if old_hat_votes else ""),
            callback_data="{}_old_hat|{}".format(callback_prefix, message_id),
        ),
    )

    return markup
