#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import requests
import json
import time
import sys
import os
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env!")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ПРОВАЙДЕР 1: Pollinations.ai (точно работает) ==========
def ask_pollinations(message):
    try:
        encoded_msg = requests.utils.quote(message)
        url = f"https://text.pollinations.ai/{encoded_msg}"
        
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        
        if resp.status_code == 200 and resp.text.strip():
            return resp.text.strip()
        return None
    except Exception as e:
        logger.error(f"Pollinations error: {e}")
        return None

# ========== ПРОВАЙДЕР 2: AI-Studio (публичный) ==========
def ask_aistudio(message):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateMessage"
        # Пробуем через прокси если нужно
        return None
    except:
        return None

# ========== ПРОВАЙДЕР 3: Copilot (через прокси) ==========
def ask_copilot(message):
    try:
        # Публичное зеркало Copilot
        url = "https://copilot-proxy.githubusercontent.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        payload = {
            "messages": [{"role": "user", "content": message}],
            "model": "gpt-4"
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        return None
    except:
        return None

# ========== ПРОВАЙДЕР 4: ПРОСТОЙ ЧАТ-БОТ (всегда работает) ==========
def ask_simple_chat(message):
    """Локальные правила если все API недоступны"""
    message_lower = message.lower()
    
    # Приветствия
    if any(word in message_lower for word in ["привет", "здравствуй", "хай", "hello", "hi"]):
        return random.choice([
            "Привет! Я простой чат-бот. К сожалению, все AI провайдеры сейчас недоступны с этого сервера, но я могу поддержать базовый диалог!",
            "Здравствуй! Нейросети временно заблокированы на этом IP, но я здесь и слушаю тебя!",
            "Приветствую! Похоже DuckDuckGo и Hugging Face заблокировали этот сервер. Попробуй использовать VPN или напиши позже."
        ])
    
    # Как дела
    if "как дела" in message_lower or "как ты" in message_lower:
        return random.choice([
            "У меня всё отлично! Жду когда админ настроит нормальный прокси для AI 😅",
            "Работаю в режиме заглушки. Нейросети недоступны, но я жив!",
            "Нормально, только вот API блокируют этот сервер. Может попробуешь другой хостинг?"
        ])
    
    # Кто ты
    if "кто ты" in message_lower or "что ты" in message_lower:
        return "Я AI-бот который должен был работать через публичные API, но сервер в Нидерландах заблокирован провайдерами. Нужен прокси или VPN!"
    
    # Помощь
    if "помог" in message_lower or "help" in message_lower:
        return "Чем могу помочь? Хотя без нейросетей я ограничен. Могу посоветовать включить VPN на сервере или использовать другой хостинг."
    
    # Пока
    if any(word in message_lower for word in ["пока", "до свидания", "bye"]):
        return random.choice(["Пока! Заходи ещё!", "До встречи!", "Удачи!"])

    # Погода
    if "погода" in message_lower:
        return "Я бы посмотрел погоду, но без API это сложно. Попробуй weather.com 😊"
    
    # Время
    if "врем" in message_lower or "час" in message_lower:
        from datetime import datetime
        return f"Сейчас {datetime.now().strftime('%H:%M:%S')} по времени сервера."
    
    # По умолчанию
    return random.choice([
        f"Ты написал: '{message[:50]}...'\n\nИзвини, но AI провайдеры недоступны с этого сервера. Попробуй позже или используй VPN.",
        "Я бы с радостью ответил используя нейросеть, но все публичные API заблокированы для этого IP адреса 😔",
        "Эх, DuckDuckGo AI, BlackBox и Hugging Face недоступны. Нужно менять хостинг или настраивать прокси.",
        "Сейчас я работаю в ограниченном режиме. Нейросети недоступны. Попробуй написать позже!"
    ])

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def get_ai_response(message):
    # Пробуем все провайдеры по очереди
    
    # 1. Pollinations.ai
    logger.info("🌸 Пробую Pollinations.ai...")
    resp = ask_pollinations(message)
    if resp and len(resp) > 20:
        return resp
    
    # 2. Copilot
    logger.info("🤖 Пробую Copilot...")
    resp = ask_copilot(message)
    if resp and len(resp) > 20:
        return resp
    
    # 3. Заглушка
    logger.info("📝 Использую локальную заглушку...")
    return ask_simple_chat(message)

# ========== TELEGRAM ОБРАБОТЧИКИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Мульти-AI Бот\n"
        "🔒 Без API ключей\n"
        "🌸 Pollinations.ai + Copilot\n\n"
        "Просто напиши что-нибудь!\n"
        "/status — проверить статус провайдеров"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = "📊 Статус провайдеров:\n\n"
    
    # Проверяем Pollinations
    try:
        test = ask_pollinations("test")
        status_msg += "✅ Pollinations.ai: работает\n" if test else "❌ Pollinations.ai: недоступен\n"
    except:
        status_msg += "❌ Pollinations.ai: ошибка\n"
    
    # Проверяем Copilot
    try:
        test = ask_copilot("test")
        status_msg += "✅ Copilot: работает\n" if test else "❌ Copilot: недоступен\n"
    except:
        status_msg += "❌ Copilot: ошибка\n"
    
    status_msg += "\n💡 Если всё красное — нужен VPN на сервере!"
    
    await update.message.reply_text(status_msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    logger.info(f"📨 [{user_id}] {user_text[:50]}...")
    
    response = get_ai_response(user_text)
    
    logger.info(f"📤 Ответ: {len(response)} символов")
    
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
            time.sleep(0.3)
    else:
        await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print("🚀 Бот запущен")
    print("📡 Провайдеры: Pollinations.ai + Copilot + Локальная заглушка")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
