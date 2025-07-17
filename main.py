import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
import logging
from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any

from aiogram import F
from aiogram.types import Message

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from asyncio import Lock

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import json
import os
from random import sample, randint, choices
import time
from random import choice
from aiogram.types import CallbackQuery  # если ещё не импортирован

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import random
from collections import Counter
from datetime import date

from aiogram.types import ChatMemberUpdated
from aiogram import Bot, Dispatcher, F

from aiogram.exceptions import TelegramBadRequest
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import ChatMemberUpdatedFilter

from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from aiogram.utils.formatting import as_marked_section, Bold
from aiogram import types
import asyncio



from aiogram.filters import Command

from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram import Bot
import logging

# Создание логгера
logging.basicConfig(
    level=logging.INFO,  # Можно INFO или DEBUG
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),  # 👉 сюда пишутся все логи
        # logging.StreamHandler()  # ❌ отключи, если не хочешь видеть в консоли
    ]
)

# Уменьшаем спам от aiogram.event
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
active_hel_games = {}  # {chat_id: {user_id: {"bet": int, "choice": None}}}
spin_result_ready = {}  # {chat_id: bool}
last_spin_bet = {}  # {user_id: {"entries": [...], "sum": int}}
hell_game_history = {}

chat_spin_start = {}  # {chat_id: timestamp}

daily_top = {}

disabled_games_by_chat = {}  # {chat_id: set(game_codes)}

chat_spin_bets = {}       # {chat_id: {user_id: {...}}}

chat_spinning = {}        # {chat_id: bool}
spin_history_by_chat = {} # {chat_id: [results]}

DAILY_TOP_PATH = "daily_top.json"
SPIN_LOG_PATH = "spin_log.json"
DISABLED_GAMES_PATH = "disabled_games.json"

RED_NUMBERS = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
BLACK_NUMBERS = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]

duel_requests = {}  # chat_id: {target_id: {...}}
active_duels = set()  # user_ids участвующие в дуэли
user_last_message_time = {}
active_mines_games = {}  # user_id: timestamp
# Данные для игры (поля, мины, состояния)
mines = [1, 4, 7]  # Пример клеток с минами
opened_cells = set()  # Множество открытых клеток
players = {}  # Статус игроков

# Кол-во пользователей на 1 страницу
PAGE_SIZE = 5


daily_top_date = str(date.today())
SAKURA_RULES_CHAT_ID = -1002790729076  # Чат для правил Sakura
TARGET_CHAT_ID = -1002835369234  # Тот самый чат
CHANNEL_ID = -1002536417248  # ID канала
CHANNEL_LINK = "https://t.me/settskamss"
BONUS_AMOUNT = 5000

BOT_USERNAME = "economuvl_bot"  # без @
# 🎯 Список редких кастомных ников и их цены
RARE_NICKS = {
    "durov": 15_000_000,
    "sakura": 1_500_000
}


DUEL_TIMEOUT = 120  # 2 минуты
# 🔐 Настройки
API_TOKEN = "7988458795:AAFsWNyn_iR8RNXuD66TAoAQuHjfVYE0SVQ"
DB_PATH = "sakurarep.db"
ADMINS = [7333809850]  # добавь свои ID сюда
ADMIN_ID = 123456789
TARGET_USER_ID = 7333809850

# 📦 Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class MineGame(StatesGroup):
    playing = State()

async def is_treasury_enabled(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT 1 FROM group_treasury WHERE chat_id = ?", (chat_id,))
        return (await row.fetchone()) is not None



# 🔧 Middleware регистрации
class RegisterUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message):
            await register_user(event.from_user)
        return await handler(event, data)

# 🔒 Middleware защиты от флуда (только для групп)
user_last_message_time = {}

class FloodControlMiddleware(BaseMiddleware):
    def __init__(self, limit_seconds: int = 3):
        super().__init__()
        self.limit = limit_seconds

    async def __call__(
        self,
        handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message):
            # ✅ Только для групп
            if event.chat.type not in ("group", "supergroup"):
                return await handler(event, data)

            user_id = event.from_user.id
            now = time.time()

            last_time = user_last_message_time.get(user_id)

            user_last_message_time[user_id] = now

        return await handler(event, data)

class MessageStatsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.Message, Dict[str, Any]], Awaitable[Any]],
        event: types.Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message):
            if event.chat.type not in ("group", "supergroup"):
                return await handler(event, data)

            user = event.from_user
            chat_id = event.chat.id
            user_id = user.id
            username = user.username or f"id{user.id}"
            date = datetime.now().strftime("%Y-%m-%d")  # суточная метка

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT INTO message_stats (chat_id, user_id, username, date, count)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(chat_id, user_id, date)
                    DO UPDATE SET count = count + 1
                """, (chat_id, user_id, username, date))
                await db.commit()

        return await handler(event, data)

class BlacklistMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: Dict[str, Any]):
        user_id = event.from_user.id
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
            result = await row.fetchone()
            if result:
                return  # Игнорируем все команды
        return await handler(event, data)

dp.message.middleware(BlacklistMiddleware())

dp.message.middleware(MessageStatsMiddleware())


# 📦 Подключение middleware
dp.message.middleware(RegisterUserMiddleware())
dp.message.middleware(FloodControlMiddleware(limit_seconds=3))

# ✅ Регистрация пользователя + создание таблицы users
async def register_user(user: types.User):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                sakura INTEGER DEFAULT 0,
                iriski INTEGER DEFAULT 0,
                bag_open INTEGER DEFAULT 1,
                last_bonus TEXT,
                basketball_hits INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                bio_checked INTEGER DEFAULT 0,
                starter_bonus INTEGER DEFAULT 0,
                registered_at TEXT
            )
        """)
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, registered_at)
            VALUES (?, ?, ?, ?)
        """, (user.id, user.username or f"id{user.id}", user.first_name, now))
        await db.commit()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_bonuses (
                bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount INTEGER,
                max_activations INTEGER,
                activated_by TEXT DEFAULT ''
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                amount INTEGER,
                price INTEGER,
                created_at TEXT
            )
        """)

        now = datetime.now().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, registered_at)
            VALUES (?, ?, ?, ?)
        """, (user.id, user.username or f"id{user.id}", user.first_name, now))
        await db.commit()

        async def init_db():
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS message_stats (
                        chat_id INTEGER,
                        user_id INTEGER,
                        username TEXT,
                        date TEXT,
                        count INTEGER DEFAULT 0,
                        PRIMARY KEY (chat_id, user_id, date)
                    )
                """)
                await db.commit()


async def init_db():
    async with aiosqlite.connect("sakurarep.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                sakura INTEGER DEFAULT 0,
                starter_bonus INTEGER DEFAULT 0,
                custom_name TEXT DEFAULT NULL
            )
        """)
        await db.commit()

        # 🎮 Лог игры "хел"
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hel_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                symbol TEXT,
                timestamp TEXT
            )
        """)

        # 🎁 Таблицы промокодов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                amount INTEGER,
                activations_left INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_usages (
                code TEXT,
                user_id INTEGER,
                PRIMARY KEY (code, user_id)
            )
        """)

        # 🛠 Проверка колонок в таблице users
        result = await db.execute("PRAGMA table_info(users)")
        user_columns = await result.fetchall()
        user_column_names = [col[1] for col in user_columns]

        if "custom_name" not in user_column_names:
            await db.execute("ALTER TABLE users ADD COLUMN custom_name TEXT")
            print("✅ Добавлено поле custom_name в таблицу users")

        if "chips" not in user_column_names:
            await db.execute("ALTER TABLE users ADD COLUMN chips INTEGER DEFAULT 0")
            print("✅ Добавлено поле chips в таблицу users")

        if "created_at" not in user_column_names:
            await db.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
            print("✅ Добавлено поле created_at в таблицу users")

        # 📜 Проверка структуры user_articles
        result = await db.execute("PRAGMA table_info(user_articles)")
        columns = await result.fetchall()
        column_names = [col[1] for col in columns]

        if not columns or ("chat_id" not in column_names or len(columns) == 4):
            await db.execute("DROP TABLE IF EXISTS user_articles")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_articles (
                    user_id INTEGER,
                    chat_id INTEGER,
                    article_index INTEGER,
                    last_used TEXT,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            print("✅ Пересоздана таблица user_articles с PRIMARY KEY (user_id, chat_id)")

        await db.commit()




        # ✅ Проверка колонки custom_id в таблице users
        row = await db.execute("PRAGMA table_info(users)")
        columns = await row.fetchall()
        column_names = [col[1] for col in columns]

        if "custom_id" not in column_names:
            await db.execute("ALTER TABLE users ADD COLUMN custom_id INTEGER")
            print("✅ Добавлена колонка custom_id в таблицу users")

        # ✅ Таблица admin_ranks
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_ranks (
                user_id INTEGER PRIMARY KEY,
                rank INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_rights (
                action TEXT PRIMARY KEY,
                min_rank INTEGER
            )
        """)

        # Заполняем по умолчанию, если пусто
        defaults = {
            "мут": 2,
            "размут": 2,
            "бан": 3,
            "разбан": 3,
            "смс": 2  # 👈 вот эта строка
        }

        for action, rank in defaults.items():
            await db.execute("""
                INSERT OR IGNORE INTO mod_rights (action, min_rank) VALUES (?, ?)
            """, (action, rank))

        # 👑 Добавление создателя как rank 5, если его ещё нет
        row = await db.execute("SELECT 1 FROM admin_ranks WHERE user_id = ?", (7333809850,))
        exists = await row.fetchone()
        if not exists:
            await db.execute("INSERT INTO admin_ranks (user_id, rank) VALUES (?, ?)", (7333809850, 5))
            print("👑 Создатель добавлен в admin_ranks с рангом 5")

        await db.commit()




