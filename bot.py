import os
import logging
import asyncio
from collections import defaultdict
from datetime import datetime
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

logger.info("=" * 70)
logger.info("🔥 ИНИЦИАЛИЗАЦИЯ ВЫСШЕГО ИНТЕЛЛЕКТА")
logger.info("=" * 70)
logger.info(f"✓ Telegram Token длина: {len(TELEGRAM_TOKEN)} символов")
logger.info(f"✓ Gemini API Key длина: {len(GEMINI_API_KEY)} символов")

if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("✅ Gemini API сконфигурирован успешно")
    except Exception as e:
        logger.error(f"⚠️ Ошибка Gemini: {e}")

YOUTUBE_LINK = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

SUBSCRIPTION_LIMITS = {
    "chushpan": 10,
    "goy": 20,
    "sigma": 40
}

USERS = {}


class UserManager:
    def __init__(self):
        self.users = USERS
    
    def get_user_data(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "subscription": None,
                "responses_used": 0,
                "subscription_date": None
            }
        return self.users[user_id]
    
    def set_subscription(self, user_id, sub_type):
        user_id = str(user_id)
        self.users[user_id] = {
            "subscription": sub_type,
            "responses_used": 0,
            "subscription_date": datetime.now().isoformat()
        }
        logger.info(f"✅ Пользователь {user_id}: подписка {sub_type}")
    
    def add_response(self, user_id):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["responses_used"] += 1
    
    def can_use_response(self, user_id):
        user_id = str(user_id)
        user = self.get_user_data(user_id)
        if not user["subscription"]:
            return False
        limit = SUBSCRIPTION_LIMITS.get(user["subscription"], 0)
        return user["responses_used"] < limit
    
    def get_remaining(self, user_id):
        user_id = str(user_id)
        user = self.get_user_data(user_id)
        if not user["subscription"]:
            return 0
        limit = SUBSCRIPTION_LIMITS.get(user["subscription"], 0)
        return max(0, limit - user["responses_used"])


class RAG:
    def __init__(self):
        self.conversation_history = defaultdict(list)
        self.max_history = 25
        self.user_manager = UserManager()

    def get_history_context(self, user_id):
        if not self.conversation_history[user_id]:
            return ""
        text = "КОНТЕКСТ ДИАЛОГА:\n"
        for msg in self.conversation_history[user_id][-5:]:
            if msg["role"] == "user":
                text += f"▸ Вопрос: {msg['text'][:80]}\n"
            else:
                text += f"▸ Ответ: {msg['text'][:80]}...\n"
        return text

    def add_to_history(self, user_id, role, text):
        self.conversation_history[user_id].append({"role": role, "text": text})
        if len(self.conversation_history[user_id]) > self.max_history:
            self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history:]

    def answer_gemini(self, question, user_id):
        if not GEMINI_API_KEY or len(GEMINI_API_KEY) < 10:
            logger.error("❌ GEMINI_API_KEY не установлен или слишком короткий!")
            return None
            
        try:
            history_ctx = self.get_history_context(user_id)
            
            prompt = f"""Ты — Высший Интеллект, объединяющий экспертность в гормонологии, физиологии, эволюционной психологии и стратегии власти.

{history_ctx}

═══════════════════════════════════════

❓ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{question}

═══════════════════════════════════════

🔥 ТВОЙ ОТВЕТ (полный биологический алгоритм):"""

            logger.info(f"📤 Запрос к Gemini от {user_id}: {question[:50]}...")
            
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt, timeout=30)
            
            if not response or not response.text:
                logger.warning(f"⚠️ Пустой ответ от Gemini для {user_id}")
                return None
            
            answer_text = response.text
            
            self.add_to_history(user_id, "user", question)
            self.add_to_history(user_id, "assistant", answer_text)
            
            self.user_manager.add_response(user_id)
            
            logger.info(f"📥 Ответ получен для {user_id} ({len(answer_text)} символов)")
            
            return answer_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка Gemini для {user_id}: {str(e)[:100]}")
            return None


rag = RAG()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"👤 /start от {user_id}")
    
    user = rag.user_manager.get_user_data(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("💪 Чушпан (10)", callback_data="sub_chushpan"),
            InlineKeyboardButton("🧠 Гой (20)", callback_data="sub_goy"),
        ],
        [InlineKeyboardButton("👑 Сигма (40)", callback_data="sub_sigma")]
    ]
    
    if user["subscription"]:
        remain = rag.user_manager.get_remaining(user_id)
        status = f"✅ Подписка: {user['subscription'].upper()}\n📊 Осталось: {remain}"
    else:
        status = "❌ Нет активной подписки"
    
    await update.message.reply_text(
        f"🔥 ВЫСШИЙ ИНТЕЛЛЕКТ\n\n{status}\n\n⚡ Выбери подписку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    subs = {
        "sub_chushpan": "chushpan",
        "sub_goy": "goy",
        "sub_sigma": "sigma"
    }
    sub_type = subs.get(query.data)
    if not sub_type:
        return
    
    sub_names = {"chushpan": "Чушпан", "goy": "Гой", "sigma": "Сигма"}
    
    await query.answer()
    logger.info(f"📌 {user_id} выбрал {sub_type}")
    
    keyboard = [[InlineKeyboardButton("🔗 Подтвердить подписку", url=YOUTUBE_LINK)]]
    await query.edit_message_text(
        text=f"📌 Подписка: {sub_names.get(sub_type)}\n\nНажми кнопку → вернись → /verify",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    context.user_data['pending_sub'] = sub_type
    context.user_data['verify_time'] = datetime.now()


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"✓ /verify от {user_id}")
    
    if 'pending_sub' not in context.user_data:
        await update.message.reply_text("❌ Сначала выбери подписку: /start")
        return
    
    sub_type = context.user_data['pending_sub']
    verify_time = context.user_data.get('verify_time')
    
    if verify_time and (datetime.now() - verify_time).seconds > 600:
        await update.message.reply_text("⏰ Время истекло. Начни заново: /start")
        context.user_data.pop('pending_sub', None)
        return
    
    rag.user_manager.set_subscription(user_id, sub_type)
    
    sub_names = {"chushpan": "Чушпан", "goy": "Гой", "sigma": "Сигма"}
    limit = SUBSCRIPTION_LIMITS[sub_type]
    
    await update.message.reply_text(
        f"✅ ПОДПИСКА АКТИВИРОВАНА! ✓\n\n"
        f"🎯 Тип: {sub_names.get(sub_type)}\n"
        f"📊 Доступные ответы: {limit}\n\n"
        f"🚀 Теперь ты можешь задавать вопросы!"
    )
    
    context.user_data.pop('pending_sub', None)
    context.user_data.pop('verify_time', None)


