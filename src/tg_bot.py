from telebot import TeleBot, types
import sqlite3
import subprocess
import os
import asyncio
import time
import re
from threading import Lock
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.errors import FloodWaitError, AuthRestartError
from telethon.errors import SessionPasswordNeededError

# Ваш токен бота
BOT_TOKEN = '7282596116:AAFEPgk-G5hdEdnj1FIWvW489Dcx7BrMToU'
ALLOWED_USERS = [7021930058, 5349332457]
def is_user_allowed(user_id):
    return user_id in ALLOWED_USERS

# Створення бота через TeleBot
bot = TeleBot(BOT_TOKEN)

# Змінні для зберігання процесів
bot_process = None

# Блокування для синхронізації доступу до бази даних
db_lock = Lock()

# Функція для виконання запитів до бази даних з повторними спробами
def execute_db_query(query, params=(), retries=5):
    for attempt in range(retries):
        with db_lock:
            try:
                with sqlite3.connect('accounts_db.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    conn.commit()
                    
                    # Повертаємо результат запиту, якщо це SELECT-запит
                    if query.strip().upper().startswith("SELECT"):
                        return cursor.fetchall()
                    return True
            except sqlite3.OperationalError as e:
                if 'locked' in str(e):
                    print(f"База даних заблокована. Спроба {attempt + 1} з {retries}")
                    time.sleep(1)  # Затримка перед повторною спробою
                else:
                    print(f"Помилка при виконанні запиту: {e}")
                    return False
    print("Запит не вдалося виконати після кількох спроб.")
    return False

# Створення або підключення до бази даних
def create_db():
    execute_db_query(''' 
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id TEXT UNIQUE,
            api_hash TEXT,
            phone TEXT,
            code TEXT,
            password TEXT
        )
    ''')

    execute_db_query('''
        CREATE TABLE IF NOT EXISTS channel_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_link TEXT UNIQUE,
            channel_id TEXT
        )
    ''')

# Додавання нового користувача
def add_user(api_id, api_hash, phone, chat_id):
    try:
        execute_db_query('INSERT INTO accounts (api_id, api_hash, phone) VALUES (?, ?, ?)', (api_id, api_hash, phone))
        print(f"Користувач з API_ID {api_id} успішно доданий.")
    except sqlite3.IntegrityError as e:
        print(f"Помилка при додаванні користувача: {e}")
        # Відправляємо повідомлення користувачу, що API_ID вже існує
        bot.send_message(chat_id, "Ошибка: Пользователь с таким API_ID уже существует.")
    except Exception as e:
        print(f"Непередбачена помилка при додаванні користувача: {e}")
        bot.send_message(chat_id, "Непредвиденная ошибка при добавлении пользователя.")


# Видалення користувача за номером телефону
def delete_user(phone):
    result = execute_db_query('DELETE FROM accounts WHERE phone = ?', (phone))
    return result

# Видалення користувача за номером телефону
def delete_channel(link):
    result = execute_db_query('DELETE FROM channel_links WHERE channel_link = ?', (link))
    return result

# Відображення всіх користувачів
def get_all_users():
    return execute_db_query('SELECT api_id, api_hash, phone FROM accounts')


def get_all_channels():
    return execute_db_query('SELECT id, channel_link FROM channel_links')

# Меню додавання нового користувача
@bot.message_handler(commands=['start'])
def start(message):
    if is_user_allowed(message.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Добавить пользователя", callback_data='add_user'))
        markup.add(types.InlineKeyboardButton("Удалить пользователя", callback_data='delete_user'))
        markup.add(types.InlineKeyboardButton("Показать пользователей", callback_data='show_users'))
        markup.add(types.InlineKeyboardButton("Добавить канал", callback_data='add_channel'))
        markup.add(types.InlineKeyboardButton("Удалить канал", callback_data='delete_channel'))
        markup.add(types.InlineKeyboardButton("Показать каналы", callback_data='show_channels'))
        markup.add(types.InlineKeyboardButton("Перезапустить", callback_data='restart'))
    
        bot.send_message(message.chat.id, "Привет! Выберите действие:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Извините, у вас нет доступа к этому боту.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if is_user_allowed(call.from_user.id):
        global bot_process
        if call.data == 'add_user':
          msg = bot.send_message(call.message.chat.id, 'Введите данные нового пользователя в формате: API_ID API_HASH PHONE')
          bot.register_next_step_handler(msg, add_user_handler_sync)
        elif call.data == 'delete_user':
            msg = bot.send_message(call.message.chat.id, 'Введите телефонный номер пользователя для удаления:')
            bot.register_next_step_handler(msg, delete_user_handler)
        elif call.data == 'show_users':
            users = get_all_users()
            if users:
                response = "Пользователи в базе данных:\n"
                for user in users:
                    response += f"Phone: {user[2]}, API_ID: {user[0]}\n"
            else:
                response = "Нет пользователей в базе данных."
            bot.send_message(call.message.chat.id, response)
    

    
        elif call.data == 'restart':
            if bot_process:
                bot_process.terminate()
                bot_process.wait()

            time.sleep(3)  # Зачекайте 3 секунди

            bot_process = subprocess.Popen(['python', 'bot.py'], start_new_session=True)
            time.sleep(10)
        
            bot.send_message(call.message.chat.id, 'Перезапуск завершен!')

        elif call.data == 'add_channel':
            msg = bot.send_message(call.message.chat.id, 'Введите новый телеграмм канал в формате: link chat_id:')
            bot.register_next_step_handler(msg, add_channel)

        elif call.data == 'show_channels':
            channels = get_all_channels()
            if channels:
                response = "Каналы в базе данных:\n"
                counter = 1
                for channel in channels:
                    response += f"Id: {counter}, Channel link: {channel[1]}\n"
                    counter+=1
            else:
                response = "Нет каналов в базе данных."
            bot.send_message(call.message.chat.id, response)
    
        elif call.data == 'delete_channel':
            msg = bot.send_message(call.message.chat.id, 'Введите ссылку на канал, который хотите удалить:')
            bot.register_next_step_handler(msg, delete_channel_handler)

def add_user_handler_sync(message):
    asyncio.run(add_user_handler(message))

async def add_user_handler(message):
    try:
        api_id, api_hash, phone = message.text.split()
        add_user(api_id, api_hash, phone, message.chat.id)
        await start_user_authentication(phone, api_id, api_hash, message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Ошибка! Убедитесь, что вы ввели данные в правильном формате: API_ID API_HASH PHONE")

# Обробка введення коду підтвердження та пароля
pending_authorizations = {}

async def authenticate_user(phone, api_id, api_hash, code, phone_code_hash, password, chat_id):
    client = TelegramClient(f'session_{phone}', api_id, api_hash)
    
    try:
        await client.connect()
        if password:
            await client.sign_in(password=password)
        else:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        print("Користувач успішно авторизований!")
        bot.send_message(chat_id, 'Авторизация успешна! Пользователь будет активен после перезапуска.')
        
        # Видалення даних користувача з черги авторизації
        if chat_id in pending_authorizations:
            del pending_authorizations[chat_id]

    except SessionPasswordNeededError:
        print("Потрібен пароль двоетапної аутентифікації.")
        bot.send_message(chat_id, "Требуется пароль двухэтапной аутентификации. Введите пароль:")
        pending_authorizations[chat_id]['step'] = 'password'
    except FloodWaitError as e:
        wait_time = min(e.seconds, 3600)  # Максимальна затримка - 1 година
        print(f"FloodWaitError: Sleeping for {wait_time} seconds")
        delete_user(phone)
        bot.send_message(chat_id, f"Лимит кодов исчерпан, подождите {wait_time//60} минут для повторной авторизации. Чтобы избежать ошибок пользователь был удален из базы, перезапустите код.")
        await asyncio.sleep(wait_time)
        await start_user_authentication(phone, api_id, api_hash, chat_id)
    except AuthRestartError:
        print("Telegram is having internal issues. Restarting the authorization process...")
        await start_user_authentication(phone, api_id, api_hash, chat_id)
    except Exception as e:
        print(f"Авторизація не вдалася. Помилка: {e}")
        bot.send_message(chat_id, f"Авторизация не удалась. Ошибка: {e}")
        if 'PHONE_CODE_INVALID' in str(e):
            bot.send_message(chat_id, "Введённый код подтверждения неверен. Попробуйте еще раз.")
            pending_authorizations[chat_id]['step'] = 'code'
    finally:
        if client.is_connected():
            await client.disconnect()


@bot.message_handler(func=lambda message: message.chat.id in pending_authorizations)
def authorization_handler(message):
    asyncio.run(authorization_handler_async(message))

async def authorization_handler_async(message):
    user_data = pending_authorizations[message.chat.id]
    
    if user_data['step'] == 'code':
        code = message.text
        phone = user_data['phone']
        api_id = user_data['api_id']
        api_hash = user_data['api_hash']
        phone_code_hash = user_data['phone_code_hash']
        
        # Оновлення коду в базі даних
        execute_db_query('UPDATE accounts SET code = ? WHERE phone = ?', (code, phone))
        
        # Вставляємо код в авторизацію
        user_data['code'] = code
        await authenticate_user(phone, api_id, api_hash, code, phone_code_hash, None, message.chat.id)
    
    elif user_data['step'] == 'password':
        password = message.text
        phone = user_data['phone']
        api_id = user_data['api_id']
        api_hash = user_data['api_hash']
        code = user_data['code']
        phone_code_hash = user_data['phone_code_hash']
        
        # Вставляємо пароль в авторизацію
        await authenticate_user(phone, api_id, api_hash, code, phone_code_hash, password, message.chat.id)


async def start_user_authentication(phone, api_id, api_hash, chat_id):
    
    if await check_session_exists(phone, api_id, api_hash):
        print("Сесія вже існує.")
        bot.send_message(chat_id, "Сессия уже существует, пользователь будет активен после перезапуска.")
        return
    else:
        print("Сесія не існує. Розпочинаємо авторизацію.")

    client = TelegramClient(f'session_{phone}', api_id, api_hash)
    
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        pending_authorizations[chat_id] = {
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'phone_code_hash': sent_code.phone_code_hash,
            'step': 'code'
        }
        bot.send_message(chat_id, "Введите код подтверждения:")
    except FloodWaitError as e:
        wait_time = min(e.seconds, 3600)  # Максимальна затримка - 1 година
        print(f"FloodWaitError: Sleeping for {wait_time} seconds")
        delete_user(phone)
        bot.send_message(chat_id, f"Лимит кодов исчерпан, подождите {wait_time//60} минут для повторной авторизации. Чтобы избежать ошибок пользователь был удален из базы, перезапустите код.")
    except Exception as e:
        print(f"Помилка під час підключення: {e}")
        await asyncio.sleep(5)

# Функція для видалення користувача
def delete_user_handler(message):
    phone = message.text.split()
    if len(str(phone)) <= 8:
        bot.send_message(message.chat.id, "Неверный формат телефонного номера.")
        return
    if delete_user(phone):
        bot.send_message(message.chat.id, f"Пользователя с номером телефона {phone} удален.")
    else:
        bot.send_message(message.chat.id, "Пользователя не найдено.")

# Функція для видалення користувача
def delete_channel_handler(message):
    link = message.text.split()
    if delete_channel(link):
        bot.send_message(message.chat.id, f"Ссылка {link} на канал удалено.")
    else:
        bot.send_message(message.chat.id, "Ссылка на канал не найдена.")

async def check_session_exists(phone, api_id, api_hash):
    session_file = f'session_{phone}.session'
    
    # Перевіряємо наявність сесійного файлу
    if not os.path.exists(session_file):
        return False

    client = TelegramClient(session_file, api_id, api_hash)
    
    try:
        await client.connect()
        
        # Перевіряємо, чи сесія є дійсною
        if not await client.is_user_authorized():
            return False
        
        return True
        
    except SessionPasswordNeededError:
        # Потрібен пароль двоетапної аутентифікації
        return True  # Сесія існує, але потрібно ввести пароль
    
    except Exception as e:
        print(f"Помилка перевірки сесії: {e}")
        return False
    finally:
        if client.is_connected():
            await client.disconnect()


def add_channel(message):
    try:
        link, chat_id = message.text.split()

        execute_db_query('INSERT INTO channel_links (channel_link, channel_id) VALUES (?,?)', (link, chat_id))
        print(f"Канал із посиланням {link} успішно доданий.")
        bot.send_message(message.chat.id, f"Канал со ссылкой {link} успешно добавлен.")
    except ValueError:
        # Якщо не вдалося розділити на два значення
        bot.send_message(message.chat.id, "Пожалуйста, введите ссылку на канал и ID чата через пробел.")
    except sqlite3.IntegrityError as e:
        print(f"Помилка при додаванні каналу: {e}")
        # Відправляємо повідомлення користувачу, що API_ID вже існує
        bot.send_message(message.chat.id, "Ошибка: канал с такой ссылкой уже существует.")
    except Exception as e:
        print(f"Непередбачена помилка при додаванні каналу: {e}")
        bot.send_message(message.chat.id, "Непредвиденная ошибка при добавлении канала.")




if __name__ == '__main__':
    create_db()
    bot.polling(none_stop=True)