# 🧱 Создаём таблицу blacklist при старте — до запуска middleware
async def ensure_blacklist_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY
            )
        """)
        await db.commit()

# Запускаем сразу
asyncio.get_event_loop().run_until_complete(ensure_blacklist_table())

def save_disabled_games():
    try:
        with open(DISABLED_GAMES_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {str(chat_id): list(games) for chat_id, games in disabled_games_by_chat.items()},
                f,
                ensure_ascii=False,
                indent=2
            )
        print("✅ Отключённые игры успешно сохранены.")
    except Exception as e:
        print(f"❌ Ошибка при сохранении отключённых игр: {e}")

def load_disabled_games():
    global disabled_games_by_chat
    disabled_games_by_chat = {}

    if not os.path.exists(DISABLED_GAMES_PATH):
        print("ℹ️ Файл отключённых игр не найден — создадим при первом сохранении.")
        return

    try:
        with open(DISABLED_GAMES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            for chat_id, game_list in data.items():
                try:
                    chat_id_int = int(chat_id)
                    disabled_games_by_chat[chat_id_int] = set(game_list)
                except (ValueError, TypeError):
                    print(f"⚠️ Пропущен некорректный chat_id: {chat_id}")
        print("✅ Отключённые игры успешно загружены.")
    except json.JSONDecodeError:
        print("❌ Ошибка: файл disabled_games.json повреждён. Будет перезаписан при следующем изменении.")
    except Exception as e:
        print(f"⚠️ Ошибка при загрузке disabled_games.json: {e}")



@dp.message(F.text.lower() == "/start")
async def start_command(message: Message):
    if message.chat.type != "private":
        return  # ❌ Игнорировать, если не ЛС

    user = message.from_user
    user_id = user.id
    bonus_text = ""

    # 🎁 Проверка и выдача стартового бонуса
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT starter_bonus FROM users WHERE user_id = ?", (user_id,))
        result = await row.fetchone()
        starter_bonus = result[0] if result else 0

        if not starter_bonus:
            await db.execute("""
                UPDATE users SET sakura = sakura + 5000, starter_bonus = 1
                WHERE user_id = ?
            """, (user_id,))
            await db.commit()
            bonus_text = (
                "\n\n🎁 <b>Ты получил 5000 🌸 стартового бонуса!</b>\n"
                "📢 Пиар-чат: <b>@piarsakur</b>"
            )

    # 🧾 Панель кнопок
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=" Бонус")],
            [KeyboardButton(text=" Команды"), KeyboardButton(text=" Донат")]
        ],
        resize_keyboard=True
    )

    # 📜 Приветственный текст
    text = (
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"Ты попал в уникального Telegram-бота <b>Sakura Bot</b> — здесь ты можешь играть, зарабатывать сакуру 🌸, "
        f"соревноваться с другими игроками и весело проводить время.\n"
        f"{bonus_text}\n\n"
        f"🧾 Напиши <code>помощь</code>, чтобы узнать список всех команд.\n"
        f"🎮 Удачи!"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.message(F.text.lower().startswith("мешок"))
async def show_bag(message: Message):
    user = message.from_user

    # Цель: либо reply-пользователь, либо сам
    if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
        target = message.reply_to_message.from_user
    else:
        target = user

    # 🔐 Приватность мешка (если чужой)
    if target.id != user.id:
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT bag_open FROM users WHERE user_id = ?", (target.id,))
            res = await row.fetchone()
            if not res or res[0] != 1:
                return await message.reply("🔒 Пользователь закрыл доступ к своему мешку.")

    # 📦 Получение данных
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura, chips FROM users WHERE user_id = ?", (target.id,))
        res = await row.fetchone()
        sakura, chips = res if res else (0, 0)

    await message.reply(
        f"💰 В мешке {target.first_name}\n"
        f"🌸 Сакур: <b>{sakura}</b>\n"
        f"♠️ Фишки: <b>{chips}</b>",
        parse_mode="HTML"
    )




@dp.message(F.text.lower() == "б")
async def show_balance(message: Message):
    user = message.from_user
    user_id = user.id
    chat_id = str(message.chat.id)

    # ⏳ Ждём окончания рулетки, если она в процессе
    if not spin_result_ready.get(chat_id, True):
        return await message.reply("⏳ Подожди окончания рулетки, затем повтори.")

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (user_id,))
        res = await row.fetchone()

    sakura = res[0] if res else 0
    sakura_formatted = "{:,}".format(sakura).replace(",", " ")

    await message.reply(
        f"<b>{user.first_name}</b>\n"
        f"<b>💰 Баланс: {sakura_formatted} 𝐬𝐚𝐤𝐮𝐫</b>",
        parse_mode="HTML"
    )




@dp.message(F.text.lower() == "+мешок")
async def open_bag(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET bag_open = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
    await message.reply("🔓 Ваш мешок теперь открыт. Другие могут смотреть его по реплаю.")



@dp.message(F.text.lower() == "-мешок")
async def close_bag(message: Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET bag_open = 0 WHERE user_id = ?", (user_id,))
        await db.commit()
    await message.reply("🔒 Ваш мешок теперь закрыт. Другие не могут просматривать его.")


@dp.message(F.text.lower().startswith("п "))
async def transfer_sakura(message: Message):
    sender = message.from_user
    args = message.text.strip().split()

    # 🔁 Только по reply
    if not message.reply_to_message or message.reply_to_message.from_user.is_bot:
        return await message.reply("⚠ Перевод возможен только по реплаю на сообщение пользователя.")

    recipient = message.reply_to_message.from_user
    recipient_id = recipient.id

    # 💰 Сумма
    try:
        amount = int(args[-1])
        if amount <= 0:
            return await message.reply("❌ Укажи положительное число.")
    except:
        return await message.reply("❌ Укажи корректную сумму сакуры числом.")

    if sender.id == recipient_id:
        return await message.reply("❌ Себе переводить нельзя.")

    # 💸 Баланс и перевод
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (sender.id,))
        res = await row.fetchone()
        balance = res[0] if res else 0

        if balance < amount:
            return await message.reply("❌ Недостаточно сакуры для перевода.")

        # Обеспечиваем, что получатель есть
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (recipient_id,))
        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (amount, sender.id))
        await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (amount, recipient_id))
        await db.commit()

    # 💬 Форматированный вывод
    sender_mention = f"<a href='tg://user?id={sender.id}'>{sender.first_name}</a>"
    recipient_mention = f"<a href='tg://user?id={recipient.id}'>{recipient.first_name}</a>"
    amount_formatted = "{:,}".format(amount).replace(",", " ")

    await message.reply(
        f"{sender_mention} перевел <b>{amount_formatted} 𝐬𝐚𝐤𝐮𝐫</b> для {recipient_mention}",
        parse_mode="HTML"
    )



@dp.message(F.text.lower() == "профиль")
async def profile_command(message: Message):
    user = message.from_user
    user_id = user.id

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("""
            SELECT sakura, username, created_at
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        res = await row.fetchone()

        if not res:
            return await message.reply("❌ Пользователь не найден в базе.")

        sakura, username, created_at = res
        sakura_formatted = "{:,}".format(sakura).replace(",", " ")
        display_name = username or user.first_name

        # 👑 katana
        if user_id == 7333809850:
            profile_text = (
                "👤 Пользователь: <b>katana</b>\n"
                "👨🏻‍🔧 <i>bot developer</i>\n\n"
                f"▫️ Баланс: <b>{sakura_formatted} сакур🌸</b>\n"
                f"▫️ ID: <code>888</code>"
            )
        else:
            # 📅 Расчёт дней с регистрации
            if created_at:
                try:
                    reg_date = datetime.fromisoformat(created_at)
                    days = (datetime.utcnow() - reg_date).days
                    reg_text = f"{days} дней"
                except:
                    reg_text = "неизвестно"
            else:
                reg_text = "неизвестно"

            profile_text = (
                f"👤 Пользователь: <b>{display_name}</b>\n"
                f"👨🏻‍🔧 дата регистрации в боте: <b>{reg_text}</b>\n\n"
                f"💚 Баланс: <b>{sakura_formatted} сакур🌸</b>\n"
                f"💚 ID: <code>{user_id}</code>"
            )

        await message.reply(profile_text, parse_mode="HTML")






@dp.message(F.text.lower().startswith("купить "))
async def buy_chips(message: Message):
    user = message.from_user
    args = message.text.strip().split()

    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>купить 3</code>", parse_mode="HTML")

    try:
        count = int(args[1])
        if count <= 0:
            return await message.reply("❌ Количество фишек должно быть положительным числом.")
    except:
        return await message.reply("❌ Укажи корректное количество фишек числом.")

    price_per_chip = 5000
    total_price = count * price_per_chip

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (user.id,))
        result = await row.fetchone()
        balance = result[0] if result else 0

        if balance < total_price:
            return await message.reply(
                f"❌ Недостаточно сакуры.\nНужно: {total_price} 🌸\nТвой баланс: {balance} 🌸"
            )

        await db.execute("""
            UPDATE users SET sakura = sakura - ?, chips = chips + ?
            WHERE user_id = ?
        """, (total_price, count, user.id))
        await db.commit()

    await message.reply(
        f"✅ Ты купил <b>{count} фишек</b> [♠️ Poker Chip] за <b>{total_price} 🌸</b>",
        parse_mode="HTML"
    )






@dp.message(F.text.lower().startswith(".ид"))
async def id_command(message: Message):
    args = message.text.strip().split()
    target_user = None

    # 👤 По реплаю
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    # 🔎 По username
    elif len(args) == 2 and args[1].startswith("@"):
        username = args[1][1:].lower()
        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT user_id FROM users WHERE lower(username) = ?", (username,))
            result = await row.fetchone()
        if not result:
            return await message.reply(
                f"⚠️ Пользователь @{username} не найден в базе данных.\n"
                f"Он должен хотя бы раз написать боту.",
                parse_mode="HTML"
            )
        user_id = result[0]
        target_user = types.User(id=user_id, is_bot=False, first_name=username)

    # 👤 Автор
    else:
        target_user = message.from_user

    user_id = target_user.id

    # 👑 Особый пользователь — katana
    if user_id == 7333809850:
        return await message.reply("👨🏻‍🔧 bot developer")  # просто текст, без форматирования

    # 🔍 Обычный ответ
    name = target_user.first_name
    await message.reply(f"🆔 <b>{name}</b>\n<code>{user_id}</code>", parse_mode="HTML")






