#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import requests
import json
import time
import sys
import os
import uuid
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL = os.getenv("MODEL", "gpt-3.5-turbo")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env!")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== НОВЫЙ МЕТОД С ПОЛНЫМИ ЗАГОЛОВКАМИ ==========

def ask_duckduckgo(message):
    """Исправленный запрос к DuckDuckGo AI"""
    
    session = requests.Session()
    
    # Генерируем уникальный ID сессии
    x_vqd_4 = str(uuid.uuid4()).replace('-', '')[:16]
    
    # Заголовки как у браузера
    headers = {
        "Accept": "text/event-stream",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": "https://duckduckgo.com",
        "Pragma": "no-cache",
        "Referer": "https://duckduckgo.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-vqd-4": x_vqd_4
    }
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}]
    }
    
    try:
        # Сначала получаем статус для получения реального VQD токена
        status_url = "https://duckduckgo.com/duckchat/v1/status"
        status_resp = session.get(status_url, headers={"x-vqd-accept": "1", "User-Agent": headers["User-Agent"]})
        
        if "x-vqd-4" in status_resp.headers:
            headers["x-vqd-4"] = status_resp.headers["x-vqd-4"]
            logger.info(f"✅ VQD получен: {headers['x-vqd-4'][:10]}...")
        
        # Отправляем сообщение
        chat_url = "https://duckduckgo.com/duckchat/v1/chat"
        resp = session.post(chat_url, headers=headers, json=payload, timeout=30, stream=True)
        
        if resp.status_code == 403:
            logger.error("❌ DuckDuckGo заблокировал IP")
            return None
        elif resp.status_code != 200:
            logger.error(f"❌ HTTP {resp.status_code}")
            return None
        
        # Собираем ответ
        full_response = ""
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("message"):
                        full_response += data["message"]
                except:
                    continue
        
        return full_response.strip() if full_response else None
        
    except Exception as e:
        logger.error(f"❌ DuckDuckGo ошибка: {e}")
        return None

# ========== РЕЗЕРВНЫЙ ПРОВАЙДЕР: BlackBox AI ==========

def ask_blackbox(message):
    """Резервный провайдер - BlackBox AI"""
    try:
        url = "https://api.blackbox.ai/api/chat"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        payload = {
            "messages": [{"role": "user", "content": message}],
            "model": "blackboxai"
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            return resp.text.strip()
        return None
    except:
        return None

# ========== РЕЗЕРВНЫЙ ПРОВАЙДЕР 2: Cloudflare AI ==========

def ask_cloudflare(message):
    """Cloudflare Workers AI (нужен свой воркер)"""
    try:
        # Замени на свой URL если есть
        url = "https://llama3.yourname.workers.dev"
        resp = requests.get(f"{url}?q={requests.utils.quote(message)}", timeout=30)
        if resp.status_code == 200:
            return resp.text.strip()
        return None
    except:
        return None

# ========== ОСНОВНАЯ ФУНКЦИЯ С ФОЛЛБЭКОМ ==========

def get_ai_response(message):
    """Пробуем разные провайдеры"""
    
    # 1. Пробуем DuckDuckGo
    logger.info("🦆 Пробую DuckDuckGo...")
    response = ask_duckduckgo(message)
    if response:
        return response
    
    # 2. Пробуем BlackBox
    logger.info("📦 Пробую BlackBox AI...")
    response = ask_blackbox(message)
    if response:
        return response + "\n\n_(через BlackBox AI)_"
    
    # 3. Заглушка если всё упало
    return "❌ Все AI провайдеры недоступны. Попробуй позже."

# ========== ОБРАБОТЧИКИ TELEGRAM ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 AI Бот\n"
        f"🧠 Модель: {MODEL}\n"
        f"🔒 Без API ключей\n\n"
        f"Просто напиши вопрос!\n"
        f"/model — сменить модель"
    )

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODEL
    models = """
📋 *Модели:*
• `gpt-3.5-turbo` — OpenAI
• `claude-3-haiku` — Anthropic  
• `llama-3-70b` — Meta
• `mixtral-8x7b` — Mistral

Смена: `model:название`
Текущая: `{MODEL}`
"""
    await update.message.reply_text(models.format(MODEL=MODEL), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
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
    
    # Отправляем "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    logger.info(f"📨 [{user_id}] {user_text[:50]}...")
    
    # Получаем ответ
    response = get_ai_response(user_text)
    
    logger.info(f"📤 [{user_id}] Ответ: {len(response)} символов")
    
    # Отправляем
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
            time.sleep(0.3)
    else:
        await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

def main():
    print(f"🚀 Бот запущен")
    print(f"🧠 Модель: {MODEL}")
    print(f"📡 Провайдеры: DuckDuckGo + BlackBox (фоллбэк)")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
