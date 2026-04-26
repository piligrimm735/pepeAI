import g4f
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Сюда вставляешь токен от @BotFather
TOKEN = "BOT_TOKEN"

async def ask_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Отправляем в чат статус "печатает...", чтобы пользователь не скучал
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.gemini,
            messages=[{"role": "user", "content": user_text}],
            stream=False # Получаем ответ целиком
        )
        
        if response:
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("Нейросеть прислала пустой ответ. Попробуй еще раз.")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text("Сейчас Gemini недоступна, попробуй позже.")

if __name__ == '__main__':
    # Создаем приложение
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Регистрируем обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ask_gemini))
    
    print("Бот запущен...")
    app.run_polling()
