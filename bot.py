import os
import asyncio
import logging
import g4f
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Загружаем переменные из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Настройка логирования (важно для сервера, чтобы видеть ошибки в консоли)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def ask_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    # Показываем статус "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Используем асинхронный вызов с перебором провайдеров
        response = await g4f.ChatCompletion.create_async(
            model=g4f.models.gemini,
            messages=[{"role": "user", "content": user_text}],
        )

        if response and len(response) > 0:
            # Если ответ слишком длинный, Телеграм его не пропустит (лимит 4096 символов)
            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000])
            else:
                await update.message.reply_text(response)
        else:
            await update.message.reply_text("Не удалось получить ответ от нейросети. Попробуй позже.")

    except Exception as e:
        logging.error(f"Ошибка в Gemini: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

if __name__ == '__main__':
    if not TOKEN:
        print("Ошибка: TOKEN не найден в переменых окружения!")
        exit(1)

    # Создаем приложение с автоматическим перезапуском при сбоях сети
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ask_gemini))
    
    print("Бот запущен на хостинге...")
    app.run_polling(drop_pending_updates=True) # drop_pending_updates игнорирует старые сообщения после включения
