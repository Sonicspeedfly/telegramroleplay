#!/usr/bin/env python3
"""
Простой Telegram бот "Хроники Нейкона" без проблемных зависимостей
"""

import os
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict
import google.generativeai as genai

import google.generativeai as genai
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SimpleTelegramBot:
    def __init__(self):
        self.system_prompt = ""
        self.gemini_api_key = ""
        self.telegram_token = ""
        self.model = None
        self.user_sessions: Dict[int, Dict] = {}
        self.base_url = "https://api.telegram.org/bot"
        
        # Загружаем конфигурацию
        self.load_config()
        self.load_settings()
        
        # Инициализируем Gemini
        self.initialize_gemini()
    
    def load_config(self):
        """Загрузка конфигурации из config.json"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.system_prompt = config.get('system_prompt', '')
        except FileNotFoundError:
            logger.error("Файл config.json не найден!")
            raise
        except json.JSONDecodeError:
            logger.error("Ошибка чтения config.json!")
            raise
    
    def load_settings(self):
        """Загрузка настроек из settings.json"""
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.gemini_api_key = settings.get('gemini_api_key', '')
                self.telegram_token = settings.get('telegram_token', '')
        except FileNotFoundError:
            logger.error("Файл settings.json не найден!")
            raise
        except json.JSONDecodeError:
            logger.error("Ошибка чтения settings.json!")
            raise
    
    def initialize_gemini(self):
        """Инициализация Gemini API"""
        if not self.gemini_api_key:
            logger.warning("API ключ Gemini не установлен!")
            return
        
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.5-pro')
            logger.info("Gemini API успешно инициализирован!")
        except Exception as e:
            logger.error(f"Ошибка инициализации Gemini API: {e}")
    
    def get_user_session(self, user_id: int) -> Dict:
        """Получение или создание сессии пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'chat_history': [],
                'current_game': None,
                'last_activity': datetime.now(),
                'files': [],  # Список сохраненных файлов
                'images': []   # Список сохраненных изображений
            }
        return self.user_sessions[user_id]
    
    def send_message(self, chat_id: int, text: str, reply_markup=None):
        """Отправка сообщения через Telegram API"""
        url = f"{self.base_url}{self.telegram_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return None
    
    def send_chat_action(self, chat_id: int, action: str):
        """Отправка действия чата"""
        url = f"{self.base_url}{self.telegram_token}/sendChatAction"
        data = {
            'chat_id': chat_id,
            'action': action
        }
        
        try:
            requests.post(url, json=data)
        except Exception as e:
            logger.error(f"Ошибка отправки действия чата: {e}")
    
    def get_updates(self, offset=None):
        """Получение обновлений от Telegram"""
        url = f"{self.base_url}{self.telegram_token}/getUpdates"
        params = {'timeout': 30}
        if offset:
            params['offset'] = offset
        
        try:
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка получения обновлений: {e}")
            return None
    
    def get_file(self, file_id):
        """Получение информации о файле"""
        url = f"{self.base_url}{self.telegram_token}/getFile"
        params = {'file_id': file_id}
        
        try:
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка получения информации о файле: {e}")
            return None
    
    def download_file(self, file_path):
        """Скачивание файла"""
        url = f"https://api.telegram.org/file/bot{self.telegram_token}/{file_path}"
        
        try:
            response = requests.get(url)
            return response.content
        except Exception as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            return None
    
    def extract_text_from_document(self, file_content, file_name):
        """Извлечение текста из документа"""
        try:
            # Определяем тип файла по расширению
            file_ext = file_name.lower().split('.')[-1]
            
            if file_ext in ['txt', 'md']:
                # Текстовые файлы
                return file_content.decode('utf-8', errors='ignore')
            
            elif file_ext in ['pdf']:
                # PDF файлы - используем PyPDF2 если доступен
                try:
                    import PyPDF2
                    import io
                    pdf_file = io.BytesIO(file_content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text
                except ImportError:
                    return "PDF файл получен, но для чтения нужна библиотека PyPDF2. Установите: pip install PyPDF2"
            
            elif file_ext in ['docx']:
                # DOCX файлы
                try:
                    from docx import Document
                    import io
                    doc = Document(io.BytesIO(file_content))
                    text = ""
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + "\n"
                    return text
                except ImportError:
                    return "DOCX файл получен, но для чтения нужна библиотека python-docx. Установите: pip install python-docx"
            
            else:
                return f"Неподдерживаемый тип файла: {file_ext}. Поддерживаются: txt, md, pdf, docx"
                
        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return f"Ошибка при чтении файла: {e}"
    
    def save_file_to_memory(self, user_id: int, file_info: dict, file_content: bytes, file_type: str):
        """Сохранение файла в память пользователя"""
        session = self.get_user_session(user_id)
        
        file_data = {
            'name': file_info.get('name', 'unknown'),
            'type': file_type,
            'content': file_content,
            'description': file_info.get('description', ''),
            'timestamp': datetime.now().isoformat(),
            'size': len(file_content)
        }
        
        if file_type == 'document':
            session['files'].append(file_data)
            # Ограничиваем количество сохраненных файлов
            if len(session['files']) > 10:
                session['files'] = session['files'][-10:]
        elif file_type == 'image':
            session['images'].append(file_data)
            # Ограничиваем количество сохраненных изображений
            if len(session['images']) > 10:
                session['images'] = session['images'][-10:]
    
    def get_memory_context(self, user_id: int) -> str:
        """Получение контекста памяти для пользователя"""
        session = self.get_user_session(user_id)
        context = ""
        
        # Добавляем информацию о сохраненных файлах
        if session['files']:
            context += "\n📄 Сохраненные документы:\n"
            for i, file_data in enumerate(session['files'], 1):
                context += f"{i}. {file_data['name']}"
                if file_data['description']:
                    context += f" - {file_data['description']}"
                context += f" ({file_data['timestamp'][:10]})\n"
        
        # Добавляем информацию о сохраненных изображениях
        if session['images']:
            context += "\n🖼️ Сохраненные изображения:\n"
            for i, image_data in enumerate(session['images'], 1):
                context += f"{i}. {image_data['name']}"
                if image_data['description']:
                    context += f" - {image_data['description']}"
                context += f" ({image_data['timestamp'][:10]})\n"
        
        return context
    
    def answer_callback_query(self, callback_query_id: str, text: str = None):
        """Ответ на callback query"""
        url = f"{self.base_url}{self.telegram_token}/answerCallbackQuery"
        data = {'callback_query_id': callback_query_id}
        if text:
            data['text'] = text
        
        try:
            requests.post(url, json=data)
        except Exception as e:
            logger.error(f"Ошибка ответа на callback: {e}")
    
    def handle_start_command(self, chat_id: int, user_name: str):
        """Обработка команды /start"""
        welcome_text = f"""
🎮 Добро пожаловать в "Хроники Нейкона", {user_name}!

Я — Нейкон, ваш ИИ-Мастер Игры для ролевых игр. 

📋 Доступные команды:
/start - Начать игру
/new - Новая история
/help - Помощь

Просто напишите мне, чтобы начать ролевую игру!
        """
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Новая игра', 'callback_data': 'new_game'}],
                [{'text': '📚 Помощь', 'callback_data': 'help'}]
            ]
        }
        
        self.send_message(chat_id, welcome_text, keyboard)
    
    def handle_help_command(self, chat_id: int):
        """Обработка команды /help"""
        help_text = """
🎮 **Хроники Нейкона - Помощь**

**Основные команды:**
/start - Запуск бота
/new - Начать новую игру
/memory - Просмотр сохраненных файлов
/help - Эта справка

**Как играть:**
1. Нажмите "Новая игра" или напишите /new
2. Опишите, в какую ролевую игру хотите играть
3. Нейкон создаст мир и начнет игру
4. Отвечайте на вопросы и описывайте действия

**📄 Анализ документов:**
- Загрузите документ (PDF, DOCX, TXT, MD)
- Нейкон проанализирует содержимое
- Получите подробный анализ и рекомендации
- Максимальный размер файла: 20MB

**🖼️ Анализ изображений:**
- Отправьте фото с описанием или без
- Нейкон проанализирует изображение
- Интегрирует его в ролевую игру
- Максимальный размер файла: 20MB

**Поддерживаемые форматы:**
- 📄 PDF (.pdf)
- 📝 Word (.docx)
- 📄 Текст (.txt, .md)
- 🖼️ Изображения (JPG, PNG, GIF)

**💾 Постоянная память:**
- Все загруженные документы и изображения сохраняются
- Нейкон помнит все файлы и их содержимое
- Используйте /memory для просмотра сохраненных файлов
- Память автоматически включается в контекст игры

**Примеры игр:**
- Фэнтези (эльфы, драконы, магия)
- Научная фантастика (космос, роботы)
- Детектив (расследования, загадки)

Удачной игры! 🎲
        """
        self.send_message(chat_id, help_text)
    
    def handle_new_command(self, chat_id: int, user_id: int):
        """Обработка команды /new"""
        session = self.get_user_session(user_id)
        
        # Очищаем историю
        session['chat_history'] = []
        session['current_game'] = None
        
        message = (
            "🎮 Новая игра начата! Опишите, в какую ролевую игру хотите играть.\n\n"
            "Например:\n"
            "• 'Хочу быть эльфом-магом в фэнтези мире'\n"
            "• 'Начнем космическую оперу, я капитан корабля'\n"
            "• 'Детектив в Нью-Йорке 1940-х годов'"
        )
        
        self.send_message(chat_id, message)
    
    def handle_memory_command(self, chat_id: int, user_id: int):
        """Обработка команды /memory"""
        session = self.get_user_session(user_id)
        
        memory_context = self.get_memory_context(user_id)
        if memory_context:
            message = f"💾 **Память пользователя:**\n{memory_context}\n\nИспользуйте эту информацию в игре!"
        else:
            message = "💾 Память пуста. Загрузите документы или изображения, чтобы они сохранились в памяти."
        
        self.send_message(chat_id, message)
    
    def handle_callback_query(self, callback_query):
        """Обработка callback query"""
        chat_id = callback_query['message']['chat']['id']
        user_id = callback_query['from']['id']
        callback_data = callback_query['data']
        callback_id = callback_query['id']
        
        # Отвечаем на callback
        self.answer_callback_query(callback_id)
        
        if callback_data == "new_game":
            self.handle_new_command(chat_id, user_id)
        elif callback_data == "help":
            self.handle_help_command(chat_id)
    
    def handle_photo(self, message):
        """Обработка загруженного изображения"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        user_name = message['from'].get('first_name', 'Пользователь')
        photos = message['photo']
        caption = message.get('caption', '')
        
        # Получаем фото с максимальным разрешением (последний элемент в массиве)
        photo = photos[-1]
        file_id = photo['file_id']
        file_size = photo.get('file_size', 0)
        
        # Проверяем размер файла (максимум 5MB для экономии токенов)
        if file_size > 5 * 1024 * 1024:
            self.send_message(chat_id, "❌ Фото слишком большое. Максимальный размер: 5MB")
            return
        
        # Отправляем статус обработки
        self.send_message(chat_id, f"🖼️ Анализирую изображение...")
        self.send_chat_action(chat_id, "typing")
        
        try:
            # Получаем информацию о файле
            file_info = self.get_file(file_id)
            if not file_info or not file_info.get('ok'):
                self.send_message(chat_id, "❌ Не удалось получить информацию о фото")
                return
            
            file_path = file_info['result']['file_path']
            
            # Скачиваем файл
            file_content = self.download_file(file_path)
            if not file_content:
                self.send_message(chat_id, "❌ Не удалось скачать фото")
                return
            
            # Обновляем сессию пользователя
            session = self.get_user_session(user_id)
            session['last_activity'] = datetime.now()
            
            # Сохраняем изображение в память
            image_info = {
                'name': f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                'description': caption if caption else "Изображение для ролевой игры"
            }
            self.save_file_to_memory(user_id, image_info, file_content, 'image')
            
            # Формируем контекст для анализа изображения
            context_text = self.system_prompt + "\n\n"
            context_text += "Пользователь отправил изображение для анализа в контексте ролевой игры.\n\n"
            
            if caption:
                context_text += f"Описание пользователя: {caption}\n\n"
                context_text += "Нейкон, проанализируй это изображение с учетом описания пользователя и интегрируй его в ролевую игру. Опиши, что ты видишь, и как это может повлиять на игровой процесс."
            else:
                context_text += "Нейкон, проанализируй это изображение и интегрируй его в ролевую игру. Опиши, что ты видишь, и как это может повлиять на игровой процесс."
            
            # Создаем модель для работы с изображениями
            try:
                vision_model = genai.GenerativeModel('gemini-2.5-pro')
                
                # Создаем изображение для Gemini
                import io
                from PIL import Image
                
                image = Image.open(io.BytesIO(file_content))
                
                # Отправляем изображение и текст в Gemini
                response = vision_model.generate_content([context_text, image])
                analysis = response.text.strip()
                
                # Добавляем длительную задержку для избежания превышения квоты
                time.sleep(10)
                
                # Добавляем информацию о фото в историю
                photo_description = f"Отправлено изображение{f' с описанием: {caption}' if caption else ''}"
                session['chat_history'].append({
                    "role": "user", 
                    "content": photo_description
                })
                
                # Добавляем анализ в историю
                session['chat_history'].append({"role": "assistant", "content": analysis})
                
                # Ограничиваем длину истории для экономии токенов
                if len(session['chat_history']) > 10:
                    session['chat_history'] = session['chat_history'][-10:]
                
                # Отправляем анализ
                self.send_message(chat_id, f"🖼️ **Анализ изображения:**\n\n{analysis}")
                
            except ImportError:
                # Если PIL не установлен, отправляем сообщение об ошибке
                self.send_message(chat_id, 
                    "❌ Для анализа изображений нужна библиотека Pillow. Установите: pip install Pillow")
                return
                
        except Exception as e:
            logger.error(f"Ошибка при обработке изображения: {e}")
            
            # Проверяем ошибку квоты
            if "429" in str(e) or "quota" in str(e).lower():
                self.send_message(chat_id, 
                    "⚠️ Превышен лимит запросов к Gemini API. Попробуйте через несколько минут.")
            else:
                self.send_message(chat_id, 
                    "❌ Произошла ошибка при обработке изображения. Попробуйте позже.")
    
    def handle_document(self, message):
        """Обработка загруженного документа"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        user_name = message['from'].get('first_name', 'Пользователь')
        document = message['document']
        
        file_name = document.get('file_name', 'document')
        file_id = document['file_id']
        file_size = document.get('file_size', 0)
        
        # Проверяем размер файла (максимум 5MB для экономии токенов)
        if file_size > 5 * 1024 * 1024:
            self.send_message(chat_id, "❌ Файл слишком большой. Максимальный размер: 5MB")
            return
        
        # Отправляем статус обработки
        self.send_message(chat_id, f"📄 Обрабатываю документ: {file_name}")
        self.send_chat_action(chat_id, "typing")
        
        try:
            # Получаем информацию о файле
            file_info = self.get_file(file_id)
            if not file_info or not file_info.get('ok'):
                self.send_message(chat_id, "❌ Не удалось получить информацию о файле")
                return
            
            file_path = file_info['result']['file_path']
            
            # Скачиваем файл
            file_content = self.download_file(file_path)
            if not file_content:
                self.send_message(chat_id, "❌ Не удалось скачать файл")
                return
            
            # Извлекаем текст из документа
            document_text = self.extract_text_from_document(file_content, file_name)
            
            if document_text.startswith("Ошибка") or document_text.startswith("Неподдерживаемый"):
                self.send_message(chat_id, document_text)
                return
            
            # Обновляем сессию пользователя
            session = self.get_user_session(user_id)
            session['last_activity'] = datetime.now()
            
            # Сохраняем документ в память
            file_info = {
                'name': file_name,
                'description': f"Документ содержит: {document_text[:200]}...",
                'text_content': document_text
            }
            self.save_file_to_memory(user_id, file_info, file_content, 'document')
            
            # Добавляем информацию о документе в историю
            session['chat_history'].append({
                "role": "user", 
                "content": f"Загружен документ '{file_name}':\n\n{document_text[:1000]}{'...' if len(document_text) > 1000 else ''}"
            })
            
            # Ограничиваем длину истории для экономии токенов
            if len(session['chat_history']) > 10:
                session['chat_history'] = session['chat_history'][-10:]
            
            # Ограничиваем размер текста для экономии токенов
            max_text_length = 2000  # Ограничиваем до 2000 символов
            if len(document_text) > max_text_length:
                document_text = document_text[:max_text_length] + "..."
            
            # Формируем контекст для анализа
            context_text = self.system_prompt + "\n\n"
            context_text += f"Пользователь загрузил документ '{file_name}' для анализа.\n\n"
            context_text += f"Содержимое документа:\n{document_text}\n\n"
            context_text += "Нейкон, проанализируй этот документ и дай краткий ответ с рекомендациями."
            
            # Отправляем в Gemini для анализа с текстом документа
            response = self.model.generate_content(context_text)
            analysis = response.text.strip()
            
            # Добавляем длительную задержку для избежания превышения квоты
            time.sleep(10)
            
            # Добавляем анализ в историю
            session['chat_history'].append({"role": "assistant", "content": analysis})
            
            # Отправляем анализ
            self.send_message(chat_id, f"📊 **Анализ документа '{file_name}':**\n\n{analysis}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке документа: {e}")
            
            # Проверяем ошибку квоты
            if "429" in str(e) or "quota" in str(e).lower():
                self.send_message(chat_id, 
                    "⚠️ Превышен лимит запросов к Gemini API. Попробуйте через несколько минут.")
            elif "format" in str(e).lower() or "type" in str(e).lower():
                self.send_message(chat_id, 
                    "❌ Ошибка формата файла. Попробуйте другой документ.")
            else:
                self.send_message(chat_id, 
                    "❌ Произошла ошибка при обработке документа. Попробуйте позже.")
    
    def handle_message(self, message):
        """Обработка текстового сообщения"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        user_name = message['from'].get('first_name', 'Пользователь')
        text = message['text']
        
        # Обновляем время последней активности
        session = self.get_user_session(user_id)
        session['last_activity'] = datetime.now()
        
        # Добавляем сообщение пользователя в историю
        session['chat_history'].append({"role": "user", "content": text})
        
        # Ограничиваем длину истории для экономии токенов
        if len(session['chat_history']) > 10:
            session['chat_history'] = session['chat_history'][-10:]
        
        # Отправляем "печатает" статус
        self.send_chat_action(chat_id, "typing")
        
        try:
            if not self.model:
                self.send_message(chat_id, 
                    "❌ Ошибка: Gemini API не инициализирован. "
                    "Проверьте настройки API ключа.")
                return
            
            # Формируем контекст
            context_text = self.system_prompt + "\n\n"
            
            # Добавляем контекст памяти (сохраненные файлы и изображения)
            memory_context = self.get_memory_context(user_id)
            if memory_context:
                context_text += "💾 ПАМЯТЬ ПОЛЬЗОВАТЕЛЯ:" + memory_context + "\n\n"
            
            # Добавляем историю диалога
            for msg in session['chat_history'][:-1]:
                if msg["role"] == "user":
                    context_text += f"Пользователь: {msg['content']}\n"
                else:
                    context_text += f"Нейкон: {msg['content']}\n"
            
            # Добавляем текущее сообщение
            context_text += f"Пользователь: {text}\n"
            context_text += "Нейкон:"
            
            # Отправляем в Gemini
            response = self.model.generate_content(context_text)
            assistant_message = response.text.strip()
            
            # Добавляем длительную задержку для избежания превышения квоты
            time.sleep(5)
            
            # Добавляем ответ в историю
            session['chat_history'].append({"role": "assistant", "content": assistant_message})
            
            # Отправляем ответ
            self.send_message(chat_id, assistant_message)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            
            # Проверяем ошибку квоты
            if "429" in str(e) or "quota" in str(e).lower():
                self.send_message(chat_id, 
                    "⚠️ Превышен лимит запросов к Gemini API. Попробуйте через несколько минут.")
            else:
                self.send_message(chat_id, 
                    "❌ Произошла ошибка при обработке сообщения. Попробуйте позже.")
    
    def process_update(self, update):
        """Обработка обновления"""
        if 'message' in update:
            message = update['message']
            text = message.get('text', '')
            
            # Проверяем наличие документа
            if 'document' in message:
                self.handle_document(message)
            # Проверяем наличие фото
            elif 'photo' in message:
                self.handle_photo(message)
            elif text.startswith('/start'):
                self.handle_start_command(message['chat']['id'], 
                                       message['from'].get('first_name', 'Пользователь'))
            elif text.startswith('/help'):
                self.handle_help_command(message['chat']['id'])
            elif text.startswith('/new'):
                self.handle_new_command(message['chat']['id'], message['from']['id'])
            elif text.startswith('/memory'):
                self.handle_memory_command(message['chat']['id'], message['from']['id'])
            else:
                self.handle_message(message)
        
        elif 'callback_query' in update:
            self.handle_callback_query(update['callback_query'])
    
    def run(self):
        """Запуск бота"""
        if not self.telegram_token:
            logger.error("Telegram токен не установлен!")
            return
        
        logger.info("Бот запущен!")
        offset = None
        
        while True:
            try:
                updates = self.get_updates(offset)
                if updates and updates.get('ok'):
                    for update in updates['result']:
                        self.process_update(update)
                        offset = update['update_id'] + 1
                
            except KeyboardInterrupt:
                logger.info("Бот остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка в главном цикле: {e}")
                continue

def main():
    """Главная функция"""
    bot = SimpleTelegramBot()
    bot.run()

if __name__ == "__main__":
    main() 