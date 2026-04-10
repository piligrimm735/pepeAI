#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import sys
import os
import subprocess
import requests
import tarfile
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL = os.getenv("MODEL", "tinyllama")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env!")
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== АВТОУСТАНОВКА OLLAMA ==========

def check_ollama():
    """Проверяет установлена ли Ollama"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def install_ollama():
    """Автоматическая установка Ollama"""
    print("📦 Ollama не найдена. Начинаю установку...")
    
    try:
        # Создаём временную папку
        temp_dir = "/tmp/ollama_install"
        os.makedirs(temp_dir, exist_ok=True)
        os.chdir(temp_dir)
        
        # Определяем архитектуру
        arch = subprocess.check_output(["uname", "-m"]).decode().strip()
        if arch == "x86_64":
            ollama_url = "https://github.com/ollama/ollama/releases/download/v0.4.7/ollama-linux-amd64.tgz"
        elif arch == "aarch64":
            ollama_url = "https://github.com/ollama/ollama/releases/download/v0.4.7/ollama-linux-arm64.tgz"
        else:
            print(f"❌ Неподдерживаемая архитектура: {arch}")
            return False
        
        print(f"📥 Скачиваю Ollama с {ollama_url}...")
        
        # Скачиваем
        response = requests.get(ollama_url, stream=True)
        with open("ollama.tgz", "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("📦 Распаковываю...")
        
        # Распаковываем
        with tarfile.open("ollama.tgz", "r:gz") as tar:
            tar.extractall()
        
        # Копируем в систему
        shutil.copy("ollama", "/usr/local/bin/ollama")
        os.chmod("/usr/local/bin/ollama", 0o755)
        
        # Создаём systemd сервис
        service_content = """[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
        with open("/etc/systemd/system/ollama.service", "w") as f:
            f.write(service_content)
        
        # Запускаем
        subprocess.run(["systemctl", "daemon-reload"])
        subprocess.run(["systemctl", "enable", "ollama"])
        subprocess.run(["systemctl", "start", "ollama"])
        
        # Ждём запуска
        time.sleep(3)
        
        print("✅ Ollama установлена и запущена!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка установки Ollama: {e}")
        return False
    
    finally:
        # Чистим
        shutil.rmtree(temp_dir, ignore_errors=True)
        os.chdir("/")

def check_and_pull_model(model_name):
    """Проверяет и скачивает модель если нужно"""
    try:
        # Проверяем есть ли модель
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        
        if model_name not in result.stdout:
            print(f"📥 Скачиваю модель {model_name}...")
            print("Это может занять несколько минут...")
            
            subprocess.run(["ollama", "pull", model_name], check=True)
            print(f"✅ Модель {model_name} готова!")
        else:
            print(f"✅ Модель {model_name} уже есть")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        return False

def init_ollama():
    """Инициализация Ollama"""
    print("🔧 Проверяю Ollama...")
    
    # Проверяем и устанавливаем Ollama
    if not check_ollama():
        print("⚠️ Ollama не установлена")
        if not install_ollama():
            return False
    
    # Проверяем и скачиваем модель
    if not check_and_pull_model(MODEL):
        return False
    
    return True

# ========== РАБОТА С OLLAMA ==========

def ask_ollama(message):
    """Запрос к Ollama"""
    try:
        import ollama
        
        messages = [
            {
                "role": "system",
                "content": "Ты полезный ассистент. Отвечай на русском языке кратко и по делу."
            },
            {
                "role": "user",
                "content": message
            }
        ]
        
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            options={
                "temperature": 0.7,
                "max_tokens": 500
            }
        )
        
        return response["message"]["content"].strip()
        
    except ImportError:
        return "❌ Установи ollama-python: pip install ollama"
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"❌ Ошибка Ollama: {str(e)[:100]}"

def get_available_models():
    """Список доступных моделей"""
    try:
        import ollama
        models = ollama.list()
        return [m["name"] for m in models["models"]]
    except:
        return []

# ========== TELEGRAM ОБРАБОТЧИКИ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models = get_available_models()
    models_str = ", ".join(models[:5]) if models else "нет"
    
    await update.message.reply_text(
        f"🦙 Ollama AI Бот\n"
        f"🧠 Модель: {MODEL}\n"
        f"📦 Доступные модели: {models_str}\n"
        f"💾 Локально на сервере\n\n"
        f"Просто напиши вопрос!\n"
        f"/pull модель — скачать новую модель\n"
        f"/models — список моделей\n"
        f"/switch модель — сменить модель"
    )

async def pull_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📥 Укажи модель для скачивания:\n"
            "`/pull tinyllama`\n"
            "`/pull llama3.2:1b`\n"
            "`/pull gemma2:2b`",
            parse_mode="Markdown"
        )
        return
    
    model = context.args[0]
    msg = await update.message.reply_text(f"📥 Скачиваю {model}... Это займёт пару минут.")
    
    try:
        subprocess.run(["ollama", "pull", model], check=True, timeout=300)
        await msg.edit_text(f"✅ Модель {model} установлена!")
    except subprocess.TimeoutExpired:
        await msg.edit_text(f"⏰ Скачивание {model} занимает больше 5 минут. Проверь вручную.")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models = get_available_models()
    
    if not models:
        await update.message.reply_text("📦 Нет установленных моделей. Скачай: `/pull tinyllama`", parse_mode="Markdown")
        return
    
    msg = "📦 *Установленные модели:*\n\n"
    for m in models[:10]:
        msg += f"• `{m}`\n"
    
    msg += "\nСменить: `/switch название`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def switch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MODEL
    
    if not context.args:
        await update.message.reply_text("Укажи модель: `/switch llama3.2:1b`", parse_mode="Markdown")
        return
    
    new_model = context.args[0]
    models = get_available_models()
    
    if new_model in models:
        MODEL = new_model
        await update.message.reply_text(f"✅ Модель изменена на `{MODEL}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Модель `{new_model}` не найдена.\n"
            f"Скачай: `/pull {new_model}`",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = ask_ollama(user_text)
    
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
            time.sleep(0.3)
    else:
        await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

# ========== ЗАПУСК ==========

def main():
    print("🚀 Запуск Ollama Telegram Bot")
    print("=" * 40)
    
    # Инициализируем Ollama
    if not init_ollama():
        print("❌ Не удалось инициализировать Ollama")
        print("Попробуй установить вручную:")
        print("curl -fsSL https://ollama.com/install.sh | sh")
        sys.exit(1)
    
    print("=" * 40)
    print(f"✅ Ollama готова!")
    print(f"🧠 Текущая модель: {MODEL}")
    print(f"🤖 Запускаю Telegram бота...")
    
    # Проверяем ollama-python
    try:
        import ollama
    except ImportError:
        print("⚠️ Устанавливаю ollama-python...")
        subprocess.run([sys.executable, "-m", "pip", "install", "ollama"])
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pull", pull_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("switch", switch_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error)
    
    print("✅ Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
