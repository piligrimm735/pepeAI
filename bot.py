#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import requests
import json
import time
import sys
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# ========== ЗАГРУЗКА .env ==========
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL = os.getenv("MODEL", "gpt-3.5-turbo")

# Проверка токена
if not BOT_TOKEN or BOT_TOKEN == "вставь_свой_токен_сюда":
    print("=" * 60)
    print("❌ ОШИБКА: Токен не найден в .env файле!")
    print("=" * 60)
    print("📝 Создай файл .env и вставь токен:")
    print()
    print("BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    print("MODEL=gpt-3.5-turbo")
    print()
    print("=" * 60)
    sys.exit(1)

# ========== ЛОГИ ==========
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== КЭШ VQD ТОКЕНА ==========
vqd_cache = {"token": None, "expires": 0}

def get_vqd_token(session):
    """Получает VQD токен для DuckDuckGo AI"""
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
            logger.info("✅ VQD токен получен")
            return token
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка VQD: {e}")
        return None

def ask_duckduckgo(message, session):
    """Запрос к DuckDuckGo AI"""
    vqd = get_vqd_token(session)
    if not vqd:
        return "🚫 DuckDuckGo AI недоступен"
    
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
            return f"⚠️ Ошибка {resp.status_code}"
        
        full_response = ""
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("message"):
                        full_response += data["message"]
                except:
                    continue
        
        return full_response.strip() or "🤖 Нет ответа"
        
    except Exception as e:
        return f"💥 Ошибка: {str(e)[:100]}"

# ========== ОБРАБОТЧИКИ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🦆 Бот с DuckDuckGo AI\n"
        f"🧠 Модель: {MODEL}\n"
        f"🔒 Без API ключей\n\n"
        f"Просто напиши вопрос!\n"
        f"/model — сменить модель"
    )

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models = """
📋 *Модели:*
• `gpt-3.5-turbo` — OpenAI
• `claude-3-haiku` — Anthropic  
• `llama-3-70b` — Meta
• `mixtral-8x7b` — Mistral

Смена: `model:название`
"""
    await update.message.reply_text(models, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # Смена модели
    if user_text.lower().startswith("model:"):
        global MODEL
        new_model = user_text[6:].strip()
        valid = ["gpt-3.5-turbo", "claude-3-haiku", "llama-3-70b", "mixtral-8x7b"]
        
        if new_model in valid:
            MODEL = new_model
            await update.message.reply_text(f"✅ Модель: {MODEL}")
        else:
            await update.message.reply_text(f"❌ Доступны: {', '.join(valid)}")
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    session = requests.Session()
    response = ask_duckduckgo(user_text, session)
    
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
            time.sleep(0.5)
    else:
        await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print(f"🚀 Бот запускается...")
    print(f"🧠 Модель: {MODEL}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error)
    
    print("✅ Бот работает!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