#админский раздел
@dp.message(F.text.lower().startswith(("/выдать", "/забрать")))
async def admin_grant_or_take(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа к этой команде.")

    args = message.text.strip().split()
    if len(args) != 3:
        return await message.reply("⚠️ Формат: /выдать ID сумма или /забрать ID сумма")

    cmd, user_input, amount_str = args

    # 🔢 Сумма
    try:
        amount = int(amount_str)
        if amount <= 0:
            return await message.reply("⚠️ Сумма должна быть больше нуля.")
    except:
        return await message.reply("❌ Неверная сумма.")

    # 🔍 Определение user_id
    async with aiosqlite.connect(DB_PATH) as db:
        if user_input.startswith("@"):
            row = await db.execute("SELECT user_id FROM users WHERE username = ?", (user_input[1:],))
        else:
            try:
                uid = int(user_input)
                row = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
            except:
                return await message.reply("❌ Укажи корректный числовой ID или @username.")

        res = await row.fetchone()
        if not res:
            return await message.reply("❌ Пользователь не найден в базе.")

        user_id = res[0]

        # ✅ Обновляем баланс
        if cmd == "/выдать":
            await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return await message.reply(
                f"✅ Выдано <b>{amount} 🌸</b> пользователю <code>{user_id}</code>.",
                parse_mode="HTML"
            )

        elif cmd == "/забрать":
            await db.execute("UPDATE users SET sakura = MAX(sakura - ?, 0) WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return await message.reply(
                f"✅ Забрано <b>{amount} 🌸</b> у пользователя <code>{user_id}</code>.",
                parse_mode="HTML"
            )

        else:
            return await message.reply("❌ Неизвестная команда.")




#второй админский блок

def parse_time_arg(time_str: str) -> int:
    time_str = time_str.lower()
    if time_str.endswith("м"):
        return int(time_str[:-1]) * 60
    elif time_str.endswith("ч"):
        return int(time_str[:-1]) * 60 * 60
    elif time_str.endswith("д"):
        return int(time_str[:-1]) * 60 * 60 * 24
    return int(time_str) * 60  # по умолчанию — минуты









@dp.message(F.text.lower().startswith("бан"))
async def admin_ban(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа.")

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>бан ID</code>", parse_mode="HTML")

    try:
        target_id = int(args[1])
    except:
        return await message.reply("❌ Неверный ID")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO blacklist (user_id) VALUES (?)", (target_id,))
        await db.commit()

    await message.reply(f"🚫 Пользователь <code>{target_id}</code> забанен в боте.", parse_mode="HTML")




@dp.message(F.text.lower().startswith("разбан"))
async def admin_unban(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа.")

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>разбан ID</code>", parse_mode="HTML")

    try:
        target_id = int(args[1])
    except:
        return await message.reply("❌ Неверный ID")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blacklist WHERE user_id = ?", (target_id,))
        await db.commit()

    await message.reply(f"✅ Пользователь <code>{target_id}</code> разбанен в боте.", parse_mode="HTML")




#админ команды






# ========== ЗАГРУЗКА ФАЙЛОВ ==========
def load_spin_log():
    global spin_history_by_chat
    if os.path.exists(SPIN_LOG_PATH):
        try:
            with open(SPIN_LOG_PATH, "r", encoding="utf-8") as f:
                spin_history_by_chat = json.load(f)
        except:
            spin_history_by_chat = {}
    else:
        spin_history_by_chat = {}

def load_daily_top():
    global daily_top, daily_top_date
    if os.path.exists(DAILY_TOP_PATH):
        try:
            with open(DAILY_TOP_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                daily_top = data.get("top", {})
                daily_top_date = data.get("date", str(date.today()))
        except:
            daily_top = {}
            daily_top_date = str(date.today())
    else:
        daily_top = {}
        daily_top_date = str(date.today())

def save_spin_result(chat_id: int, result: int):
    chat_id = str(chat_id)
    spin_history_by_chat.setdefault(chat_id, []).insert(0, result)
    spin_history_by_chat[chat_id] = spin_history_by_chat[chat_id][:20]
    with open(SPIN_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(spin_history_by_chat, f)

def save_daily_top():
    with open(DAILY_TOP_PATH, "w", encoding="utf-8") as f:
        json.dump({"date": daily_top_date, "top": daily_top}, f)

load_spin_log()
load_daily_top()

# ========== ВСПОМОГАТЕЛЬНЫЕ ==========
def get_weighted_result_complex(chat_id: int, bets: dict) -> int:
    weights = {i: 1.0 for i in range(37)}
    all_numbers = []
    for b in bets.values():
        all_numbers += b.get("numbers", [])
    freq = Counter(all_numbers)
    for num, count in freq.items():
        weights[num] *= 0.85 ** count

    # 📉 Снижаем шанс на последние 2 числа
    history = spin_history_by_chat.get(str(chat_id), [])
    recent = history[:2]
    for n in recent:
        weights[n] *= 0.6

    # ♻️ Цветовые паттерны
    last_colors = []
    for n in history[:5]:
        if n == 0:
            last_colors.append("green")
        elif n in RED_NUMBERS:
            last_colors.append("red")
        else:
            last_colors.append("black")

    if len(set(last_colors[:3])) == 1:
        dominant = last_colors[0]
        if dominant == "red":
            for n in RED_NUMBERS:
                weights[n] *= 0.7
        elif dominant == "black":
            for n in BLACK_NUMBERS:
                weights[n] *= 0.7

    # 📛 Слишком частое число за 10 игр
    top_common = Counter(history[:10]).most_common(1)
    if top_common:
        frequent = top_common[0][0]
        weights[frequent] *= 0.5

    numbers, w = zip(*weights.items())
    return choices(numbers, weights=w, k=1)[0]

def get_number_multiplier(count: int) -> float:
    return round((36 / count) * 0.9, 2) if 0 < count <= 16 else 0.0

def update_daily_top(chat_id: int, user_id: int, name: str, amount: int):
    global daily_top, daily_top_date
    today = str(date.today())
    if daily_top_date != today:
        daily_top = {}
        daily_top_date = today
    cid = str(chat_id)
    uid = str(user_id)
    daily_top.setdefault(cid, {}).setdefault(uid, {"name": name, "win": 0})
    daily_top[cid][uid]["win"] += amount
    save_daily_top()


@dp.message(F.text.regexp(r"^\d+ "))
async def handle_text_spin(message: Message):
    if "roulette" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("🎰 Игра 'Рулетка' отключена в этом чате.")

    if message.chat.type == "private":
        return await message.reply("⚠ Игра доступна только в группах.")

    user = message.from_user
    uid = user.id
    cid = message.chat.id
    parts = message.text.lower().split()

    try:
        amount = int(parts[0])
        if amount <= 0:
            return
    except:
        return

    red = black = 0
    numbers = []

    for part in parts[1:]:
        if part == "к":
            red = amount
        elif part == "ч":
            black = amount
        elif part == "рандом":
            numbers = sample(range(1, 37), min(16, 36))
        elif part.isdigit():
            n = int(part)
            if 0 <= n <= 36:
                numbers.append(n)

    total = red + black + len(numbers) * amount

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (uid,))
        res = await row.fetchone()
        balance = res[0] if res else 0
        if balance < total:
            return await message.reply(f"❌ Недостаточно средств. Нужно: {total} 🌸")
        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (total, uid))
        await db.commit()

    chat_spin_bets.setdefault(cid, {})
    user_bets = chat_spin_bets[cid].setdefault(uid, {"entries": [], "sum": 0})
    user_bets["sum"] += total

    if red:
        user_bets["entries"].append({"type": "red", "amount": red})
    if black:
        user_bets["entries"].append({"type": "black", "amount": black})
    for n in numbers:
        user_bets["entries"].append({"type": "number", "number": n, "amount": amount})

    if cid not in chat_spin_start:
        chat_spin_start[cid] = time.time()

    mention = f"<a href='tg://user?id={uid}'>{user.first_name}</a>"
    lines = []

    if red:
        lines.append(f"{mention} Ставка принята: Сакура {red} 🌸 на 🔴")
    if black:
        lines.append(f"{mention} Ставка принята: Сакура {black} 🌸 на ⚫")
    for n in numbers:
        lines.append(f"{mention} Ставка принята: Сакура {amount} 🌸 на {n}")

    if lines:
        await message.reply("\n".join(lines), parse_mode="HTML")
    else:
        await message.reply("❌ Ставки не распознаны. Пример: <code>100 к ч 7</code>", parse_mode="HTML")





ROULETTE_STICKER_MAP = {
    0: "CAACAgIAAxkBAhxuEmh4HrohKPsWkWTa0Gc05T7obThoAAIxcQACwY-oS-C0sJmfrQEJNgQ",
    1: "CAACAgIAAxkBAhxuemh4ILxF7rfWvW6UhKWMxthYGrjYAAJibQACxX-pS_BXYj47_3YzNgQ",
    2: "CAACAgIAAxkBAhxt9mh4HhXZqE0YpUcoI860H0yN-TK5AAK7cAACa3ypS4wePbZsMruENgQ",
    3: "CAACAgIAAxkBAhxuIGh4HuvnDjcQumzMe-NksUsTQXxWAAJ_awAChs2pS_k2EHscsHMtNgQ",
    4: "CAACAgIAAxkBAhxuTGh4H8IkV9TrklcbH078ajwEXiF2AAIZbAACCZaoS8Npzo5cAAFidjYE",
    5: "CAACAgIAAxkBAhxtJWh4GQHtwkSSGonKkpMKZAZXzkjVAAJobwAC9nSpSzXRYISSrFfcNgQ",
    6: "CAACAgIAAxkBAhxuWGh4IAYceTEi6x_LF3haVjJYJ4EJAAIicAACSSCpS6betiFUYw5jNgQ",
    7: "CAACAgIAAxkBAhxudWh4IKnw5R16PbU1YNaZ1InZdViYAAKmZQACDFCwS846uoxbMOz3NgQ",
    8: "CAACAgIAAxkBAhxtPGh4GZGwtVC-gZa2UDzD-f2ZYj3eAAJzaQACjTKpSyt4s_ED4n5pNgQ",
    9: "CAACAgIAAxkBAhxuXWh4IBsOUr4mrFZwc8G6qDZxzOKVAAKDZgACtT6pS8GwDlCmkxgENgQ",
    10: "CAACAgIAAxkBAhxuFWh4Hsm6Xr_YWdKrFsQQKMUbPge0AAIIbAACf0qoS2X1__wZ-cAsNgQ",
    11: "CAACAgIAAxkBAhxuAWh4HmmEYUvH5TBvMgd-R56MRyYGAALeawACOX6pS2AJamyKKTikNgQ",
    12: "CAACAgIAAxkBAhxuJmh4HwX3qdlbA18_LmdiEfQlVDi5AAJzdwACpmSoSxkFgdm1vgewNgQ",
    13: "CAACAgIAAxkBAhxuc2h4IJktToOly_1VwpMR-BSg85_qAAL1ZQACpS2wS7gD91hUGXcTNgQ",
    14: "CAACAgIAAxkBAhxuY2h4IFgpAAG4D9PqgzWDdRanJr0rUwACaHUAAm06qUubaUhHHkRQtDYE",
    15: "CAACAgIAAxkBAhxuR2h4H7MT1PcNvnt2_GUTdfhJIqruAAJecgACuDmpS56q2j8hpkidNgQ",
    16: "CAACAgIAAxkBAhxuCGh4HoxlaiP3oCYsw7uQPbu4IBJ1AALedAACXYuoS2LbTcv4YdnxNgQ",
    17: "CAACAgIAAxkBAhxuKmh4Hx-OAyljFT_P9ekUHxKiloKsAAL5cQADyqhLPL6kTTa3_sM2BA",
    18: "CAACAgIAAxkBAhxuHGh4HtqYkcEEli1HtvcG7h8vvWYwAAK7cQAClqipS3j426tQd1ALNgQ",
    19: "CAACAgIAAxkBAhxt-mh4HiTwPoTMB-hwZZhwaGqII3HfAALTbwACFG-oSziEB1gSrr6wNgQ",
    20: "CAACAgIAAxkBAhxtL2h4GTVdyiFi96ZT4HIfUe7eXrOXAAKaYwACf62pS4iiUDSFR0a7NgQ",
    22: "CAACAgIAAxkBAhxuYWh4ID02s1cb42smo37TgEMZNYonAAKidQACW3ioS57bJaI8iXxFNgQ",
    23: "CAACAgIAAxkBAhxuEGh4HqptqrdCIz2NjsLzIJCMo2yBAALFcQACeY2oSxlUW8fv_LmXNgQ",
    24: "CAACAgIAAxkBAhxt5mh4HdUnNpIAAYyZ_Q48twyH6BCxDQAC4nkAArFxsEu3KApsLo6nfDYE",
    25: "CAACAgIAAxkBAhxtKmh4GR7tRWbPqCLQsnPbxxeKeDdNAAJ_cwACSKqpS3Z1Rtbz5CD0NgQ",
    26: "CAACAgIAAxkBAhxubWh4IH6eSivyjtVyjRfke_vumczyAAI-awAC__mxS4aGkpB9THDANgQ",
    27: "CAACAgIAAxkBAhxt_mh4HlGXIWgF09rDMlJbAuYq18bEAAI9bQACmPWoS_AIYwu8GfFtNgQ",
    28: "CAACAgIAAxkBAhxtLWh4GSqZ1NJlo5psyPuS8GYvDt2EAAK7bAACJSSoSxMweWRCg47LNgQ",
    29: "CAACAgIAAxkBAhxuN2h4H1OJWoYPlvgQMCfZysSgpvsbAALfbgACHtWpS17RRzdqh8rDNgQ",
    30: "CAACAgIAAxkBAhxuLmh4HytSzo6O0Yt39TK8IB0ze8JNAALcbQACOgawS6a-krzx53S7NgQ",
    31: "CAACAgIAAxkBAhxuBmh4HnolwyAOiYXuvG7idqIZsN_fAAIWbwACZGapS8XIF1b-veMENgQ",
    32: "CAACAgIAAxkBAhxt7Gh4HfM-hr2dEzroIQdATAIbOJCsAAJjcQACUEKxS6dWwVP1E7HPNgQ",
    33: "CAACAgIAAxkBAhxt8mh4HgTh5ovPDcNm5khE-tTzISpNAAJRcgACKJuxS7u3yZqd0ZC5NgQ",
    34: "CAACAgIAAxkBAhxuT2h4H8zeVtuFB5KHqBHIAmrexV6TAAJpdwACrqOxSwZCP_cVJSUTNgQ",
    35: "CAACAgIAAxkBAhxt_Gh4HkLLEsNpnBG48Iy745cSSxbEAAK9aAACzZeoSwtiUBA0gaUNNgQ",
    36: "CAACAgIAAxkBAhxuUWh4H9qaTSqbnVGejgkgVULhzaQeAAJRbwACL0moS4HHKaEP45LdNgQ",
}

@dp.message(F.text.lower().in_(["го", "/го"]))
async def spin_game(message: Message):
    if "roulette" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("🎰 Игра 'Рулетка' отключена в этом чате.")


    cid = message.chat.id
    author_uid = message.from_user.id
    now = time.time()

    if message.chat.type == "private":
        return await message.reply("⚠ Игра доступна только в группах.")
    if chat_spinning.get(cid):
        return await message.reply("⏳ Игра уже идёт.")
    if cid not in chat_spin_bets or not chat_spin_bets[cid]:
        return await message.reply("❌ Ещё нет ставок.")
    if author_uid not in chat_spin_bets[cid]:
        return await message.reply("⚠️ У тебя нет ставок.")

    start_ts = chat_spin_start.get(cid)
    if start_ts is None:
        return await message.reply("⚠ Ставки ещё не начались.")
    if now - start_ts < 12:
        return await message.reply(f"⏳ Подожди {int(12 - (now - start_ts))} сек.")

    chat_spinning[cid] = True
    spin_result_ready[cid] = False

    # 🎯 Генерация результата
    result = get_weighted_result_complex(cid, chat_spin_bets[cid])
    emoji = "🟢" if result == 0 else "🔴" if result in RED_NUMBERS else "⚫"
    save_spin_result(cid, result)
    spin_result_ready[cid] = True

    # 🎰 Показ анимации (стикер по числу)
    sticker_id = ROULETTE_STICKER_MAP.get(result)
    if sticker_id:
        sticker_msg = await message.reply_sticker(sticker_id)
        await asyncio.sleep(3)
        try:
            await sticker_msg.delete()
        except:
            pass

    winners = []
    stakes = []

    async with aiosqlite.connect(DB_PATH) as db:
        for uid, bet in chat_spin_bets[cid].items():
            entries = bet.get("entries", [])
            spent = bet.get("sum", 0)
            win = 0

            row = await db.execute("SELECT first_name FROM users WHERE user_id = ?", (uid,))
            u = await row.fetchone()
            name = u[0] if u else "Игрок"
            mention = f"<a href='tg://user?id={uid}'>{name}</a>"

            last_spin_bet[uid] = {"entries": entries, "sum": spent}

            for entry in entries:
                amount = entry["amount"]
                if entry["type"] == "red":
                    stakes.append(f"Сакура {amount} 🌸 на 🔴")
                    if result in RED_NUMBERS:
                        win += amount * 2
                elif entry["type"] == "black":
                    stakes.append(f"Сакура {amount} 🌸 на ⚫")
                    if result in BLACK_NUMBERS:
                        win += amount * 2
                elif entry["type"] == "number":
                    number = entry["number"]
                    stakes.append(f"Сакура {amount} 🌸 на {number}")
                    if number == result:
                        win += amount * 36

            if win > 0:
                await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (win, uid))
                update_daily_top(cid, uid, name, win)
                winners.append(f"{mention} выиграл на {result} — <b>{win}</b> 🌸")

        await db.commit()

    msg = [f"💠 Рулетка: <b>{result} {emoji}</b>"] + stakes + [""] + (winners or ["❌ Никто не выиграл."])
    text = "\n".join(msg)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=" Повторить", callback_data=f"repeat_{author_uid}"),
        InlineKeyboardButton(text=" Удвоить", callback_data=f"double_{author_uid}")
    ]])

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    # Очистка данных
    chat_spinning[cid] = False
    spin_result_ready.pop(cid, None)
    chat_spin_bets.pop(cid, None)
    chat_spin_start.pop(cid, None)




