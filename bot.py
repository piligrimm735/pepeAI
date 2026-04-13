# -*- coding: utf-8 -*-
import telebot
import sqlite3
import requests
import json
import io
import os
from datetime import datetime
import time

# ===== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))


# ===== БАЗА ДАННЫХ =====
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        whitelist INTEGER DEFAULT 0,
        total_used INTEGER DEFAULT 0
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stars INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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
                "Authorization": "Bearer sk-or-v1-бесплатный_ключ_openrouter",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']
    except:
        return "⚠️ Ошибка нейросети. Попробуйте позже."

def ai_image(prompt):
    """Бесплатная генерация картинок через Hugging Face"""
    try:
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=45)
        
        if response.status_code == 200:
            return response.content
        else:
            # Запасная бесплатная модель
            API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
            response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
            return response.content
    except:
        return None

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_user(user_id, username=None):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user and username:
        cursor.execute('INSERT INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
        return (user_id, username, 0, 0, 0)
    return user

def has_access(user_id):
    user = get_user(user_id)
    return user[3] == 1 or user[2] > 0  # whitelist или есть баланс

def use_credit(user_id):
    user = get_user(user_id)
    if user[3] == 1:  # whitelist - безлимит
        cursor.execute('UPDATE users SET total_used = total_used + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        return True
    elif user[2] > 0:  # есть баланс
        cursor.execute('UPDATE users SET balance = balance - 1, total_used = total_used + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        return True
    return False

# ===== КОМАНДЫ БОТА =====
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id, message.from_user.username)
    bot.reply_to(message, 
        f"🤖 *AI Бот*\n\n"
        f"💰 Баланс: {user[2]} запросов\n"
        f"🔓 Whitelist: {'✅ Да' if user[3] else '❌ Нет'}\n\n"
        f"📝 Команды:\n"
        f"/buy - купить запросы\n"
        f"/img описание - создать картинку\n"
        f"/ask вопрос - задать вопрос\n"
        f"/balance - проверить баланс\n\n"
        f"Просто отправь текст для ответа нейросети!",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['balance'])
def balance(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"💰 Ваш баланс: *{user[2]}* запросов\n🔓 Whitelist: {'✅' if user[3] else '❌'}", parse_mode='Markdown')

@bot.message_handler(commands=['buy'])
def buy(message):
    prices = [
        telebot.types.LabeledPrice("10 запросов к AI", 10),
        telebot.types.LabeledPrice("50 запросов к AI", 50),
        telebot.types.LabeledPrice("100 запросов к AI", 100)
    ]
    
    bot.send_invoice(
        chat_id=message.chat.id,
        title="🎯 AI Запросы",
        description="Покупка запросов к нейросети",
        invoice_payload="ai_requests_purchase",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="buy_ai_requests"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    user_id = message.from_user.id
    amount = message.successful_payment.total_amount
    
    requests_map = {10: 10, 50: 50, 100: 100}
    requests_to_add = requests_map.get(amount, amount)
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (requests_to_add, user_id))
    cursor.execute('INSERT INTO payments (user_id, stars) VALUES (?, ?)', (user_id, amount))
    conn.commit()
    
    bot.reply_to(message, f"✅ Оплата успешна! Добавлено {requests_to_add} запросов!")

@bot.message_handler(commands=['whitelist'])
def whitelist(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Использование: /whitelist @username")
        return
    
    username = args[1].replace('@', '')
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute('UPDATE users SET whitelist = 1 WHERE user_id = ?', (user[0],))
        conn.commit()
        bot.reply_to(message, f"✅ @{username} добавлен в whitelist (безлимит)")
    else:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден")

@bot.message_handler(commands=['unwhitelist'])
def unwhitelist(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Использование: /unwhitelist @username")
        return
    
    username = args[1].replace('@', '')
    cursor.execute('UPDATE users SET whitelist = 0 WHERE username = ?', (username,))
    conn.commit()
    bot.reply_to(message, f"✅ @{username} удален из whitelist")

@bot.message_handler(commands=['add'])
def add_credits(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "❌ Использование: /add @username 100")
        return
    
    username = args[1].replace('@', '')
    amount = int(args[2])
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE username = ?', (amount, username))
    conn.commit()
    bot.reply_to(message, f"✅ Добавлено {amount} запросов для @{username}")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor.execute('SELECT COUNT(*), SUM(balance), SUM(total_used) FROM users')
    total_users, total_balance, total_used = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE whitelist = 1')
    whitelist_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(stars) FROM payments')
    total_stars = cursor.fetchone()[0] or 0
    
    bot.reply_to(message, 
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"⭐ Whitelist: {whitelist_count}\n"
        f"💰 Баланс всего: {total_balance or 0}\n"
        f"📝 Использовано: {total_used or 0}\n"
        f"💎 Заработано звезд: {total_stars}",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['img'])
def generate_image_cmd(message):
    user_id = message.from_user.id
    
    if not has_access(user_id):
        bot.reply_to(message, "❌ Недостаточно запросов. Купите через /buy")
        return
    
    prompt = message.text.replace('/img', '').strip()
    if not prompt:
        bot.reply_to(message, "❌ Напишите описание после /img")
        return
    
    msg = bot.reply_to(message, "🎨 Генерирую изображение...")
    
    image_data = ai_image(prompt)
    
    if image_data:
        use_credit(user_id)
        bot.send_photo(message.chat.id, image_data, caption=f"🎨 {prompt[:100]}")
    else:
        bot.reply_to(message, "❌ Ошибка генерации")
    
    bot.delete_message(message.chat.id, msg.message_id)

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    user_id = message.from_user.id
    
    if not has_access(user_id):
        bot.reply_to(message, "❌ Недостаточно запросов")
        return
    
    question = message.text.replace('/ask', '').strip()
    if not question:
        bot.reply_to(message, "❌ Напишите вопрос после /ask")
        return
    
    msg = bot.reply_to(message, "🤔 Думаю...")
    
    response = ai_text(question)
    use_credit(user_id)
    
    bot.edit_message_text(f"❓ *Вопрос:* {question}\n\n💡 *Ответ:* {response}", 
                          message.chat.id, msg.message_id, parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    
    if not has_access(user_id):
        bot.reply_to(message, "❌ Нет запросов. /buy для покупки")
        return
    
    msg = bot.reply_to(message, "💭 Печатаю...")
    
    response = ai_text(message.text)
    use_credit(user_id)
    
    bot.edit_message_text(response, message.chat.id, msg.message_id)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("🚀 Бот запущен с бесплатными нейросетями!")
    print("📝 Текст: Mistral 7B (OpenRouter)")
    print("🎨 Изображения: Stable Diffusion (Hugging Face)")
    
    # Удаляем вебхук и запускаем поллинг
    bot.remove_webhook()
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
