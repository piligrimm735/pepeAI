import os
import telebot
import requests
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("8791536646:AAESrE6-5t3HZFUee5T6qtcwFN0neESStYw")
GEMINI_API_KEY = os.getenv("AIzaSyBELsa-RoCF3lmqR6czBtp2rM0lBwPfex0")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("BOT_TOKEN или GEMINI_API_KEY не заданы в .env файле")

# Используем стабильную модель gemini-2.0-flash-exp
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"

# Хранилище истории диалогов по chat_id
history = {}

def get_gemini_response(user_msg, chat_id):
    if chat_id not in history:
        history[chat_id] = []
    # Добавляем сообщение пользователя
    history[chat_id].append({"role": "user", "parts": [{"text": user_msg}]})
    # Ограничиваем историю 10 сообщениями
    if len(history[chat_id]) > 10:
        history[chat_id] = history[chat_id][-10:]

    payload = {"contents": history[chat_id]}
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            answer = data["candidates"][0]["content"]["parts"][0]["text"]
            # Сохраняем ответ модели
            history[chat_id].append({"role": "model", "parts": [{"text": answer}]})
            return answer
        else:
            return f"Ошибка Gemini: {resp.status_code} - {resp.text}"
    except Exception as e:
        return f"Ошибка соединения: {str(e)}"

# Создаём бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот на Google Gemini. Просто напиши мне.")

@bot.message_handler(commands=['clear'])
def clear_history(message):
    chat_id = message.chat.id
    if chat_id in history:
        del history[chat_id]
    bot.reply_to(message, "История диалога очищена.")

@bot.message_handler(func=lambda message: True)
def reply_to_message(message):
    chat_id = message.chat.id
    user_text = message.text
    bot.send_chat_action(chat_id, 'typing')
    answer = get_gemini_response(user_text, chat_id)
    bot.send_message(chat_id, answer)

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()