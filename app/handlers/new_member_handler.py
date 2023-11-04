from datetime import datetime


def process_new_member(message, bot, conn):
    for new_user in message.new_chat_members:
        user_id = new_user.id
        user_name = new_user.first_name
        mention = "[" + user_name + "](tg://user?id=" + str(user_id) + ")"
        bot_msg = "WelCUM CUMрад, {}".format(mention)
        bot.send_animation(
            message.chat.id,
            animation="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNWEwY2MwY2Q0MTU2Mjg0OWZiNzk0NmY0ZDQ5MWNjMzczODI1YWFmZiZjdD1n/FeAs1kvsWP4OvWa9zt/giphy-downsized-large.gif",
            caption=bot_msg,
            reply_to_message_id=message.id,
            message_thread_id=message.message_thread_id,
            parse_mode="Markdown",
        )
        hello_text = """Расскажу не много инфы про это темное место\n
        1. Первое правило данк клуба, никому не рассказывать про данк
        2. Мемы кидаем только в тред “Мемы”, туда нельзя написать текстом сообщение его сразу удалит бот, только картинки, видео и гифки с мемами. Как только ты кинешь туда мем бот сразу откроет голосовалку где остальные участники проголосуют насколько топовый мем, так можно ориентироваться какие мемы нравятся местной публике, ну и сама не забывай голосовать\n
        3. Изба-пиздельня -  по факту тред для флуда, любое непонятное можно и нужно писать сюда.\n
        4. Практически у всех активных людей в этом чате есть статус, это не просто рандомный текст, а краткое описание того что это за человек и о чем с ним можно поговорить, со временем тебе тоже дадим)\n
        5. Остальные треды по вкусу, там из описания понятно что и зачем\n
        6. Бот собирает статистику за неделю и в понедельник утром шлет метрики, топ самых смешных мемов, сколько суммарно лайков набралось и метрику AML (average meme like) свою текущую метрику AML можно получить написав в любой чат /myaml который показывает среднее количество лайков на твоих мемах. Раз в неделю человеку с самым большим AML бот присваивает почетное звание, так же победитль автоматически промоутится до админа чата.\n
        7. Никаких ограничений на черность мемов тут нет, по ощущениям чем мем чернее тем лучше, лайтовые мемы стараемся не кидать\n
        8. Для смены статуса кому то можно писать мне с обоснованием почему)\n
        9. Так как тут своеобразная атмосфера и не все ее поймут. Можно инвайтить проверенных людей, если уверен(а) что им зайдёт, новеньким тут всегда рады\n
        10. У нас тут полная демократия, если хочешь что-то изменить, кого-то кикнуть / удалить тред / добавить новые правила смело создавай не анонимную голосовалку и если большинство проголосует за, так и будет
        11. Не верь тем кто попросит тебя скидывать дикпик, это самые вруны.
        """

        instruction_message = "Привет {}!\n{}".format(mention, hello_text)
        bot.send_message(
            message.chat.id,
            message_thread_id=message.message_thread_id,
            text=instruction_message,
            parse_mode="Markdown",
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, username, active, joined_date) VALUES(?, ?, ?, ?) ON CONFLICT DO UPDATE SET active=1",
            (
                user_id,
                user_name,
                True,
                datetime.now(),
            ),
        )
        conn.commit()
