# -*- coding: utf-8 -*-
import telebot
import sqlite3
import requests
import io
import os
import time
from datetime import datetime

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))

# Бесплатные API (ваши ключи)
HF_TOKEN = os.environ.get("HF_TOKEN", "")  # huggingface.co
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")  # openrouter.ai

# ===== БАЗА ДАННЫХ (только статистика) =====
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        total_requests INTEGER DEFAULT 0,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# ===== БОТ =====
bot = telebot.TeleBot(BOT_TOKEN)

# ===== БЕСПЛАТНЫЕ НЕЙРОСЕТИ =====
def ai_text(prompt):
    """Бесплатная текстовая нейросеть через OpenRouter"""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1000
            },
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"Text error: {e}")
        return "⚠️ Нейросеть временно недоступна. Попробуйте позже."

def ai_image(prompt):
    """Бесплатная генерация картинок через Hugging Face"""
    try:
        API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=60)
        
        if response.status_code == 200:
            return response.content
        else:
            # Запасная модель
            API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=45)
            return response.content
    except Exception as e:
        print(f"Image error: {e}")
        return None

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def update_stats(user_id, username=None):
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        cursor.execute('UPDATE users SET total_requests = total_requests + 1 WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('INSERT INTO users (user_id, username, total_requests) VALUES (?, ?, 1)', 
                      (user_id, username))
    conn.commit()

# ===== КОМАНДЫ БОТА =====
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        f"🤖 *Бесплатный AI Бот*\n\n"
        f"✨ Нейросеть полностью бесплатна!\n\n"
        f"📝 Команды:\n"
        f"/img описание - создать картинку\n"
        f"/ask вопрос - задать вопрос\n"
        f"/stats - ваша статистика\n\n"
        f"💬 Просто отправь текст для ответа!",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['stats'])
def stats(message):
    user_id = message.from_user.id
    cursor.execute('SELECT total_requests FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    total = result[0] if result else 0
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(total_requests) FROM users')
    total_all = cursor.fetchone()[0] or 0
    
    bot.reply_to(message, 
        f"📊 *Статистика*\n\n"
        f"👤 Ваши запросы: {total}\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💬 Всего запросов: {total_all}",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor.execute('SELECT COUNT(*), SUM(total_requests) FROM users')
    users, total = cursor.fetchone()
    
    cursor.execute('SELECT user_id, username, total_requests FROM users ORDER BY total_requests DESC LIMIT 10')
    top = cursor.fetchall()
    
    text = f"👑 *Админ панель*\n\n👥 Пользователей: {users}\n💬 Запросов: {total or 0}\n\n*Топ-10:*\n"
    for i, (uid, name, req) in enumerate(top, 1):
        text += f"{i}. @{name}: {req}\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['img'])
def generate_image_cmd(message):
    prompt = message.text.replace('/img', '').strip()
    if not prompt:
        bot.reply_to(message, "❌ Напишите описание после /img\nПример: /img кот в космосе")
        return
    
    msg = bot.reply_to(message, "🎨 Генерирую изображение...")
    
    image_data = ai_image(prompt)
    
    if image_data:
        update_stats(message.from_user.id, message.from_user.username)
        bot.send_photo(message.chat.id, image_data, caption=f"🎨 {prompt[:200]}")
        bot.delete_message(message.chat.id, msg.message_id)
    else:
        bot.edit_message_text("❌ Ошибка генерации. Попробуйте позже.", 
                            message.chat.id, msg.message_id)

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    question = message.text.replace('/ask', '').strip()
    if not question:
        bot.reply_to(message, "❌ Напишите вопрос после /ask\nПример: /ask как дела?")
        return
    
    msg = bot.reply_to(message, "🤔 Думаю...")
    
    response = ai_text(question)
    update_stats(message.from_user.id, message.from_user.username)
    
    bot.edit_message_text(f"❓ *Вопрос:* {question}\n\n💡 *Ответ:* {response}", 
                          message.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'):
        return
    
    msg = bot.reply_to(message, "💭 Печатаю...")
    
    response = ai_text(message.text)
    update_stats(message.from_user.id, message.from_user.username)
    
    # Разбиваем длинные сообщения
    if len(response) > 4096:
        for i in range(0, len(response), 4096):
            bot.send_message(message.chat.id, response[i:i+4096])
        bot.delete_message(message.chat.id, msg.message_id)
    else:
        bot.edit_message_text(response, message.chat.id, msg.message_id)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Бесплатный AI бот запущен!")
    print("📝 Текст: Mistral 7B (OpenRouter)")
    print("🎨 Изображения: FLUX/Stable Diffusion (Hugging Face)")
    print("💰 Система покупок отключена - всё бесплатно!")
    
    bot.remove_webhook()
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