@dp.callback_query(F.data.startswith("double_"))
async def double_bet(call: CallbackQuery):
    if "roulette" in disabled_games_by_chat.get(call.message.chat.id, set()):
        return await call.answer("🎰 Игра 'Рулетка' отключена в этом чате.", show_alert=True)

    uid = call.from_user.id
    if str(uid) != call.data.split("_")[1]:
        return await call.answer("⛔ Не твоя ставка", show_alert=True)

    last_bet = last_spin_bet.get(uid)
    if not last_bet:
        return await call.answer("⚠️ Нет сохранённой ставки.")

    cid = call.message.chat.id
    chat_spin_start[cid] = time.time()

    base_entries = []
    doubled_sum = 0
    for entry in last_bet["entries"]:
        new_entry = entry.copy()
        new_entry["amount"] *= 2
        base_entries.append(new_entry)
        doubled_sum += new_entry["amount"]

    # Получаем баланс
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (uid,))
        res = await row.fetchone()
        balance = res[0] if res else 0

        if balance == 0:
            return await call.message.answer(
                f"⛔ <b><a href='tg://user?id={uid}'>{call.from_user.first_name}</a></b>, у тебя нет средств для ставки.",
                parse_mode="HTML"
            )

        if balance < doubled_sum:
            # ✂️ Пропорционально уменьшаем ставку
            factor = balance / doubled_sum
            adjusted_entries = []
            adjusted_sum = 0
            for entry in base_entries:
                adjusted_amount = max(int(entry["amount"] * factor), 1)
                adjusted = entry.copy()
                adjusted["amount"] = adjusted_amount
                adjusted_entries.append(adjusted)
                adjusted_sum += adjusted_amount
        else:
            adjusted_entries = base_entries
            adjusted_sum = doubled_sum

        # 💸 Списываем с баланса
        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (adjusted_sum, uid))
        await db.commit()

    # Записываем ставку
    if cid not in chat_spin_bets:
        chat_spin_bets[cid] = {}

    chat_spin_bets[cid][uid] = {
        "entries": adjusted_entries,
        "sum": adjusted_sum
    }

    user_name = call.from_user.first_name
    mention = f"<b><a href='tg://user?id={uid}'>{user_name}</a></b>"

    lines = []
    for entry in adjusted_entries:
        if entry["type"] == "red":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на 🔴")
        elif entry["type"] == "black":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на ⚫")
        elif entry["type"] == "number":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на {entry['number']}")

    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("repeat_"))
async def repeat_bet(call: CallbackQuery):
    if "roulette" in disabled_games_by_chat.get(call.message.chat.id, set()):
        return await call.answer("🎰 Игра 'Рулетка' отключена в этом чате.", show_alert=True)

    uid = call.from_user.id
    if str(uid) != call.data.split("_")[1]:
        return await call.answer("⛔ Не твоя ставка", show_alert=True)

    last_bet = last_spin_bet.get(uid)
    if not last_bet:
        return await call.answer("⚠️ Нет сохранённой ставки.")

    cid = call.message.chat.id
    chat_spin_start[cid] = time.time()

    entries = last_bet["entries"]
    total_sum = last_bet["sum"]

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (uid,))
        res = await row.fetchone()
        balance = res[0] if res else 0

        if balance < total_sum:
            return await call.message.answer(
                f"⛔ <b><a href='tg://user?id={uid}'>{call.from_user.first_name}</a></b>, у тебя недостаточно средств для повтора ставки.\n"
                f"Нужно: {total_sum} 🌸, у тебя: {balance} 🌸",
                parse_mode="HTML"
            )

        # 💸 Списываем
        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (total_sum, uid))
        await db.commit()

    # ✅ Записываем ставку
    if cid not in chat_spin_bets:
        chat_spin_bets[cid] = {}

    chat_spin_bets[cid][uid] = {
        "entries": entries,
        "sum": total_sum
    }

    user_name = call.from_user.first_name
    mention = f"<b><a href='tg://user?id={uid}'>{user_name}</a></b>"

    lines = []
    for entry in entries:
        if entry["type"] == "red":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на 🔴")
        elif entry["type"] == "black":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на ⚫")
        elif entry["type"] == "number":
            lines.append(f"{mention} Ставка принята: Сакура {entry['amount']} 🌸 на {entry['number']}")

    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()







@dp.message(F.text.lower() == "отменить")
async def cancel_spin(message: Message):
    cid = message.chat.id
    uid = message.from_user.id

    # 🚫 Если игра уже крутится — нельзя отменить
    if chat_spinning.get(cid):
        return await message.reply("⚠️ Игра уже идёт. Отменить ставку нельзя.")

    if cid in chat_spin_bets and uid in chat_spin_bets[cid]:
        bet = chat_spin_bets[cid].pop(uid)
        refund = bet.get("sum", 0)

        if refund > 0:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (refund, uid))
                await db.commit()

        # 💬 Сообщение с именем и возвратом
        user_name = message.from_user.first_name
        mention = f"<b><a href='tg://user?id={uid}'>{user_name}</a></b>"

        return await message.reply(
            f"{mention}\n🚫 Ставка отменена. Возврат: <b>{refund}</b> 🌸",
            parse_mode="HTML"
        )

    await message.reply("❌ У тебя нет активной ставки.")



@dp.message(F.text.lower() == "ставка")
async def show_my_bet(message: Message):
    cid = message.chat.id
    uid = message.from_user.id

    bet = chat_spin_bets.get(cid, {}).get(uid)
    if not bet or not bet.get("entries"):
        return await message.reply("❌ У тебя нет активной ставки.")

    entries = bet["entries"]
    user_name = message.from_user.first_name
    mention = f"<b><a href='tg://user?id={uid}'>{user_name}</a></b>"

    lines = [f"{mention}"]
    for entry in entries:
        if entry["type"] == "red":
            lines.append(f"Сакура {entry['amount']} 🌸 на 🔴")
        elif entry["type"] == "black":
            lines.append(f"Сакура {entry['amount']} 🌸 на ⚫")
        elif entry["type"] == "number":
            lines.append(f"Сакура {entry['amount']} 🌸 на {entry['number']}")

    await message.reply("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.lower().in_(["лог", "/лог"]))
async def spin_log_command(message: Message):
    if "log" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("📜 Просмотр лога отключён в этом чате.")

    cid = str(message.chat.id)

    # 🔒 Проверяем, не крутится ли ещё
    if not spin_result_ready.get(cid, True):
        return await message.reply("⏳ Подожди окончания текущей рулетки, потом будет лог.")

    hist = spin_history_by_chat.get(cid, [])
    if not hist:
        return await message.reply("⛔ Лог пуст. Ещё не было игр.")

    def fmt(n):
        color = "🟢" if n == 0 else "🔴" if n in RED_NUMBERS else "⚫"
        return f"<b>{n}</b> {color}"

    log_text = "\n".join(fmt(n) for n in hist[:10])  # 👈 Без заголовка
    await message.reply(log_text, parse_mode="HTML")





@dp.message(F.text.lower().in_(["/топ", "топ"]))
async def show_daily_top(message: Message):
    cid = str(message.chat.id)
    if cid not in daily_top or not daily_top[cid]:
        return await message.reply("📊 Пока нет данных для топа за сегодня.")

    top = sorted(daily_top[cid].items(), key=lambda x: x[1]['win'], reverse=True)[:10]
    lines = ["📊 <b>Топ игроков по выигрышу за сегодня:</b>"]
    for i, (uid, data) in enumerate(top, 1):
        lines.append(f"{i}. {data['name']} — <b>{data['win']} 🌸</b>")

    await message.reply("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.lower() == "/обнул_топ")
async def reset_top_command(message: Message):
    if message.chat.type != "private":
        return  # Только в ЛС

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 Команда доступна только администраторам.")

    daily_top.clear()
    await message.reply("✅ Все топы были успешно обнулены.")




#монетка
@dp.message(F.text.lower().startswith("монета"))
async def coin_command(message: Message):
    user = message.from_user
    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠️ Формат: <code>монета 100</code>", parse_mode="HTML")
    try:
        bet = int(args[1])
        if bet <= 0 or bet > 1_000_000:
            return await message.reply("⚠️ Ставка должна быть от 1 до 1 000 000 🌸.")
    except:
        return await message.reply("❌ Неверная сумма.")

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (user.id,))
        balance = (await row.fetchone() or [0])[0]

        if balance < bet:
            return await message.reply("❌ Недостаточно средств.")

        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (bet, user.id))
        await db.commit()

    # Сохраняем ставку в callback data
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🦅 Орёл", callback_data=f"coin:orel:{bet}"),
            InlineKeyboardButton(text="🎲 Решка", callback_data=f"coin:reshka:{bet}")
        ]
    ])

    await message.reply("🪙 Выбери сторону монеты:", reply_markup=buttons)

@dp.callback_query(F.data.startswith("coin:"))
async def handle_coin(callback: CallbackQuery):
    parts = callback.data.split(":")
    side = parts[1]  # orel / reshka
    bet = int(parts[2])
    user = callback.from_user
    user_id = user.id

    await callback.message.edit_text("🪙 Бросаем монету...")
    gif = await callback.message.answer_animation(
        "https://i.gifer.com/3X95.gif",
        caption="⏳ Подождите..."
    )

    await asyncio.sleep(2.5)
    try:
        await gif.delete()
    except:
        pass

    result = choice(["orel", "reshka"])
    win = bet * 2 if result == side else 0
    emoji = "🦅" if result == "orel" else "🎲"
    result_text = f"{emoji} <b>{result.upper()}</b>!"

    if win:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (win, user_id))
            await db.commit()
        final = f"{result_text}\n\n🎉 Победа! Вы выиграли <b>{win}</b> 🌸"
    else:
        final = f"{result_text}\n\n😢 Вы проиграли. Ставка <b>{bet}</b> 🌸 сгорела."

    await callback.message.answer(final, parse_mode="HTML")


def render_mines_buttons(opened: set, mines: set, reveal=False):
    """
    Генерирует кнопки для игры с отображением мин и открытых ячеек.
    :param opened: Множество открытых ячеек.
    :param mines: Множество мин.
    :param reveal: Флаг для отображения мин.
    :return: InlineKeyboardMarkup с кнопками.
    """
    buttons = []
    for i in range(25):
        if i in opened:
            # Если ячейка открыта, отображаем ее как безопасную или мину
            emoji = "💠" if i not in mines else "💣"
        else:
            # Если ячейка не открыта, показываем ? (или сами минусы при reveal)
            emoji = "❓" if not reveal else ("💣" if i in mines else "💠")

        # Добавляем кнопку для каждой ячейки
        buttons.append(InlineKeyboardButton(text=emoji, callback_data=f"mine:{i}"))

    # Кнопка для забора выигрыша
    rows = [buttons[i:i + 5] for i in range(0, 25, 5)]
    rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data="mine:take")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


mines_locks: dict[int, Lock] = {}

# 💣 Минное поле
@dp.message(F.text.lower().startswith("мины"))
async def start_mines(message: Message, state: FSMContext):
    if "mines" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("💣 Игра 'Мины' отключена в этом чате.")

    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("⚠ Игра доступна только в группах.")

    user_id = message.from_user.id
    if user_id in active_mines_games:
        return await message.reply("⚠️ У тебя уже идёт игра. Заверши её перед новой.")

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>мины 500</code>", parse_mode="HTML")

    try:
        bet = int(args[1])
        if bet <= 0 or bet > 500000000000000000000000000:
            return await message.reply("⚠ Укажи ставку от 1 до 500000000000000000000000000.")
    except ValueError:
        return await message.reply("⚠ Укажи корректную сумму.")

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (user_id,))
        balance = (await row.fetchone() or [0])[0]
        if balance < bet:
            return await message.reply("💸 Недостаточно сакуры.")
        await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (bet, user_id))
        await db.commit()

    total_cells = 25
    total_mines = 6
    mines = set(random.sample(range(total_cells), total_mines))
    opened = set()

    active_mines_games[user_id] = time.time()
    mines_locks[user_id] = Lock()

    await state.set_state(MineGame.playing)
    await state.update_data(mines=mines, opened=opened, bet=bet)

    mention = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"
    msg = await message.reply(
        f"👤 {mention}\n💣 Игра началась! Выбирай ячейки:",
        reply_markup=render_mines_buttons(opened, mines, reveal=False, show_take_button=False, show_cancel_button=True),
        parse_mode="HTML"
    )

    asyncio.create_task(end_mine_game_timeout(msg, state, user_id, bet))


async def end_mine_game_timeout(msg: Message, state: FSMContext, user_id: int, bet: int):
    await asyncio.sleep(120)
    if user_id not in active_mines_games:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (bet, user_id))
        await db.commit()

    try:
        await msg.edit_text(f"⏳ Время вышло! Ставка <b>{bet} 🌸</b> возвращена.", parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await state.clear()
    active_mines_games.pop(user_id, None)
    mines_locks.pop(user_id, None)


def render_mines_buttons(opened: set, mines: set, reveal=False, show_take_button=False, show_cancel_button=False):
    buttons = []
    for i in range(25):
        if i in opened:
            emoji = "💠" if i not in mines else "💣"
        else:
            emoji = "❓" if not reveal else ("💣" if i in mines else "💠")

        buttons.append(InlineKeyboardButton(text=emoji, callback_data=f"mine:{i}"))

    rows = [buttons[i:i + 5] for i in range(0, 25, 5)]

    if show_cancel_button:
        rows.append([InlineKeyboardButton(text="❌ Отменить", callback_data="mine:cancel")])
    if show_take_button:
        rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data="mine:take")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("mine:"), MineGame.playing)
