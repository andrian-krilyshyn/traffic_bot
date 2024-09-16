from telethon import TelegramClient, events, functions, types
import sqlite3
import random
import asyncio
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.messages import GetChatsRequest
from telethon.tl.types import Chat

# Отримання даних облікових записів із бази даних
def get_account_data():
    try:
        with sqlite3.connect('accounts_db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT api_id, api_hash, phone FROM accounts')
            return cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return []
    

# Отримання даних про канали із бази даних
def get_channel_data():
    try:
        with sqlite3.connect('accounts_db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT channel_link, channel_id FROM channel_links')
            return cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return []

# Словник для зберігання клієнтів
clients = {}

CHANNEL_LINKS = []
TARGET_CHAT_ID = []

def is_value_in_list(value):
    return str(value) in TARGET_CHAT_ID



# Ініціалізація клієнтів
async def initialize_clients():
    accounts = get_account_data()
    for api_id, api_hash, phone in accounts:
        client = TelegramClient(f'session_{phone}', api_id, api_hash)
        await client.start(phone)
        clients[phone] = client
        print(f"Initialized client for {phone}")
        await subscribe_to_channels(client)
        print(f"Client with phone: {phone} subscribed to all channels")

        # Додавання обробників подій для кожного клієнта
        client.add_event_handler(new_message_handler, events.NewMessage)
        client.add_event_handler(poll_message_handler, events.NewMessage)

        # Ініціалізація клієнтів
def initialize_channels():
    channels = get_channel_data()
    for channel_link, channel_id  in channels:
        CHANNEL_LINKS.append(channel_link)
        TARGET_CHAT_ID.append(channel_id)
        print(f"Initialized chat for {channel_id}")

# Підписка клієнта на всі канали з CHANNEL_LINKS
async def subscribe_to_channels(client):
    for  channel_link in CHANNEL_LINKS:
        try:
            # Перевірка, чи це посилання запрошення (починається з '+')
            if '+' in channel_link:
                invite_hash = channel_link.split('+')[-1]  # Отримуємо частину запрошення після '+'
                
                # Приєднання до каналу
                await client(ImportChatInviteRequest(invite_hash))
                print(f"Client {client.session.filename} joined channel using invite link {channel_link}")
            else:
                print(f"Invalid invite link format: {channel_link}")
        except Exception as e:
            print(f"Error joining channel {channel_link}: {e}")



# Вказати ID або назву групи, у якій слід реагувати


# Рандомний вибір реакції з доступних варіантів
REACTIONS = ['👍', '🔥', '❤️', '😎', '😍', '⚡️']

# Обробник подій для нових повідомлень (додає реакції)
async def new_message_handler(event):
    # Перевірка, чи подія є повідомленням і чи відбувається в цільовій групі
    if isinstance(event, events.NewMessage.Event) and is_value_in_list(event.chat_id):
        client = event._client  # Використовуємо _client замість client
        chat_id = event.chat_id
        message_id = event.message.id
        reaction = random.choice(REACTIONS)

        # Створення реакції типу ReactionEmoji
        reaction_emoji = types.ReactionEmoji(emoticon=reaction)

        await client(functions.messages.SendReactionRequest(
            peer=chat_id,
            msg_id=message_id,
            reaction=[reaction_emoji]  # Використання об'єкта ReactionEmoji
        ))
        print(f"Reaction {reaction} added to message {message_id} in chat {chat_id}")

# Обробник подій для нових опитувань (випадкове голосування)
async def poll_message_handler(event):

    # Перевірка, чи подія є повідомленням з опитуванням і чи відбувається в цільовій групі
    if isinstance(event, events.NewMessage.Event) and event.message.poll and is_value_in_list(event.chat_id):
        client = event._client  # Використовуємо _client замість client
        chat_id = event.chat_id
        poll_id = event.message.id

        # Отримання опцій опитування
        try:
            poll = event.message.media.poll  # Отримуємо опитування з повідомлення
            options = poll.answers  # Це опції опитування

            if options:
                random_choice = random.choice(options)  # Випадковий вибір варіанту
                await client(functions.messages.SendVoteRequest(
                    peer=chat_id,
                    msg_id=poll_id,
                    options=[random_choice.option]  # Використовуємо байтове значення варіанту
                ))
                print(f"Voted randomly in poll {poll_id} in chat {chat_id}")

        except Exception as e:
            print(f"Failed to vote in poll {poll_id} in chat {chat_id}: {e}")

# Основна функція для запуску клієнтів і обробників подій
async def main():
    initialize_channels()
    await initialize_clients()
    # Не завершуємо програму, поки працюють обробники
    await asyncio.Event().wait()

# Запуск
if __name__ == '__main__':
    asyncio.run(main())


