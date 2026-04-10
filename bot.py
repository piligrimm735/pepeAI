#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import requests
import json
import time
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== ИМПОРТ КОНФИГА ==========
try:
    from config import TELEGRAM_TOKEN, DEFAULT_MODEL
except ImportError:
    print("❌ Ошибка: Файл config.py не найден!")
    print("📝 Создай config.py на основе config.example.py и вставь токен бота")
    sys.exit(1)

# ========== НАСТРОЙКИ ==========
MODEL = DEFAULT_MODEL

# ========== ЛОГИ ==========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КЭШ СЕССИЙ ==========
vqd_cache = {"token": None, "expires": 0}

def get_vqd_token(session):
    """Получает или обновляет VQD токен для DuckDuckGo AI"""
    global vqd_cache
    
    if vqd_cache["token"] and time.time() < vqd_cache["expires"]:
        return vqd_cache["token"]
    
    url = "https://duckduckgo.com/duckchat/v1/status"
    headers = {
        "x-vqd-accept": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    }
    
    try:
        resp = session.get(url, headers=headers, timeout=10)
        token = resp.headers.get("x-vqd-4", "")
        
        if token:
            vqd_cache["token"] = token
            vqd_cache["expires"] = time.time() + 3500
            logger.info(f"✅ Новый VQD токен получен")
            return token
        else:
            logger.error("❌ VQD токен не найден")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения VQD токена: {e}")
        return None

def ask_duckduckgo(message, session):
    """Отправляет запрос к DuckDuckGo AI Chat"""
    
    vqd = get_vqd_token(session)
    if not vqd:
        return "🚫 Не удалось подключиться к DuckDuckGo AI. Попробуй позже."
    
    url = "https://duckduckgo.com/duckchat/v1/chat"
    headers = {
        "x-vqd-4": vqd,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/event-stream",
        "Origin": "https://duckduckgo.com",
        "Referer": "https://duckduckgo.com/"
    }
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}]
    }
    
    try:
        resp = session.post(url, headers=headers, json=payload, stream=True, timeout=45)
        
        if resp.status_code != 200:
            logger.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return f"⚠️ Ошибка сервера ({resp.status_code})"
        
        full_response = ""
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("message"):
                        full_response += data["message"]
                except json.JSONDecodeError:
                    continue
        
        full_response = full_response.strip()
        
        if not full_response:
            return "🤖 Нейросеть промолчала. Попробуй переформулировать вопрос."
        
        return full_response
        
    except requests.exceptions.Timeout:
        return "⏰ DuckDuckGo AI долго думает. Попробуй ещё раз."
    except Exception as e:
        logger.error(f"Ошибка при запросе: {e}")
        return f"💥 Ошибка: {str(e)[:100]}"

# ========== ОБРАБОТЧИКИ TELEGRAM ==========

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🦆 Бот с DuckDuckGo AI\n"
        f"🧠 Модель: {MODEL}\n"
        f"🔒 Без API ключей\n"
        f"🌍 Работает из Нидерландов\n\n"
        f"Просто напиши вопрос — нейросеть ответит!\n"
        f"/model — сменить модель\n"
        f"/about — о боте"
    )

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models = """
📋 *Доступные модели:*

1️⃣ `gpt-3.5-turbo` — OpenAI (быстрая)
2️⃣ `claude-3-haiku` — Anthropic (умная)
3️⃣ `llama-3-70b` — Meta (мощная)
4️⃣ `mixtral-8x7b` — Mistral (сбалансированная)

Чтобы сменить, напиши: `model:НАЗВАНИЕ`
Пример: `model:claude-3-haiku`
"""
    await update.message.reply_text(models, parse_mode="Markdown")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 Бот работает через публичный API DuckDuckGo AI Chat\n"
        "💰 Полностью бесплатно, без регистрации\n"
        "🇳🇱 Хостинг: сервер в Нидерландах\n"
        "📦 Репозиторий: github.com/yourname/duckduckgo-telegram-bot\n"
        f"⚙️ Текущая модель: {MODEL}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Смена модели
    if user_text.lower().startswith("model:"):
        global MODEL
        new_model = user_text[6:].strip()
        valid_models = ["gpt-3.5-turbo", "claude-3-haiku", "llama-3-70b", "mixtral-8x7b"]
        
        if new_model in valid_models:
            MODEL = new_model
            await update.message.reply_text(f"✅ Модель изменена на: {MODEL}")
        else:
            await update.message.reply_text(
                f"❌ Неизвестная модель. Доступны: {', '.join(valid_models)}"
            )
        return
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    session = requests.Session()
    logger.info(f"📨 Пользователь {user_id}: {user_text[:50]}...")
    
    response = ask_duckduckgo(user_text, session)
    
    logger.info(f"📤 Ответ для {user_id}: {response[:50]}...")
    
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
            time.sleep(0.5)
    else:
        await update.message.reply_text(response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")
    if update:
        await update.message.reply_text("❌ Произошла ошибка. Попробуй позже.")

def main():
    print(f"🚀 Запуск бота...")
    print(f"🧠 Модель: {MODEL}")
    print(f"🇳🇱 Сервер: Нидерланды")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