async def handle_mine_click(callback: CallbackQuery, state: FSMContext):
    if "mines" in disabled_games_by_chat.get(callback.message.chat.id, set()):
        return await callback.answer("💣 Игра 'Мины' отключена в этом чате.", show_alert=True)

    action = callback.data.split(":")[1]
    user_id = callback.from_user.id

    # Игровая блокировка на 0.2 сек
    lock = mines_locks.setdefault(user_id, Lock())
    if lock.locked():
        return await callback.answer("⏳ Подожди чуть-чуть...")

    async with lock:
        if user_id not in active_mines_games:
            return await callback.answer("⚠ Игра уже завершена.")

        data = await state.get_data()
        mines = data["mines"]
        opened = data["opened"]
        bet = data["bet"]

        active_mines_games[user_id] = time.time()

        if action == "cancel":
            if opened:
                return await callback.answer("❌ Уже начато.")
            active_mines_games.pop(user_id, None)
            await state.clear()
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (bet, user_id))
                await db.commit()
            await callback.message.edit_text("❌ Игра отменена. Ставка <b>возвращена</b>.", parse_mode="HTML")
            return await callback.answer("Возврат")

        if action == "take":
            profit = int(bet * (1 + len(opened) * 0.35))
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (profit, user_id))
                await db.commit()
            await state.clear()
            active_mines_games.pop(user_id, None)
            await callback.message.edit_text(
                f"💰 Ты забрал: <b>{profit} 🌸</b>\nИгра завершена.",
                parse_mode="HTML"
            )
            return await callback.answer("💰 Забрал!")

        try:
            cell = int(action)
        except:
            return await callback.answer("❌ Ошибка.")

        if cell in opened:
            return await callback.answer("🔁 Уже открыта!")

        opened.add(cell)

        if cell in mines:
            await state.clear()
            active_mines_games.pop(user_id, None)
            try:
                await callback.message.edit_text(
                    "💥 Ты попал на мину!\n❌ Ставка проиграна.",
                    reply_markup=render_mines_buttons(opened, mines, reveal=True),
                    parse_mode="HTML"
                )
            except TelegramBadRequest:
                pass
            return await callback.answer("💥 Бум!")

        await state.update_data(opened=opened)

        try:
            await callback.message.edit_reply_markup(
                reply_markup=render_mines_buttons(opened, mines, reveal=False, show_take_button=True)
            )
        except TelegramBadRequest:
            pass

        await callback.answer("✅")




HELP_TEXT = (
    "💠 <b>Команды Sakura Bot</b>\n\n"
    "👤 <b>Профиль:</b>\n"
    "▫️ <b>профиль</b> — твой профиль\n"
    "▫️ <b>мешок</b> — показать мешок (или по реплаю)\n"
    "▫️ <b>б</b> — показать баланс\n"
    "▫️ <b>+мешок / -мешок</b> — открыть / закрыть доступ\n\n"

    "💸 <b>Переводы:</b>\n"
    "▫️ <b>п (реплай) (сумма)</b> — передать сакуру\n\n"

    "🎮 <b>Игры:</b>\n"
    "▫️ <b>мины (сумма)</b> — игра в мины\n"
    "▫️ <b>монета (сумма)</b> — орёл или решка\n"
    "▫️ <b>(сумма) к ч 5 9</b> — ставка в рулетке\n"
    "▫️ <b>го</b> — запустить рулетку\n"
    "▫️ <b>лог</b> — история рулеток\n"
    "▫️ <b>дуэль (сумма) (реплай)</b> — PvP дуэль\n"
    "▫️ <b>хел (сумма)</b> — покер-масть игра\n\n"

    "📈 <b>Прочее:</b>\n"
    "▫️ <b>ид</b> — узнать ID\n"
    "▫️ <b>бонус</b> — ежедневный бонус 🌸\n"
    "▫️ <b>пинг</b> — проверить связь\n\n"

    "💎 <b>Донат:</b>\n"
    "▫️ <b>донат</b> — напиши в ЛС бота"
)


def help_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Закрыть", callback_data="help:close")
    return builder.as_markup()


@dp.message(F.text.lower().in_(["помощь", "команды"]))
async def help_command(message: Message):
    await message.reply(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_markup()
    )


@dp.callback_query(F.data == "help:close")
async def help_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()




@dp.message(F.text.lower() == "/help")
async def help_command(message: Message):
    text = (
        "💠 <b>Команды Sakura Bot</b>\n\n"
        "👤 <b>Профиль:</b>\n"
        "▫️ <b>профиль</b> — твой профиль\n"
        "▫️ <b>мешок</b> — показать мешок (или по реплаю)\n"
        "▫️ <b>б</b> — показать баланс\n"
        "▫️ <b>+мешок / -мешок</b> — открыть / закрыть доступ\n\n"

        "💸 <b>Переводы:</b>\n"
        "▫️ <b>п (реплай) (сумма)</b> — передать сакуру\n\n"

        "🎮 <b>Игры:</b>\n"
        "▫️ <b>мины (сумма)</b> — игра в мины\n"
        "▫️ <b>монета (сумма)</b> — орёл или решка\n"
        "▫️ <b>(сумма) к ч 5 9</b> — ставка в рулетке\n"
        "▫️ <b>го</b> — запустить рулетку\n"
        "▫️ <b>лог</b> — история рулеток\n"
        "▫️ <b>дуэль (сумма) (реплай)</b> — PvP дуэль\n"
        "▫️ <b>хел (сумма)</b> — покер-масть игра\n\n"

        "📈 <b>Прочее:</b>\n"
        "▫️ <b>ид</b> — узнать ID\n"
        "▫️ <b>бонус</b> — ежедневный бонус 🌸\n"
        "▫️ <b>пинг</b> — проверить связь\n\n"

        "💎 <b>Донат:</b>\n"
        "▫️ <b>донат</b> — напиши в ЛС бота\n\n"
        "📢 Остальные команды смотри в канале @settskamss"
    )

    await message.reply(text, parse_mode="HTML")







@dp.message(F.text.lower().in_(["+чат", "-чат"]))
async def manage_chat(message: Message):
    if message.chat.id != -1002835369234:
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа к этой команде.")

    if message.text.lower() == "+чат":
        perms = types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True,
            can_pin_messages=True
        )
        await bot.set_chat_permissions(chat_id=message.chat.id, permissions=perms)
        await message.reply("🔓 Чат открыт. Теперь все могут писать.")
    else:
        perms = types.ChatPermissions(
            can_send_messages=False
        )
        await bot.set_chat_permissions(chat_id=message.chat.id, permissions=perms)
        await message.reply("🔒 Чат закрыт. Только админы могут писать.")





from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

GROUP_ID = -1002835369234


@dp.message(F.text.startswith("создать"))
async def create_bonus_check(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("⛔ Доступ только для админа.")

    args = message.text.split()
    if len(args) != 3:
        return await message.reply("⚠ Формат: создать (сумма) (кол-во_активаций)")

    try:
        amount = int(args[1])
        limit = int(args[2])
    except:
        return await message.reply("⚠ Укажи сумму и кол-во числом.")

    btns = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_bonus:{amount}:{limit}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_bonus")
        ]
    ])
    await message.reply(f"🔐 Создать бонус на {amount} 🌸 — {limit} активаций?", reply_markup=btns)


@dp.callback_query(F.data.startswith("confirm_bonus:"))
async def confirm_bonus_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return await callback.answer("⛔ Только для админа", show_alert=True)

    _, amount, limit = callback.data.split(":")
    amount = int(amount)
    limit = int(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO group_bonuses (amount, max_activations) VALUES (?, ?)", (amount, limit))
        bonus_id = cursor.lastrowid
        await db.commit()

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎁 Получить", callback_data=f"claim_bonus:{bonus_id}")]
    ])
    text = f"🎉 <b>Ивент открыт!</b>\n🎁 Бонус: <b>{amount} 🌸</b>\n👥 Активаций: <b>{limit}</b>"
    await bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=btn, parse_mode="HTML")
    await callback.message.edit_text("✅ Бонус отправлен в группу!")

@dp.callback_query(F.data == "cancel_bonus")
async def cancel_bonus(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отменено.")



@dp.callback_query(F.data.startswith("claim_bonus:"))
async def claim_bonus(callback: CallbackQuery):
    user_id = callback.from_user.id
    bonus_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT amount, max_activations, activated_by FROM group_bonuses WHERE bonus_id = ?", (bonus_id,))
        bonus = await row.fetchone()

        if not bonus:
            try:
                await callback.answer("❌ Бонус не найден", show_alert=True)
            except:
                pass
            return

        amount, max_activations, activated_by_raw = bonus
        activated_by = set(map(int, activated_by_raw.split(","))) if activated_by_raw else set()

        if user_id in activated_by:
            try:
                await callback.answer("❌ Ты уже получал этот бонус.", show_alert=True)
            except:
                pass
            return

        if len(activated_by) >= max_activations:
            try:
                await callback.answer("❌ Бонус уже исчерпан.", show_alert=True)
            except:
                pass
            return

        # ✅ Добавляем пользователя
        activated_by.add(user_id)
        await db.execute(
            "UPDATE group_bonuses SET activated_by = ? WHERE bonus_id = ?",
            (",".join(map(str, activated_by)), bonus_id)
        )
        await db.execute(
            "UPDATE users SET sakura = sakura + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

    # 🟢 Попытка ответить (нажатие на кнопку)
    try:
        await callback.answer(f"✅ Получено {amount} 🌸", show_alert=True)
    except:
        pass  # запрос устарел

    # 🔄 Обновим сообщение в группе
    try:
        if callback.message.chat.id == GROUP_ID:
            remaining = max_activations - len(activated_by)
            new_text = (
                f"🎉 <b>Ивент открыт!</b>\n"
                f"🎁 Бонус: <b>{amount} 🌸</b>\n"
                f"👥 Осталось активаций: <b>{remaining}</b>"
            )
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Получить", callback_data=f"claim_bonus:{bonus_id}")]
            ])
            await callback.message.edit_text(new_text, reply_markup=btn, parse_mode="HTML")
    except:
        pass




# 🎁 Общая логика бонуса
async def bonus_command_base(user_id: int, send):
    # 🔍 Проверка подписки
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ("left", "kicked"):
            raise Exception("Not subscribed")
    except:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Проверить", callback_data="check_bonus")]
        ])
        return await send("📢 Чтобы получить бонус, подпишись на канал!", reply_markup=kb)

    # 🎁 Бонус
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT sakura, last_bonus FROM users WHERE user_id = ?", (user_id,))
        res = await row.fetchone()

        if not res:
            return await send("❌ Пользователь не найден в базе.")

        sakura, last_bonus = res
        now = datetime.now()

        if last_bonus:
            try:
                last_time = datetime.fromisoformat(last_bonus)
                if now - last_time < timedelta(hours=24):
                    remaining = timedelta(hours=24) - (now - last_time)
                    hours, remainder = divmod(remaining.seconds, 3600)
                    minutes = remainder // 60
                    return await send(f"⏳ Бонус уже получен. Повтори через {hours} ч. {minutes} мин.")
            except:
                pass

        # 💰 Выдаём бонус
        new_sakura = sakura + BONUS_AMOUNT
        await db.execute("""
            UPDATE users
            SET sakura = ?, last_bonus = ?
            WHERE user_id = ?
        """, (new_sakura, now.isoformat(), user_id))
        await db.commit()

    await send(f"🎁 Ты получил <b>{BONUS_AMOUNT} 🌸</b>!\nПовтори через 24 часа.", parse_mode="HTML")


# 📥 Бонус по команде "бонус"
@dp.message(F.text.lower() == "бонус")
async def bonus_command(message: Message):
    await bonus_command_base(message.from_user.id, message.reply)


# 📥 Бонус после кнопки "Проверить"
@dp.callback_query(F.data == "check_bonus")
async def check_bonus_callback(call: CallbackQuery):
    try:
        await call.message.delete()
    except:
        pass
    await bonus_command_base(call.from_user.id, call.message.answer)




