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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env!")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== HUGGING FACE PUBLIC API ==========

def ask_huggingface(message):
    """Бесплатный Hugging Face Inference API (публичные модели)"""
    
    # Список публичных моделей которые работают без ключа
    models = [
        {
            "name": "microsoft/DialoGPT-medium",
            "api_url": "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium",
            "payload": lambda msg: {"inputs": msg}
        },
        {
            "name": "facebook/blenderbot-400M-distill",
            "api_url": "https://api-inference.huggingface.co/models/facebook/blenderbot-400M-distill",
            "payload": lambda msg: {"inputs": msg}
        },
        {
            "name": "google/flan-t5-large",
            "api_url": "https://api-inference.huggingface.co/models/google/flan-t5-large",
            "payload": lambda msg: {"inputs": msg}
        }
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }
    
    # Пробуем модели по очереди
    for model in models:
        try:
            logger.info(f"🤖 Пробую {model['name']}...")
            
            payload = model["payload"](message)
            
            resp = requests.post(
                model["api_url"], 
                headers=headers, 
                json=payload, 
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                
                # Разные форматы ответа для разных моделей
                if isinstance(data, list) and len(data) > 0:
                    if "generated_text" in data[0]:
                        return data[0]["generated_text"]
                    elif "generated_response" in data[0]:
                        return data[0]["generated_response"]
                elif isinstance(data, dict):
                    if "generated_text" in data:
                        return data["generated_text"]
                    elif "response" in data:
                        return data["response"]
                
                return str(data)
            else:
                logger.warning(f"❌ {model['name']}: {resp.status_code}")
                continue
                
        except Exception as e:
            logger.warning(f"⚠️ {model['name']}: {e}")
            continue
    
    return None

# ========== РЕЗЕРВ: ЛОКАЛЬНЫЙ ОТВЕТ ==========

def fallback_response(message):
    """Заглушка если все API недоступны"""
    responses = [
        "🤔 Интересный вопрос! Но сейчас все AI сервера перегружены. Попробуй через минуту.",
        "💭 Я бы ответил, но нейросети временно недоступны. Напиши позже!",
        "🔄 Технические работы у всех провайдеров. Повтори запрос через 30 секунд.",
        f"📝 Ты спросил: '{message[:50]}...'\nНо AI сейчас офлайн 😢"
    ]
    import random
    return random.choice(responses)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

def get_ai_response(message):
    """Получаем ответ от AI"""
    
    # 1. Пробуем Hugging Face
    response = ask_huggingface(message)
    if response and len(response) > 10:
        return response
    
    # 2. Заглушка
    return fallback_response(message)

# ========== TELEGRAM ОБРАБОТЧИКИ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 AI Бот (Hugging Face)\n"
        "🔒 Без API ключей\n"
        "🧠 Модели: DialoGPT, BlenderBot, Flan-T5\n\n"
        "Просто напиши вопрос!"
    )

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
    print("🚀 Бот запущен на Hugging Face API")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