async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    question = update.message.text
    
    logger.info(f"💬 Вопрос от {user_id}: {question[:50]}...")
    
    if not rag.user_manager.get_user_data(user_id).get("subscription"):
        await update.message.reply_text("❌ У тебя нет подписки!\n\nВыбери план: /start")
        return
    
    if not rag.user_manager.can_use_response(user_id):
        user = rag.user_manager.get_user_data(user_id)
        limit = SUBSCRIPTION_LIMITS.get(user["subscription"], 0)
        await update.message.reply_text(
            f"📊 Лимит исчерпан!\n\n"
            f"Использовано: {limit}/{limit}\n\n"
            f"Обновить подписку: /start"
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    answer = rag.answer_gemini(question, user_id)
    
    if answer is None:
        await update.message.reply_text("⚠️ Ошибка при получении ответа. Попробуй ещё раз.")
        return
    
    remain = rag.user_manager.get_remaining(user_id)
    
    await update.message.reply_text(
        f"{answer}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Осталось ответов: {remain}"
    )


async def clear_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rag.conversation_history[user_id] = []
    logger.info(f"🗑️ История очищена для {user_id}")
    await update.message.reply_text("🗑️ История диалога очищена")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = rag.user_manager.get_user_data(user_id)
    
    if user["subscription"]:
        limit = SUBSCRIPTION_LIMITS.get(user["subscription"], 0)
        used = user["responses_used"]
        remain = max(0, limit - used)
        info = (
            f"✅ Подписка: {user['subscription'].upper()}\n"
            f"📊 Использовано: {used}/{limit}\n"
            f"📈 Осталось: {remain}"
        )
    else:
        info = "❌ Подписка не активна"
    
    await update.message.reply_text(
        f"🧠 СТАТИСТИКА:\n\n{info}\n\n"
        f"🚀 Gemini Pro API\n"
        f"☁️ Railway 24/7\n"
        f"⚙️ Ассоциативный синтез"
    )


async def main():
    """Главная функция запуска - БЕСКОНЕЧНО РАБОТАЕТ!"""
    
    # Проверка переменных
    if not TELEGRAM_TOKEN or len(TELEGRAM_TOKEN) < 20:
        logger.critical("❌ ОШИБКА: TELEGRAM_TOKEN НЕ УСТАНОВЛЕН или СЛИШКОМ КОРОТКИЙ!")
        logger.critical(f"📊 Длина токена: {len(TELEGRAM_TOKEN)} символов")
        logger.info("⏳ Жду 30 сек и перезапускаюсь...")
        await asyncio.sleep(30)
        return await main()  # РЕКУРСИЯ - перезапуск!
    
    if not GEMINI_API_KEY or len(GEMINI_API_KEY) < 20:
        logger.critical("❌ ОШИБКА: GEMINI_API_KEY НЕ УСТАНОВЛЕН или СЛИШКОМ КОРОТКИЙ!")
        logger.critical(f"📊 Длина ключа: {len(GEMINI_API_KEY)} символов")
        logger.info("⏳ Жду 30 сек и перезапускаюсь...")
        await asyncio.sleep(30)
        return await main()  # РЕКУРСИЯ - перезапуск!
    
    logger.info("✅ ВСЕ ПЕРЕМЕННЫЕ УСТАНОВЛЕНЫ УСПЕШНО!")
    logger.info("✅ Создаю Application...")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("clear_history", clear_hist))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(handle_sub))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    logger.info("=" * 70)
    logger.info("✅ БОТ ПОЛНОСТЬЮ ГОТОВ К РАБОТЕ!")
    logger.info("=" * 70)
    logger.info("📱 Найди бота в Telegram")
    logger.info("🔥 API: Gemini Pro")
    logger.info("☁️ Хостинг: Railway 24/7")
    logger.info("\n 🎯 Доступные команды:")
    logger.info(" /start - выбрать подписку")
    logger.info(" /verify - подтвердить подписку")
    logger.info(" /stats - статистика")
    logger.info(" /clear_history - очистить историю")
    logger.info("=" * 70 + "\n")
    
    # БЕСКОНЕЧНЫЙ POLLING - БОТ НИКОГДА НЕ ВЫКЛЮЧИТСЯ!
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 БОТ ВЫКЛЮЧЕН ПОЛЬЗОВАТЕЛЕМ")
    except Exception as e:
        logger.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