@dp.message(F.text.lower().startswith("дуэль"))
async def start_duel(message: Message):
    if "duel" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("⚔️ Игра 'Дуэль' отключена в этом чате.")

    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id

    args = message.text.strip().split()
    if len(args) < 2:
        return await message.reply("⚠ Формат: <code>дуэль [сумма] [@юзер|id]</code>", parse_mode="HTML")

    if args[1].lower() == "нет":
        if chat_id in duel_requests:
            duel_info = duel_requests[chat_id]
            if user_id in duel_info:
                duel_requests[chat_id].pop(user_id)
                return await message.reply("❌ Дуэль отменена.")
        return await message.reply("❌ У тебя нет активной дуэли.")

    try:
        amount = int(args[1])
        if amount <= 0 or amount > 10_000:
            return await message.reply("⚠ Укажи ставку от 1 до 10000.")
    except:
        return await message.reply("⚠ Укажи корректную сумму.")

    # 👤 Оппонент
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(args) >= 3:
        try:
            target_id = int(args[2]) if not args[2].startswith("@") else None
            if target_id:
                member = await bot.get_chat_member(chat_id, target_id)
                target = member.user
            else:
                return await message.reply("⚠ Укажи ID пользователя.")
        except:
            return await message.reply("⚠ Не удалось найти пользователя.")
    else:
        return await message.reply("⚠ Ответь на сообщение игрока или укажи его ID.")

    if not target or target.id == user_id or target.is_bot:
        return await message.reply("❌ Нельзя вызвать самого себя или бота.")

    if user_id in active_duels or target.id in active_duels:
        return await message.reply("⚠ Кто-то из участников уже в дуэли.")

    # 💰 Проверка баланса (на сакуру)
    async with aiosqlite.connect(DB_PATH) as db:
        for uid in [user_id, target.id]:
            row = await db.execute("SELECT sakura FROM users WHERE user_id = ?", (uid,))
            res = await row.fetchone()
            if not res or res[0] < amount:
                return await message.reply(f"💸 У <a href='tg://user?id={uid}'>пользователя</a> недостаточно сакуры.", parse_mode="HTML")

    duel_requests.setdefault(chat_id, {})[target.id] = {
        "initiator": user,
        "amount": amount,
        "msg": None
    }
    active_duels.update({user_id, target.id})

    mention = f"<a href='tg://user?id={user_id}'>{user.first_name}</a>"
    target_mention = f"<a href='tg://user?id={target.id}'>{target.first_name}</a>"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ Принять дуэль", callback_data=f"accept_duel:{user_id}:{amount}")
    ]])

    msg = await message.answer(
        f"🎯 {mention} вызывает {target_mention} на дуэль за <b>{amount} 🌸</b>!\n"
        f"{target_mention}, у тебя 2 минуты на ответ.",
        reply_markup=kb,
        parse_mode="HTML"
    )
    duel_requests[chat_id][target.id]["msg"] = msg

    async def timeout_duel():
        await asyncio.sleep(DUEL_TIMEOUT)
        if chat_id in duel_requests and target.id in duel_requests[chat_id]:
            duel_requests[chat_id].pop(target.id, None)
            active_duels.discard(user_id)
            active_duels.discard(target.id)
            try:
                await msg.edit_text("⏳ Дуэль не принята. Отмена.")
            except:
                pass

    asyncio.create_task(timeout_duel())



@dp.callback_query(F.data.startswith("accept_duel:"))
async def accept_duel(callback: CallbackQuery):
    data = callback.data.split(":")
    initiator_id = int(data[1])
    amount = int(data[2])
    accepter = callback.from_user
    chat_id = callback.message.chat.id

    if chat_id not in duel_requests or accepter.id not in duel_requests[chat_id]:
        return await callback.answer("❌ Дуэль недействительна.")

    if accepter.id != callback.from_user.id:
        return await callback.answer("❌ Это не твоя дуэль.")

    info = duel_requests[chat_id].pop(accepter.id)
    initiator = info["initiator"]
    active_duels.discard(initiator.id)
    active_duels.discard(accepter.id)

    await callback.message.edit_text("⚔️ Дуэль начинается!")

    name1 = f"<a href='tg://user?id={initiator.id}'>{initiator.first_name}</a>"
    msg = await callback.message.answer(f"🎲 Первый бросает кубик: {name1}")
    dice1 = await bot.send_dice(chat_id=chat_id, emoji="🎲")
    roll1 = dice1.dice.value
    await asyncio.sleep(2)

    name2 = f"<a href='tg://user?id={accepter.id}'>{accepter.first_name}</a>"
    await msg.edit_text(f"🎲 Второй бросает кубик: {name2}")
    dice2 = await bot.send_dice(chat_id=chat_id, emoji="🎲")
    roll2 = dice2.dice.value
    await asyncio.sleep(2)

    winner = None
    if roll1 > roll2:
        winner = initiator.id
        loser = accepter.id
    elif roll2 > roll1:
        winner = accepter.id
        loser = initiator.id

    async with aiosqlite.connect(DB_PATH) as db:
        if winner:
            await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (amount, winner))
            await db.execute("UPDATE users SET sakura = sakura - ? WHERE user_id = ?", (amount, loser))
        await db.commit()

    result_text = f"🎲 {name1}: <b>{roll1}</b>\n🎲 {name2}: <b>{roll2}</b>\n\n"
    if winner:
        result_text += f"🏆 Победил: <a href='tg://user?id={winner}'>Игрок</a> и получил <b>{amount} 🌸</b>"
    else:
        result_text += "🤝 Ничья! Ставки возвращены."

    await callback.message.answer(result_text, parse_mode="HTML")
    await callback.answer()






from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery



@dp.message(F.text.lower() == "/купили_ид")
async def show_custom_ids(message: Message):
    if message.chat.type != "private":
        return
    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа.")

    await send_custom_id_page(message.chat.id, page=0)

# Отправка страницы
async def send_custom_id_page(chat_id: int, page: int):
    offset = page * PAGE_SIZE

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("""
            SELECT user_id, custom_id FROM users
            WHERE custom_id IS NOT NULL
            ORDER BY custom_id ASC
            LIMIT ? OFFSET ?
        """, (PAGE_SIZE, offset))
        users = await row.fetchall()

        count_row = await db.execute("SELECT COUNT(*) FROM users WHERE custom_id IS NOT NULL")
        total = (await count_row.fetchone())[0]

    if not users:
        return await bot.send_message(chat_id, "❌ Пока никто не купил ID.")

    lines = [f"{i + 1 + offset}. ID: <code>{cid}</code> | <a href='tg://user?id={uid}'>Пользователь</a>"
             for i, (uid, cid) in enumerate(users)]

    # Кнопки
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"customid:page:{page - 1}"))
    if (offset + PAGE_SIZE) < total:
        buttons.append(InlineKeyboardButton("➡️ Далее", callback_data=f"customid:page:{page + 1}"))

    kb = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

    await bot.send_message(chat_id,
        f"📋 <b>Список купленных ID (стр. {page + 1})</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb
    )

# Обработка кнопок
@dp.callback_query(F.data.startswith("customid:page:"))
async def handle_custom_id_pagination(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await callback.message.delete()
    await send_custom_id_page(callback.message.chat.id, page)
    await callback.answer()


@dp.message(F.text.lower().startswith("дать"))
async def admin_give_self_currency(message: Message):
    # Только в личке
    if message.chat.type != "private":
        return

    # Только от админа
    if message.from_user.id != 7333809850:
        return

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>дать 10000</code>", parse_mode="HTML")

    try:
        amount = int(args[1])
        if amount <= 0:
            return await message.reply("❌ Укажи положительное число.")
    except:
        return await message.reply("❌ Неверный формат суммы.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (amount, 7333809850))
        await db.commit()

    await message.reply(f"✅ Выдано <b>{amount} 🌸</b> пользователю <code>7333809850</code>", parse_mode="HTML")




#админы стафф
@dp.message(F.text.lower() == "кто админ")
async def show_admins(message: Message):
    if message.chat.id != -1002835369234:
        return  # Только в нужной группе

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute("SELECT user_id, rank FROM admin_ranks ORDER BY rank DESC")
        admins = await rows.fetchall()

        if not admins:
            return await message.reply("⚠️ Админов пока нет.")

        rank_titles = {
            5: "⭐️⭐️⭐️⭐️⭐️ <b>Создатели</b>",
            4: "⭐️⭐️⭐️⭐️ <b>Администраторы</b>",
            3: "⭐️⭐️⭐️ <b>Модераторы</b>",
            2: "⭐️⭐️ <b>Стажёры</b>",
            1: "⭐️ <b>Младшие админы</b>",
        }

        rank_blocks = {rank: [] for rank in rank_titles}

        for uid, rank in admins:
            cursor = await db.execute("SELECT first_name FROM users WHERE user_id = ?", (uid,))
            row = await cursor.fetchone()
            name = row[0] if row else f"ID {uid}"
            mention = f"<a href='tg://user?id={uid}'>{name}</a>"
            rank_blocks[rank].append(mention)

    result = "<b>👮 Список админов:</b>\n\n"
    for rank in sorted(rank_titles.keys(), reverse=True):
        members = rank_blocks[rank]
        if members:
            result += f"{rank_titles[rank]}\n" + "\n".join(members) + "\n\n"

    await message.reply(result.strip(), parse_mode="HTML")



@dp.message(F.text.lower().startswith("повысить"))
async def promote_admin(message: Message):
    if message.chat.id != -1002835369234:
        return

    if message.from_user.id != 7333809850:
        return await message.reply("⛔ Только создатель может повышать.")

    parts = message.text.strip().split()
    if len(parts) != 3:
        return await message.reply("⚠ Формат: повысить id ранг")

    try:
        target_id = int(parts[1])
        rank = int(parts[2])
        if not (1 <= rank <= 4):
            return await message.reply("⚠ Укажи ранг от 1 до 4.")
    except:
        return await message.reply("⚠ Неверный формат ID или ранга.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO admin_ranks (user_id, rank) VALUES (?, ?)", (target_id, rank))
        await db.commit()

    await message.reply(f"✅ Пользователь <code>{target_id}</code> повышен до ранга {rank}.", parse_mode="HTML")



@dp.message(F.text.lower().startswith("снять"))
async def remove_admin(message: Message):
    if message.chat.id != -1002835369234:
        return

    if message.from_user.id != 7333809850:
        return await message.reply("⛔ Только создатель может снимать.")

    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.reply("⚠ Формат: снять id")

    try:
        target_id = int(parts[1])
    except:
        return await message.reply("⚠ Неверный ID.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admin_ranks WHERE user_id = ?", (target_id,))
        await db.commit()

    await message.reply(f"🚫 Пользователь <code>{target_id}</code> снят с админки.", parse_mode="HTML")



async def get_user_rank(uid: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT rank FROM admin_ranks WHERE user_id = ?", (uid,))
        result = await row.fetchone()
        return result[0] if result else 0  # 0 — нет прав

async def check_access(user_id: int, action: str) -> bool:
    user_rank = await get_user_rank(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT min_rank FROM mod_rights WHERE action = ?", (action,))
        rule = await row.fetchone()
        return user_rank >= (rule[0] if rule else 999)

async def get_target_user(message: Message) -> types.User | None:
    if message.reply_to_message:
        return message.reply_to_message.from_user
    parts = message.text.split()
    if len(parts) >= 2:
        try:
            uid = int(parts[1])
            member = await message.bot.get_chat_member(message.chat.id, uid)
            return member.user
        except:
            return None
    return None





@dp.message(F.text.lower().startswith("мут"))
async def mute_user(message: Message):
    if message.chat.id != -1002835369234:
        return

    if not await check_access(message.from_user.id, "мут"):
        return await message.reply("⛔ У тебя нет прав использовать мут.")

    # 🎯 Цель — reply или ID
    target = await get_target_user(message)
    if not target:
        return await message.reply("⚠ Укажи пользователя ответом или через ID/username.")

    # 🕐 Длительность — 1 час
    until = datetime.utcnow() + timedelta(hours=1)

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await message.reply(
            f"🔇 {target.mention_html()} замучен на <b>1 час</b>.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"⚠ Ошибка при муте: {e}")



def parse_duration(text: str) -> timedelta:
    import re
    match = re.match(r"(\d+)([чмд])", text)
    if not match:
        return timedelta(minutes=10)
    num, unit = match.groups()
    num = int(num)
    if unit == "м":
        return timedelta(minutes=num)
    elif unit == "ч":
        return timedelta(hours=num)
    elif unit == "д":
        return timedelta(days=num)
    return timedelta(minutes=10)



@dp.message(F.text.lower().startswith("!дк"))
async def set_mod_rank(message: Message):
    if message.from_user.id != 7333809850:
        return

    parts = message.text.lower().split()
    if len(parts) != 3:
        return await message.reply("⚠ Формат: !дк [действие] [ранг]\nНапример: !дк мут 2")

    action = parts[1]
    try:
        rank = int(parts[2])
        if not (1 <= rank <= 5):
            return await message.reply("⚠ Укажи ранг от 1 до 5.")
    except:
        return await message.reply("⚠ Укажи ранг числом.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO mod_rights (action, min_rank)
            VALUES (?, ?) ON CONFLICT(action) DO UPDATE SET min_rank = excluded.min_rank
        """, (action, rank))
        await db.commit()

    await message.reply(f"✅ Доступ к команде <b>{action}</b> установлен с ранга <b>{rank}</b>.", parse_mode="HTML")



@dp.message(F.text.lower() == "!мдк")
async def show_mod_ranks(message: Message):
    if message.from_user.id != 7333809850:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute("SELECT action, min_rank FROM mod_rights")
        data = await rows.fetchall()

    lines = [f"🔧 <b>{a}</b> — с ранга <b>{r}</b>" for a, r in data]
    await message.reply("\n".join(lines), parse_mode="HTML")



@dp.message(F.text.lower().startswith("размут"))
async def unmute_user(message: Message):
    if message.chat.id != -1002835369234:
        return

    if not await check_access(message.from_user.id, "размут"):
        return await message.reply("⛔ Недостаточно прав для размутить.")

    target = await get_target_user(message)
    if not target:
        return await message.reply("⚠ Укажи ID или сделай реплай.")

    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=types.ChatPermissions(can_send_messages=True)
        )
        await message.reply(f"✅ Пользователь {target.mention_html()} размучен.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"⚠ Ошибка: {e}")



@dp.message(F.text.startswith("/бан"))
async def ban_user(message: Message):
    CHAT_ID = -1002835369234  # Укажи ID нужного чата

    # ✅ Проверка: работает только в указанном чате
    if message.chat.id != CHAT_ID:
        return

    # ✅ Проверка доступа (твоя функция)
    if not await check_access(message.from_user.id, "бан"):
        return await message.reply("⛔ У тебя нет прав использовать эту команду.")

    # 📌 Получаем пользователя: либо по reply, либо по ID
    target_user = None

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("⚠ Укажи ID пользователя или ответь на его сообщение.")
        try:
            user_id = int(args[1])
            chat_member = await message.bot.get_chat_member(message.chat.id, user_id)
            target_user = chat_member.user
        except Exception as e:
            return await message.reply(f"⚠ Не удалось найти пользователя: {e}")

    # 🔒 Пытаемся забанить
    try:
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(
            f"⛔ Пользователь <b>{target_user.full_name}</b> был забанен <b>навсегда</b>.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка при бане: {e}")







@dp.message(F.text.lower().startswith("/разбан"))
async def unban_user(message: Message):
    CHAT_ID = -1002835369234  # Укажи нужный ID чата

    # ✅ Проверка чата
    if message.chat.id != CHAT_ID:
        return

    # ✅ Проверка доступа
    if not await check_access(message.from_user.id, "разбан"):
        return await message.reply("⛔ Недостаточно прав для разбана.")

    # 🎯 Получаем пользователя по реплаю или ID
    target = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user
    else:
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("⚠ Укажи ID или сделай реплай.")
        try:
            user_id = int(args[1])
            member = await message.bot.get_chat_member(message.chat.id, user_id)
            target = member.user
        except Exception as e:
            return await message.reply(f"❌ Не удалось найти пользователя: {e}")

    # 🔓 Разбан
    try:
        await message.bot.unban_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            only_if_banned=True
        )
        await message.reply(f"✅ {target.mention_html()} разбанен.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"⚠ Ошибка при разбане: {e}")




@dp.message(F.text.lower().startswith("-смс"))
async def delete_message_pair(message: Message):
    if message.chat.id != -1002835369234:
        return

    if not await check_access(message.from_user.id, "смс"):
        return await message.reply("⛔ У тебя нет прав использовать -смс.")

    if not message.reply_to_message:
        return await message.reply("⚠ Используй как ответ на сообщение.")

    try:
        # Удаляем оба сообщения
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception as e:
        await message.reply(f"⚠ Ошибка при удалении: {e}")



@dp.message(F.text.lower() == "донат")
async def donate_command(message: Message):
    if message.chat.type != "private":
        return await message.reply(
            "⚠ Команда <b>донат</b> доступна только в личных сообщениях с ботом.",
            parse_mode="HTML"
        )

    user = message.from_user
    mention = f"<b>{user.first_name}</b>"

    text = (
        f"💠 Привет, {mention}!\n"
        f"Ты попал в <b>раздел доната</b>.\n\n"
        f"<b>💠 Прайсы на сакуру:</b>\n"
        f"1. <b>100 000</b> 🌸 — <b>50</b> ⭐️\n"
        f"2. <b>204 000</b> 🌸 — <b>100</b> ⭐️\n"
        f"3. <b>525 000</b> 🌸 — <b>250</b> ⭐️\n"
        f"4. <b>1 150 000</b> 🌸 — <b>500</b> ⭐️\n\n"
        f"<b>💠 Как оплатить донат?</b>\n"
        f"Очень просто — <b>отправь сумму</b> или <b>🧸подарок</b> на Telegram аккаунт ниже по кнопке.\n\n"
        f"📥 После оплаты ты получишь сакуру в соответствии с выбранным пакетом!"
    )

    # Кнопка оплатить
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url="https://t.me/ketanawin")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)





ARTICLES = [
    # РФ
    ("Статья 105 УК РФ", "Убийство"),
    ("Статья 158 УК РФ", "Кража"),
    ("Статья 159 УК РФ", "Мошенничество"),
    ("Статья 228 УК РФ", "Незаконный оборот наркотиков"),
    ("Статья 131 УК РФ", "Изнасилование"),
    ("Статья 111 УК РФ", "Причинение тяжкого вреда здоровью"),
    ("Статья 213 УК РФ", "Хулиганство"),
    ("Статья 282 УК РФ", "Возбуждение ненависти"),
    ("Статья 163 УК РФ", "Вымогательство"),
    ("Статья 264 УК РФ", "Пьяное вождение"),

    # Украина
    ("Стаття 115 КК України", "Умисне вбивство"),
    ("Стаття 185 КК України", "Крадіжка"),
    ("Стаття 190 КК України", "Шахрайство"),
    ("Стаття 307 КК України", "Збут наркотиків"),
    ("Стаття 152 КК України", "Згвалтування"),
    ("Стаття 121 КК України", "Тілесні ушкодження"),
    ("Стаття 296 КК України", "Хуліганство"),
    ("Стаття 161 КК України", "Розпалювання ворожнечі"),
    ("Стаття 189 КК України", "Вимагання"),
    ("Стаття 286 КК України", "Порушення ПДР у стані сп’яніння"),

    # РФ дополнительные
    ("Статья 134 УК РФ", "Половое сношение с несовершеннолетним"),
    ("Статья 242 УК РФ", "Незаконное распространение порнографии"),
    ("Статья 127 УК РФ", "Незаконное лишение свободы"),
    ("Статья 126 УК РФ", "Похищение человека"),
    ("Статья 160 УК РФ", "Присвоение или растрата"),
    ("Статья 201 УК РФ", "Злоупотребление полномочиями"),
    ("Статья 205 УК РФ", "Террористический акт"),
    ("Статья 206 УК РФ", "Захват заложника"),
    ("Статья 207 УК РФ", "Заведомо ложное сообщение об акте терроризма"),
    ("Статья 210 УК РФ", "Организация преступного сообщества"),

    # Украина дополнительные
    ("Стаття 125 КК України", "Умисне легке тілесне ушкодження"),
    ("Стаття 289 КК України", "Незаконне заволодіння транспортом"),
    ("Стаття 296 КК України", "Хуліганство"),
    ("Стаття 286-1 КК України", "Керування у нетверезому стані"),
    ("Стаття 358 КК України", "Підробка документів"),
    ("Стаття 345 КК України", "Погроза або насильство щодо поліцейського"),
    ("Стаття 395 КК України", "Порушення правил адміністративного нагляду"),
    ("Стаття 348 КК України", "Посягання на життя правоохоронця"),
    ("Стаття 368 КК України", "Одержання хабара"),
    ("Стаття 379 КК України", "Посягання на життя журналіста"),

    # Комичные и необычные
    ("Статья 245 УК РФ", "Жестокое обращение с животными"),
    ("Статья 256 УК РФ", "Незаконная добыча водных ресурсов"),
    ("Статья 214 УК РФ", "Вандализм"),
    ("Статья 272 УК РФ", "Неправомерный доступ к компьютеру"),
    ("Статья 273 УК РФ", "Создание вредоносных программ"),
    ("Статья 274 УК РФ", "Нарушение правил эксплуатации систем"),
    ("Статья 207.1 УК РФ", "Фейки про армию РФ"),
    ("Статья 280 УК РФ", "Публичные призывы к экстремизму"),
    ("Статья 354.1 УК РФ", "Реабилитация нацизма"),
    ("Статья 137 УК РФ", "Нарушение неприкосновенности частной жизни"),

    # Ещё +10 🇷🇺
    ("Статья 116 УК РФ", "Побои"),
    ("Статья 119 УК РФ", "Угроза убийством"),
    ("Статья 125 УК РФ", "Оставление в опасности"),
    ("Статья 141 УК РФ", "Воспрепятствование выборам"),
    ("Статья 148 УК РФ", "Оскорбление чувств верующих"),
    ("Статья 158.1 УК РФ", "Кража у близких"),
    ("Статья 162 УК РФ", "Разбой"),
    ("Статья 170 УК РФ", "Подделка документов"),
    ("Статья 180 УК РФ", "Незаконное использование бренда"),
    ("Статья 186 УК РФ", "Подделка денег")
]



@dp.message(F.text.lower() == "моя статья")
async def my_article(message: Message):
    if message.chat.type == "private":
        return await message.reply("⚠ Эта команда работает только в группах.")

    uid = message.from_user.id
    cid = message.chat.id

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute(
            "SELECT article_index, last_used FROM user_articles WHERE user_id = ? AND chat_id = ?",
            (uid, cid)
        )
        result = await row.fetchone()

        now = datetime.utcnow()

        if result:
            index, last_used_raw = result
            if last_used_raw:
                last_used = datetime.fromisoformat(last_used_raw)
                if now - last_used < timedelta(hours=24):
                    left = timedelta(hours=24) - (now - last_used)
                    hours, remainder = divmod(int(left.total_seconds()), 3600)
                    minutes = remainder // 60
                    return await message.reply(
                        f"⏳ Ты уже получил статью в этом чате.\nПовторно можно через {hours} ч {minutes} мин."
                    )
        else:
            index = random.randint(0, len(ARTICLES) - 1)
            await db.execute(
                "INSERT INTO user_articles (user_id, chat_id, article_index, last_used) VALUES (?, ?, ?, ?)",
                (uid, cid, index, now.isoformat())
            )
            await db.commit()

        # Обновим дату использования
        await db.execute(
            "UPDATE user_articles SET last_used = ? WHERE user_id = ? AND chat_id = ?",
            (now.isoformat(), uid, cid)
        )
        await db.commit()

    title, text = ARTICLES[index]
    mention = f"<a href='tg://user?id={uid}'>{message.from_user.first_name}</a>"

    await message.reply(
        f"🧾 Сегодня {mention} приговаривается к:\n\n"
        f"<b>{title}</b>\n<i>{text}</i>",
        parse_mode="HTML"
    )


@dp.message(F.text.lower().startswith("продать "))
async def sell_chips(message: Message):
    user = message.from_user
    args = message.text.strip().split()

    if len(args) != 2:
        return await message.reply("⚠ Формат: <code>продать 2</code>", parse_mode="HTML")

    try:
        count = int(args[1])
        if count <= 0:
            return await message.reply("❌ Количество фишек должно быть положительным числом.")
    except:
        return await message.reply("❌ Укажи корректное количество фишек числом.")

    price_per_chip = 4000
    total_gain = count * price_per_chip

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT chips FROM users WHERE user_id = ?", (user.id,))
        result = await row.fetchone()
        balance = result[0] if result else 0

        if balance < count:
            return await message.reply(
                f"❌ У тебя недостаточно фишек.\nДоступно: {balance}, требуется: {count}"
            )

        await db.execute("""
            UPDATE users SET chips = chips - ?, sakura = sakura + ?
            WHERE user_id = ?
        """, (count, total_gain, user.id))
        await db.commit()

    await message.reply(
        f"💱 Ты продал <b>{count}</b> фишек [♠️ Poker Chip] и получил <b>{total_gain} 🌸</b>",
        parse_mode="HTML"
    )



@dp.message(F.text.lower().startswith("хел"))
async def hel_game(message: Message):
    if "hel" in disabled_games_by_chat.get(message.chat.id, set()):
        return await message.reply("🔥 Игра 'Хел' отключена в этом чате.")

    if message.chat.type not in ("group", "supergroup"):
        return await message.reply("⚠ Игра доступна только в группах.")

    user_id = message.from_user.id
    chat_id = message.chat.id

    # 🛡 Блок повторной игры
    if chat_id in active_hel_games and user_id in active_hel_games[chat_id]:
        return await message.reply("⚠ У тебя уже начата игра. Заверши её перед новой.")

    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("⚠ Формат: <code>хел 1</code>", parse_mode="HTML")

    try:
        bet = int(parts[1])
        if bet <= 0:
            raise ValueError()
    except:
        return await message.reply("❌ Укажи корректное количество фишек.")

    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute("SELECT chips FROM users WHERE user_id = ?", (user_id,))
        res = await row.fetchone()
        balance = res[0] if res else 0

        if balance < bet:
            return await message.reply(f"💸 Недостаточно фишек. У тебя: {balance}, нужно: {bet}")

        await db.execute("UPDATE users SET chips = chips - ? WHERE user_id = ?", (bet, user_id))
        await db.commit()

    active_hel_games.setdefault(chat_id, {})[user_id] = {"bet": bet}

    mention = f"<a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="♠️", callback_data="hel:spade"),
        InlineKeyboardButton(text="♣️", callback_data="hel:club"),
        InlineKeyboardButton(text="♥️", callback_data="hel:heart"),
        InlineKeyboardButton(text="♦️", callback_data="hel:diamond")
    ]])

    await message.reply(
        f"{mention}\nВыбери масть и проверь удачу:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("hel:"))
async def hel_choice(call: CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    choice = call.data.split(":")[1]

    if chat_id not in active_hel_games or user_id not in active_hel_games[chat_id]:
        return await call.answer("⚠ Игра не найдена.", show_alert=True)

    user_data = active_hel_games[chat_id].pop(user_id, None)
    if not user_data:
        return await call.answer("⚠ Игра уже завершена.")

    bet_fish = user_data["bet"]
    base_value = bet_fish * 5000  # 1 фишка = 5000 сакур

    user_mention = f"<a href='tg://user?id={user_id}'>{call.from_user.first_name}</a>"

    suits = {
        "spade": "♠️",
        "club": "♣️",
        "heart": "♥️",
        "diamond": "♦️"
    }

    multipliers = {
        "♠️": 2,
        "♥️": 2.5,
        "♣️": 3,
        "♦️": 4
    }

    # 🎯 Взвешенный выбор масти
    drop = random.choices(
        population=["♠️", "♥️", "♣️", "♦️"],
        weights=[50, 30, 15, 5],  # чем выше вес, тем чаще выпадает
        k=1
    )[0]

    user_pick = suits.get(choice)
    win = (user_pick == drop)
    multiplier = multipliers.get(drop, 0)
    profit = int(base_value * multiplier) if win else 0

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass

    try:
        animation = await call.message.answer_animation("https://i.gifer.com/E3wf.gif")
        await asyncio.sleep(4)
        await animation.delete()
    except:
        pass

    if win:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (profit, user_id))
            await db.commit()

    # лог
    hell_game_history.setdefault(chat_id, []).append(drop)
    if len(hell_game_history[chat_id]) > 10:
        hell_game_history[chat_id] = hell_game_history[chat_id][-10:]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO hel_logs (chat_id, user_id, symbol, timestamp)
            VALUES (?, ?, ?, ?)
        """, (chat_id, user_id, drop, datetime.utcnow().isoformat()))
        await db.commit()

    result_text = (
        f"{user_mention}\n"
        f"🎴 Выпала масть: <b>{drop}</b>\n"
        f"📈 Множитель: <b>x{multiplier}</b>\n"
        f"{'🎉 Победа! Ты выиграл <b>' + str(profit) + ' 🌸</b>!' if win else '💥 Увы, ты проиграл.'}"
    )
    await call.message.answer(result_text, parse_mode="HTML")
    await call.answer()






@dp.message(F.text.lower() == ".лог")
async def hel_log(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return  # Только в группах

    chat_id = message.chat.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT symbol FROM hel_logs
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT 10
        """, (chat_id,))
        rows = await cursor.fetchall()

    if not rows:
        return await message.reply("🕳 Пока что лог пуст.")

    symbol_names = {
        "♠️": "Пики",
        "♣️": "Трефы",
        "♥️": "Червы",
        "♦️": "Бубны"
    }

    lines = [
        f"{i + 1}. {symbol_names.get(s, s)} {s}"
        for i, (s,) in enumerate(rows)
    ]

    text = "🧾 <b>Последние 10 выпадений мастей:</b>\n" + "\n".join(lines)
    await message.reply(text, parse_mode="HTML")




@dp.message(F.new_chat_members)
async def handle_new_members(message: Message):
    chat_id = message.chat.id

    for member in message.new_chat_members:
        if member.is_bot:
            continue

        inviter = message.from_user
        if inviter.id == member.id:
            continue

        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute(
                "SELECT 1 FROM invited_users WHERE chat_id = ? AND invited_id = ?",
                (chat_id, member.id)
            )
            already_invited = await row.fetchone()

            if already_invited:
                return

            await db.execute(
                "INSERT INTO invited_users (chat_id, invited_id, inviter_id) VALUES (?, ?, ?)",
                (chat_id, member.id, inviter.id)
            )
            await db.execute(
                "UPDATE users SET sakura = sakura + 3000 WHERE user_id = ?",
                (inviter.id,)
            )
            await db.commit()

        await message.answer(
            f"🎉 <a href='tg://user?id={inviter.id}'>{inviter.first_name}</a> пригласил <b>{member.first_name}</b> и получил <b>3000 🌸</b>!",
            parse_mode="HTML"
        )





@dp.message(F.text.lower().startswith("/очистить"))
async def clear_custom_id(message: Message):
    # 🔒 Только в ЛС
    if message.chat.type != "private":
        return

    # 🔐 Только для админов
    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 У тебя нет доступа к этой команде.")

    args = message.text.strip().split()
    if len(args) != 2:
        return await message.reply("⚠ Формат: /очистить ID_пользователя")

    try:
        target_id = int(args[1])
    except:
        return await message.reply("❌ Укажи корректный числовой ID.")

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли пользователь
        row = await db.execute("SELECT custom_id FROM users WHERE user_id = ?", (target_id,))
        res = await row.fetchone()

        if not res:
            return await message.reply("❌ Пользователь не найден в базе.")

        custom_id = res[0]
        if not custom_id:
            return await message.reply("ℹ️ У пользователя нет кастомного ID.")

        # Очищаем custom_id
        await db.execute("UPDATE users SET custom_id = NULL WHERE user_id = ?", (target_id,))
        await db.commit()

    await message.reply(f"✅ Кастомный ID <b>{custom_id}</b> успешно удалён у пользователя <code>{target_id}</code>.", parse_mode="HTML")




@dp.message(F.text.lower() == "правила")
async def chat_rules(message: Message):
    allowed_chat_id = -1002835369234

    if message.chat.id != allowed_chat_id:
        return  # Игнорируем в других чатах

    text = (
        "<b>📜 ПРАВИЛА ЧАТА</b>\n\n"
        "1. ▫️ Любая форма рекламы — <b>бан</b>\n"
        "2. ▫️ Продажи — <b>мут/бан</b>\n"
        "3. ▫️ Политика — <b>мут/бан</b>\n"
        "4. ▫️ Оскорбления родных — <b>мут/бан</b>\n"
    )
    await message.reply(text, parse_mode="HTML")



# Админ ID

# 📥 Команда /создать (только в ЛС и только для админов)
@dp.message(F.text.lower().startswith("/создать"))
async def create_promo(message: Message):
    if message.chat.type != "private":
        return

    if message.from_user.id not in ADMINS:
        return await message.reply("🚫 Только для администраторов.")

    args = message.text.strip().split()
    if len(args) != 4 or not args[1].startswith("#"):
        return await message.reply("⚠ Формат: /создать #промо 1000 5")

    code = args[1].lower()
    try:
        amount = int(args[2])
        count = int(args[3])
    except:
        return await message.reply("❌ Сумма и количество должны быть числами.")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                amount INTEGER,
                activations_left INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_usages (
                code TEXT,
                user_id INTEGER,
                PRIMARY KEY (code, user_id)
            )
        """)
        await db.execute(
            "INSERT OR REPLACE INTO promocodes (code, amount, activations_left) VALUES (?, ?, ?)",
            (code, amount, count)
        )
        await db.commit()

    await message.reply(f"✅ Промокод <b>{code}</b> создан: {amount} 🌸, {count} активаций.", parse_mode="HTML")



# 📥 Команда активации промо в чате: промо #код
@dp.message(F.text.lower().startswith("промо "))
async def activate_promo(message: Message):
    args = message.text.strip().split()
    if len(args) != 2 or not args[1].startswith("#"):
        return await message.reply("⚠ Формат: <code>промо #код</code>", parse_mode="HTML")

    code = args[1].lower()
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверка существования
        row = await db.execute("SELECT amount, activations_left FROM promocodes WHERE code = ?", (code,))
        promo = await row.fetchone()
        if not promo:
            return await message.reply("❌ Промокод не найден.")

        amount, left = promo
        if left <= 0:
            return await message.reply("❌ Промокод уже исчерпан.")

        # Проверка — активировал ли пользователь
        row = await db.execute("SELECT 1 FROM promo_usages WHERE code = ? AND user_id = ?", (code, user_id))
        if await row.fetchone():
            return await message.reply("⚠️ Ты уже активировал этот промокод.")

        # Выдача и учёт
        await db.execute("INSERT INTO promo_usages (code, user_id) VALUES (?, ?)", (code, user_id))
        await db.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (code,))
        await db.execute("UPDATE users SET sakura = sakura + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

    await message.reply(f"🎁 Ты активировал промокод <b>{code}</b> и получил <b>{amount} 🌸</b>!", parse_mode="HTML")




GAMES = {
    "roulette": "🎰 Рулетка",
    "hel": "🔥 Хел",
    "log": "📜 Лог",
    "go": "🎯 /го",
    "mines": "💣 Мины",
    "duel": "⚔️ Дуэль"
}
disabled_games_by_chat = {}



@dp.message(F.text.lower() == "/setgames")
async def set_games_command(message: Message):
    if message.chat.type == "private":
        return await message.reply("⚠ Команда доступна только в группах.")

    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply("🚫 Только администратор может использовать эту команду.")

    chat_id = message.chat.id
    disabled = disabled_games_by_chat.get(chat_id, set())

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if game not in disabled else '❌'} {label}",
                    callback_data=f"togglegame:{game}"
                )
            ] for game, label in GAMES.items()
        ]
    )

    await message.reply("🎮 Выберите, какие игры отключить или включить:", reply_markup=keyboard)



@dp.callback_query(F.data.startswith("togglegame:"))
async def toggle_game_handler(call: CallbackQuery):
    game_code = call.data.split(":")[1]
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    member = await bot.get_chat_member(chat_id, user_id)
    if member.status not in ("administrator", "creator"):
        return await call.answer("🚫 Только администратор может это делать.", show_alert=True)

    disabled = disabled_games_by_chat.setdefault(chat_id, set())

    if game_code in disabled:
        disabled.remove(game_code)
    else:
        disabled.add(game_code)

    save_disabled_games()  # Сохраняем в файл

    # Обновляем интерфейс
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{'✅' if g not in disabled else '❌'} {label}",
                    callback_data=f"togglegame:{g}"
                )
            ] for g, label in GAMES.items()
        ]
    )

    await call.message.edit_reply_markup(reply_markup=keyboard)
    await call.answer("✅ Настройки обновлены.")



rules_text = """
<b>📜 Правила чата Sakura</b>
<i>Обязательно к прочтению. Нарушение влечёт санкции.</i>

<b>1.</b> Любые услуги или реклама <b>только за валюту — сакура.</b>
В сообщении обязательно должно быть упомянуто, что расчёт происходит в <b>сакуре</b> — валюте игрового бота.

<b>2.</b> <b>Запрещена реклама</b> заданий/ботов/услуг, где:
— требуется передача <b>личных данных</b> (например, номера телефона);  
— есть <b>слив информации, политика, доксинг, осинт и т.д.</b>  
— упоминаются боты: глаз бога, фан стат, реф-боты с номером, сват и прочее.

<b>3.</b> <b>Оскорбления</b>, агрессия, маты, упоминание <i>родственников</i> — запрещены.  
Также запрещён <b>поиск друзей</b>.

<b>4.</b> <b>Админ</b> вправе остановить оффтоп.

<b>5.</b> Допустимые языки общения: <b>русский, украинский, английский</b>.

<b>6.</b> Если заданию более 2 часов — оно считается <b>неактивным</b>.

<b>💱 Обмен валют:</b>
Разрешён <b>только</b> между: <b>грамм ↔ сакура ↔ ирис</b>  
— 1 ириска = 4000 сакур  
— 2000 грамм = 4000 сакур  
"""

@dp.message(Command(commands=["rules", "правила"]))
async def send_rules(message: Message):
    if message.chat.id != SAKURA_RULES_CHAT_ID:
        return await message.reply("❌ Эта команда работает только в официальном чате.")

    await message.answer(rules_text, parse_mode="HTML")




# 🎯 Проверка работы: пинг
@dp.message(F.text.lower() == "пинг")
async def ping(message: Message):
    await message.reply("Понг!")

# 🚀 Запуск
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()  # ← вот тут
    await dp.start_polling(bot)
    await ensure_blacklist_table()
    await init_db()


# ▶️ Точка входа
if __name__ == "__main__":
    import asyncio

    # Сначала загружаем все данные
    load_spin_log()
    load_daily_top()
    load_disabled_games()  # ← загрузка отключённых игр

    # Потом инициализируем базу данных и запускаем бота
    asyncio.run(init_db())
    asyncio.run(main())
