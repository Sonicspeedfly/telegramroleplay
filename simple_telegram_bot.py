#!/usr/bin/env python3
"""
Простой Telegram бот "Хроники Нейкона" с продвинутой системой памяти
"""

import os
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import io
import tempfile

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class RoleplayGame:
    """Класс для хранения данных ролевой игры"""
    def __init__(self, game_id: str, title: str, description: str, tags: List[str]):
        self.game_id = game_id
        self.title = title
        self.description = description
        self.tags = tags
        self.characters = []
        self.chat_log_file_uri = None  # URI файла с полным чат-логом
        self.checkpoint_file_uri = None  # URI файла с чекпоинтом
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.is_active = False

class Character:
    """Класс для хранения данных персонажа"""
    def __init__(self, name: str, description: str, traits: str, backstory: str):
        self.name = name
        self.description = description
        self.traits = traits
        self.backstory = backstory
        self.current_state = ""
        self.relationships = {}

class SimpleTelegramBot:
    def __init__(self):
        self.system_prompt = ""
        self.gemini_api_key = ""
        self.telegram_token = ""
        self.model = None
        self.user_sessions: Dict[int, Dict] = {}
        self.base_url = "https://api.telegram.org/bot"
        self.google_files_api_base = "https://generativelanguage.googleapis.com"
        
        # Система показателей состояния
        self.system_status = {
            'bot_started': False,
            'gemini_connected': False,
            'telegram_connected': False,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'files_uploaded': 0,
            'games_created': 0,
            'active_users': 0,
            'last_error': None,
            'start_time': None
        }
        
        # Загружаем конфигурацию
        self.load_config()
        self.load_settings()
        
        # Инициализируем Gemini
        self.initialize_gemini()
        
        # Загружаем сохраненные игры
        self.load_saved_games()
        
        # Обновляем статус
        self.update_system_status('bot_started', True)
        self.system_status['start_time'] = datetime.now()
    
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
            self.update_system_status('gemini_connected', False)
            return
        
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.5-pro')
            logger.info("Gemini API успешно инициализирован!")
            self.update_system_status('gemini_connected', True)
        except Exception as e:
            logger.error(f"Ошибка инициализации Gemini API: {e}")
            self.update_system_status('gemini_connected', False)
            self.update_system_status('last_error', f"Gemini API: {e}")
    
    def load_saved_games(self):
        """Загрузка сохраненных игр из файла"""
        try:
            if os.path.exists('saved_games.json'):
                with open('saved_games.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.saved_games = {}
                    for user_id, games_data in data.items():
                        self.saved_games[int(user_id)] = []
                        for game_data in games_data:
                            game = RoleplayGame(
                                game_data['game_id'],
                                game_data['title'], 
                                game_data['description'],
                                game_data['tags']
                            )
                            game.chat_log_file_uri = game_data.get('chat_log_file_uri')
                            game.checkpoint_file_uri = game_data.get('checkpoint_file_uri')
                            game.created_at = datetime.fromisoformat(game_data['created_at'])
                            game.last_updated = datetime.fromisoformat(game_data['last_updated'])
                            game.is_active = game_data.get('is_active', False)
                            
                            # Загружаем персонажей
                            for char_data in game_data.get('characters', []):
                                char = Character(
                                    char_data['name'],
                                    char_data['description'],
                                    char_data['traits'],
                                    char_data['backstory']
                                )
                                char.current_state = char_data.get('current_state', '')
                                char.relationships = char_data.get('relationships', {})
                                game.characters.append(char)
                            
                            self.saved_games[int(user_id)].append(game)
            else:
                self.saved_games = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки сохраненных игр: {e}")
            self.saved_games = {}
    
    def save_games_to_file(self):
        """Сохранение игр в файл"""
        try:
            data = {}
            for user_id, games in self.saved_games.items():
                data[str(user_id)] = []
                for game in games:
                    characters_data = []
                    for char in game.characters:
                        characters_data.append({
                            'name': char.name,
                            'description': char.description,
                            'traits': char.traits,
                            'backstory': char.backstory,
                            'current_state': char.current_state,
                            'relationships': char.relationships
                        })
                    
                    data[str(user_id)].append({
                        'game_id': game.game_id,
                        'title': game.title,
                        'description': game.description,
                        'tags': game.tags,
                        'chat_log_file_uri': game.chat_log_file_uri,
                        'checkpoint_file_uri': game.checkpoint_file_uri,
                        'created_at': game.created_at.isoformat(),
                        'last_updated': game.last_updated.isoformat(),
                        'is_active': game.is_active,
                        'characters': characters_data
                    })
            
            with open('saved_games.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения игр: {e}")
    
    def get_mime_type(self, file_name: str) -> str:
        """Определение MIME-типа по расширению файла"""
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        mime_types = {
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'json': 'application/json'
        }
        
        return mime_types.get(file_ext, 'application/octet-stream')
    
    def upload_file_to_google(self, file_content: bytes, file_name: str, mime_type: str = None) -> Optional[str]:
        """Загрузка файла в Google Files API"""
        try:
            # Определяем MIME-тип если не передан
            if not mime_type:
                mime_type = self.get_mime_type(file_name)
            
            logger.info(f"Загружаем файл {file_name} с MIME-типом: {mime_type}")
            
            # Создаем временный файл с правильным расширением
            file_ext = file_name.lower().split('.')[-1] if '.' in file_name else 'bin'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_ext}') as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Загружаем файл через genai с указанием MIME-типа
                uploaded_file = genai.upload_file(
                    temp_file_path, 
                    display_name=file_name,
                    mime_type=mime_type
                )
                logger.info(f"✅ Файл {file_name} успешно загружен: {uploaded_file.uri}")
                
                # Обновляем статистику
                self.increment_counter('files_uploaded')
                
                return uploaded_file.uri
            finally:
                # Удаляем временный файл
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файла в Google API: {e}")
            self.update_system_status('last_error', f"Загрузка файла: {e}")
            return None
    
    def create_chat_log_pdf(self, chat_history: List[Dict], game_title: str) -> bytes:
        """Создание PDF с чат-логом"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            
            # Создаем временный файл для PDF
            temp_pdf = io.BytesIO()
            
            # Создаем документ
            doc = SimpleDocTemplate(temp_pdf, pagesize=letter, 
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            # Стили
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', 
                                       parent=styles['Heading1'],
                                       fontSize=16, 
                                       alignment=1,  # центрирование
                                       spaceAfter=30)
            
            user_style = ParagraphStyle('UserMessage',
                                      parent=styles['Normal'],
                                      fontSize=12,
                                      leftIndent=20,
                                      fontName='Helvetica-Bold')
            
            assistant_style = ParagraphStyle('AssistantMessage',
                                           parent=styles['Normal'],
                                           fontSize=12,
                                           leftIndent=40)
            
            # Содержимое документа
            story = []
            
            # Заголовок
            story.append(Paragraph(f"Чат-лог ролевой игры: {game_title}", title_style))
            story.append(Spacer(1, 12))
            
            # Добавляем сообщения
            for msg in chat_history:
                if msg["role"] == "user":
                    story.append(Paragraph(f"<b>Пользователь:</b> {msg['content']}", user_style))
                else:
                    story.append(Paragraph(f"<b>Нейкон:</b> {msg['content']}", assistant_style))
                story.append(Spacer(1, 6))
            
            # Генерируем PDF
            doc.build(story)
            
            # Возвращаем содержимое
            temp_pdf.seek(0)
            return temp_pdf.getvalue()
            
        except ImportError:
            logger.error("Для создания PDF нужна библиотека reportlab. Установите: pip install reportlab")
            # Создаем простой текстовый файл вместо PDF
            content = f"Чат-лог ролевой игры: {game_title}\n\n"
            for msg in chat_history:
                if msg["role"] == "user":
                    content += f"Пользователь: {msg['content']}\n\n"
                else:
                    content += f"Нейкон: {msg['content']}\n\n"
            return content.encode('utf-8')
        except Exception as e:
            logger.error(f"Ошибка создания PDF: {e}")
            return None
    
    def create_checkpoint_pdf(self, game: RoleplayGame, recent_messages: List[Dict]) -> bytes:
        """Создание PDF с чекпоинтом игры"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            # Создаем временный файл для PDF
            temp_pdf = io.BytesIO()
            
            # Создаем документ
            doc = SimpleDocTemplate(temp_pdf, pagesize=letter, 
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            # Стили
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle('CustomTitle', 
                                       parent=styles['Heading1'],
                                       fontSize=16, 
                                       alignment=1,
                                       spaceAfter=30)
            
            heading_style = ParagraphStyle('CustomHeading',
                                         parent=styles['Heading2'],
                                         fontSize=14,
                                         spaceAfter=12)
            
            # Содержимое документа
            story = []
            
            # Заголовок
            story.append(Paragraph(f"Чекпоинт: {game.title}", title_style))
            story.append(Spacer(1, 12))
            
            # Описание игры
            story.append(Paragraph("Описание игры:", heading_style))
            story.append(Paragraph(game.description, styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Теги
            if game.tags:
                story.append(Paragraph("Теги:", heading_style))
                story.append(Paragraph(", ".join(game.tags), styles['Normal']))
                story.append(Spacer(1, 12))
            
            # Персонажи
            story.append(Paragraph("Персонажи:", heading_style))
            for char in game.characters:
                story.append(Paragraph(f"<b>{char.name}</b>", styles['Normal']))
                story.append(Paragraph(f"Описание: {char.description}", styles['Normal']))
                story.append(Paragraph(f"Черты: {char.traits}", styles['Normal']))
                story.append(Paragraph(f"Предыстория: {char.backstory}", styles['Normal']))
                if char.current_state:
                    story.append(Paragraph(f"Текущее состояние: {char.current_state}", styles['Normal']))
                story.append(Spacer(1, 8))
            
            # Последние сообщения
            story.append(Paragraph("Последние события:", heading_style))
            for msg in recent_messages[-10:]:  # Последние 10 сообщений
                if msg["role"] == "user":
                    story.append(Paragraph(f"<b>Пользователь:</b> {msg['content']}", styles['Normal']))
                else:
                    story.append(Paragraph(f"<b>Нейкон:</b> {msg['content']}", styles['Normal']))
                story.append(Spacer(1, 6))
            
            # Генерируем PDF
            doc.build(story)
            
            # Возвращаем содержимое
            temp_pdf.seek(0)
            return temp_pdf.getvalue()
            
        except ImportError:
            logger.error("Для создания PDF нужна библиотека reportlab")
            # Создаем простой текстовый файл
            content = f"Чекпоинт: {game.title}\n\n"
            content += f"Описание: {game.description}\n\n"
            if game.tags:
                content += f"Теги: {', '.join(game.tags)}\n\n"
            
            content += "Персонажи:\n"
            for char in game.characters:
                content += f"\n{char.name}:\n"
                content += f"  Описание: {char.description}\n"
                content += f"  Черты: {char.traits}\n"
                content += f"  Предыстория: {char.backstory}\n"
                if char.current_state:
                    content += f"  Текущее состояние: {char.current_state}\n"
            
            content += "\nПоследние события:\n"
            for msg in recent_messages[-10:]:
                if msg["role"] == "user":
                    content += f"Пользователь: {msg['content']}\n"
                else:
                    content += f"Нейкон: {msg['content']}\n"
            
            return content.encode('utf-8')
        except Exception as e:
            logger.error(f"Ошибка создания чекпоинта: {e}")
            return None
    
    def get_user_session(self, user_id: int) -> Dict:
        """Получение или создание сессии пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'chat_history': [],
                'current_game': None,
                'last_activity': datetime.now(),
                'creating_new_game': False,
                'new_game_data': {},
                'character_creation_step': 0
            }
        return self.user_sessions[user_id]

    def get_active_game(self, user_id: int) -> Optional[RoleplayGame]:
        """Получение активной игры пользователя"""
        if user_id not in self.saved_games:
            return None
        
        for game in self.saved_games[user_id]:
            if game.is_active:
                return game
        return None

    def set_active_game(self, user_id: int, game_id: str):
        """Установка активной игры"""
        if user_id not in self.saved_games:
            return False
        
        # Деактивируем все игры
        for game in self.saved_games[user_id]:
            game.is_active = False
        
        # Активируем нужную игру
        for game in self.saved_games[user_id]:
            if game.game_id == game_id:
                game.is_active = True
                return True
        return False
    
    def send_message(self, chat_id: int, text: str, reply_markup=None):
        """Отправка сообщения через Telegram API с поддержкой длинных сообщений"""
        # Максимальная длина сообщения в Telegram
        MAX_MESSAGE_LENGTH = 4096
        
        if len(text) <= MAX_MESSAGE_LENGTH:
            # Обычное сообщение
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
        else:
            # Разбиваем длинное сообщение на части через ИИ
            parts = self.split_message_with_ai(text, MAX_MESSAGE_LENGTH)
            responses = []
            
            for i, part in enumerate(parts):
                # Кнопки добавляем только к последней части
                markup = reply_markup if i == len(parts) - 1 else None
                
                url = f"{self.base_url}{self.telegram_token}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': part,
                    'parse_mode': 'Markdown'
                }
                if markup:
                    data['reply_markup'] = json.dumps(markup)
                
                try:
                    response = requests.post(url, json=data)
                    responses.append(response.json())
                    # Небольшая задержка между сообщениями
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Ошибка отправки части сообщения: {e}")
            
            return responses
    
    def split_long_message(self, text: str, max_length: int) -> List[str]:
        """Разбивает длинное сообщение на части"""
        if len(text) <= max_length:
            return [text]
        
        parts = []
        current_part = ""
        
        # Разбиваем по абзацам
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # Если даже один абзац слишком длинный
            if len(paragraph) > max_length:
                # Если уже есть накопленный текст, добавляем его
                if current_part:
                    parts.append(current_part.strip())
                    current_part = ""
                
                # Разбиваем длинный абзац по предложениям
                sentences = paragraph.split('. ')
                temp_part = ""
                
                for sentence in sentences:
                    if len(temp_part + sentence + '. ') <= max_length:
                        temp_part += sentence + '. '
                    else:
                        if temp_part:
                            parts.append(temp_part.strip())
                        temp_part = sentence + '. '
                
                if temp_part:
                    current_part = temp_part
            else:
                # Проверяем, поместится ли абзац в текущую часть
                if len(current_part + paragraph + '\n\n') <= max_length:
                    current_part += paragraph + '\n\n'
                else:
                    # Добавляем накопленную часть и начинаем новую
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
        
        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    def generate_with_files(self, prompt: str, file_uris: List[str]) -> str:
        """Генерация ответа с подключенными файлами"""
        self.increment_counter('total_requests')
        
        try:
            # Создаем части для контента
            parts = [{"text": prompt}]
            # Добавляем файлы
            for file_uri in file_uris:
                parts.append({
                    "file_data": {
                        "file_uri": file_uri
                    }
                })
            # Создаем контент
            contents = [{"parts": parts}]
            # Отправляем запрос
            response = self.model.generate_content(contents)
            self.increment_counter('successful_requests')
            return response.text.strip()
        except Exception as e:
            logger.error(f"Ошибка генерации с файлами: {e}")
            self.increment_counter('failed_requests')
            self.update_system_status('last_error', f"Генерация с файлами: {e}")
            return f"Ошибка при обработке запроса: {e}"
    
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
    
    def handle_start_command(self, chat_id: int, user_id: int, user_name: str):
        """Обработка команды /start"""
        # Проверяем наличие сохраненных игр
        saved_games = self.saved_games.get(user_id, [])
        
        welcome_text = f"""
🎮 Добро пожаловать в "Хроники Нейкона", {user_name}!

Я — Нейкон, ваш ИИ-Мастер Игры для ролевых игр с продвинутой системой памяти.

📋 Доступные команды:
/start - Главное меню
/new - Новая ролевая игра
/games - Список сохраненных игр
/status - Состояние системы
/help - Помощь

💾 **Новая система памяти:**
- Все ролевые игры сохраняются автоматически
- Каждая игра имеет полный чат-лог и чекпоинты
- Можно переключаться между разными ролевыми играми
        """
        
        keyboard_buttons = [
            [{'text': '🎮 Новая игра', 'callback_data': 'new_game'}]
        ]
        
        if saved_games:
            keyboard_buttons.append([{'text': '📚 Мои игры', 'callback_data': 'my_games'}])
        
        keyboard_buttons.append([{'text': '❓ Помощь', 'callback_data': 'help'}])
        keyboard_buttons.append([{'text': '🤖 Статус системы', 'callback_data': 'status'}])
        
        keyboard = {'inline_keyboard': keyboard_buttons}
        
        self.send_message(chat_id, welcome_text, keyboard)
    
    def handle_help_command(self, chat_id: int):
        """Обработка команды /help"""
        help_text = """
🎮 **Хроники Нейкона - Продвинутая ролевая система**

**Основные команды:**
/start - Главное меню
/new - Создать новую ролевую игру
/games - Список сохраненных игр
/memory - Память активной игры
/status - Состояние системы
/help - Эта справка

**🎲 Создание ролевой игры:**
1. Выберите количество персонажей (1-5)
2. Опишите каждого персонажа детально
3. Задайте мир и историю
4. Добавьте теги для жанра
5. Начинайте играть!

**💾 Продвинутая система памяти:**
- Каждая игра имеет **2 файла памяти**:
  📚 **Чат-лог** - полная история всех событий
  💾 **Чекпоинт** - текущее состояние персонажей
- Все файлы сохраняются в Google Files API
- Нейкон всегда помнит весь контекст игры
- Можно переключаться между играми

**📄 Загрузка PDF документов:**
- Поддерживаются файлы до 20MB
- PDF автоматически интегрируется в память игры
- Файлы с "chat" или "log" → чат-лог
- Остальные файлы → чекпоинт
- Документы доступны через весь диалог

**🎮 Управление играми:**
- **Сохранение**: завершить текущую игру и сохранить
- **Загрузка**: продолжить любую сохраненную игру
- **Переключение**: работать с несколькими играми
- Все персонажи и события сохраняются

**🤖 Система мониторинга:**
- /status - просмотр состояния системы
- Отслеживание подключений к API
- Статистика запросов и ошибок
- Мониторинг загруженных файлов и созданных игр

**Примеры игр:**
- 🏰 Фэнтези: эльфы, драконы, магия
- 🚀 Фантастика: космос, ИИ, будущее
- 🕵️ Детектив: расследования, тайны
- 🏴‍☠️ Приключения: пираты, сокровища

**Технические особенности:**
- Использует Gemini 2.5 Pro
- Память через Google Files API
- Автоматическое создание PDF
- Поддержка множественных персонажей
- Система мониторинга состояния

Создайте свою первую игру командой /new! 🎲
        """
        self.send_message(chat_id, help_text)
    
    def handle_new_command(self, chat_id: int, user_id: int):
        """Обработка команды /new"""
        session = self.get_user_session(user_id)
        
        # Начинаем создание новой игры
        session['creating_new_game'] = True
        session['new_game_data'] = {}
        session['character_creation_step'] = 0
        
        message = """
🎮 **Создание новой ролевой игры**

Сначала определимся с количеством главных персонажей:

**Выберите один из вариантов:**
        """
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '👤 Один персонаж', 'callback_data': 'characters_1'}],
                [{'text': '👥 Несколько персонажей', 'callback_data': 'characters_multiple'}]
            ]
        }
        
        self.send_message(chat_id, message, keyboard)
    
    def handle_characters_count(self, chat_id: int, user_id: int, count: str):
        """Обработка выбора количества персонажей"""
        session = self.get_user_session(user_id)
        
        if count == "1":
            session['new_game_data']['character_count'] = 1
            self.ask_character_info(chat_id, user_id, 1)
        else:
            message = """
👥 **Несколько персонажей**

Укажите точное количество главных персонажей (от 2 до 5):
            """
            self.send_message(chat_id, message)
            session['new_game_data']['waiting_for_count'] = True
    
    def create_game_from_document(self, chat_id: int, user_id: int, document_uri: str, document_name: str):
        """Создание игры на основе загруженного документа"""
        try:
            self.send_message(chat_id, "🎮 **Создаю игру на основе документа...**\n\nАнализирую содержимое документа и создаю ролевую игру.")
            self.send_chat_action(chat_id, "typing")
            
            # Формируем промпт для анализа документа и создания игры
            analysis_prompt = f"""
{self.system_prompt}

ЗАДАЧА: Проанализируй загруженный документ "{document_name}" и автоматически создай на его основе ролевую игру.

ИНСТРУКЦИИ:
1. Внимательно изучи содержимое документа
2. Определи жанр и сеттинг на основе содержимого
3. Извлеки или создай персонажей (1-3 главных героя)
4. Создай захватывающую начальную сцену
5. Определи основной конфликт или цель

ФОРМАТ ОТВЕТА:
🎮 **Ролевая игра создана: [Название]**

**📖 Жанр и сеттинг:**
[Описание мира и жанра на основе документа]

**👥 Главные персонажи:**
- **[Имя 1]**: [Описание, роль, особенности]
- **[Имя 2]**: [Описание, роль, особенности]
[При необходимости добавь больше персонажей]

**🎯 Основная цель/конфликт:**
[Главная задача или проблема, которую нужно решить]

**🌟 Начальная сцена:**
[Подробное описание начальной ситуации, где находятся персонажи, что происходит, создай атмосферу и вовлеки в игру]

**📋 Следующие действия:**
Теперь ты можешь описать действия своего персонажа или задать вопросы о мире!

Создай интересную и захватывающую игру, используя ВСЕ детали из документа!
            """
            
            # Отправляем запрос с документом
            response = self.generate_with_files(analysis_prompt, [document_uri])
            
            # Добавляем задержку
            time.sleep(3)
            
            # Создаем объект игры на основе ответа
            game_id = f"doc_game_{user_id}_{int(time.time())}"
            
            # Извлекаем название игры из ответа ИИ
            game_title = "Ролевая игра на основе документа"
            if "создана:" in response:
                title_part = response.split("создана:")[1].split("**")[0].strip()
                if title_part:
                    game_title = title_part
            
            # Создаем игру
            game = RoleplayGame(
                game_id, 
                game_title, 
                f"Игра создана на основе документа: {document_name}", 
                ["документ", "автоматическая генерация"]
            )
            
            # Добавляем базового персонажа (ИИ определит детали из ответа)
            base_character = Character(
                "Главный герой",
                "Персонаж, созданный на основе документа",
                "Определяется по ходу игры",
                "История из загруженного документа"
            )
            game.characters.append(base_character)
            
            # Устанавливаем документ как чекпоинт
            game.checkpoint_file_uri = document_uri
            
            # Деактивируем другие игры и активируем новую
            if user_id not in self.saved_games:
                self.saved_games[user_id] = []
            
            for existing_game in self.saved_games[user_id]:
                existing_game.is_active = False
            
            game.is_active = True
            self.saved_games[user_id].append(game)
            
            # Сохраняем игры
            self.save_games_to_file()
            
            # Обновляем статистику
            self.increment_counter('games_created')
            
            # Очищаем данные загруженного документа и историю
            session = self.get_user_session(user_id)
            session['uploaded_document_uri'] = None
            session['uploaded_document_name'] = None
            session['chat_history'] = []
            
            # Добавляем начальное сообщение в историю
            session['chat_history'].append({"role": "assistant", "content": response})
            
            # Отправляем ответ с информацией о созданной игре
            final_response = f"""
✅ **Загрузка завершена!**

📄 **Документ "{document_name}" успешно проанализирован**
🎮 **Ролевая игра автоматически создана и запущена**
💾 **Документ сохранен в памяти игры**

---

{response}
            """
            
            self.send_message(chat_id, final_response)
            
        except Exception as e:
            logger.error(f"Ошибка создания игры из документа: {e}")
            self.send_message(chat_id, f"❌ Ошибка создания игры: {e}\n\nПопробуйте создать игру вручную командой /new")
    
    def ask_character_info(self, chat_id: int, user_id: int, character_number: int):
        """Запрос информации о персонаже"""
        session = self.get_user_session(user_id)
        total_chars = session['new_game_data'].get('character_count', 1)
        
        if character_number == 1:
            session['new_game_data']['characters'] = []
        
        message = f"""
👤 **Персонаж {character_number}/{total_chars}**

Пожалуйста, опишите своего персонажа по следующему шаблону:

**Имя:** [Имя персонажа]
**Описание:** [Внешность, возраст, пол]
**Черты характера:** [Личность, особенности]
**Предыстория:** [История персонажа, откуда он]

Пример:
**Имя:** Эльриэль Звездокрылая
**Описание:** Молодая эльфийка 120 лет, высокая и грациозная, с серебристыми волосами
**Черты характера:** Мудрая, но импульсивная, любит природу и магию
**Предыстория:** Выросла в лесном королевстве, изучает древнюю магию
        """
        
        session['character_creation_step'] = character_number
        self.send_message(chat_id, message)
    
    def parse_character_info(self, text: str) -> Optional[Dict]:
        """Парсинг информации о персонаже"""
        try:
            lines = text.strip().split('\n')
            character = {'name': '', 'description': '', 'traits': '', 'backstory': ''}
            
            current_field = None
            for line in lines:
                line = line.strip()
                if line.startswith('**Имя:**'):
                    character['name'] = line.replace('**Имя:**', '').strip()
                    current_field = 'name'
                elif line.startswith('**Описание:**'):
                    character['description'] = line.replace('**Описание:**', '').strip()
                    current_field = 'description'
                elif line.startswith('**Черты характера:**') or line.startswith('**Черты:**'):
                    character['traits'] = line.replace('**Черты характера:**', '').replace('**Черты:**', '').strip()
                    current_field = 'traits'
                elif line.startswith('**Предыстория:**'):
                    character['backstory'] = line.replace('**Предыстория:**', '').strip()
                    current_field = 'backstory'
                elif line and current_field and not line.startswith('**'):
                    # Продолжение текущего поля
                    character[current_field] += ' ' + line
            
            # Проверяем обязательные поля
            if character['name'] and character['description']:
                return character
            return None
            
        except Exception as e:
            logger.error(f"Ошибка парсинга персонажа: {e}")
            return None
    
    def ask_game_description(self, chat_id: int, user_id: int):
        """Запрос описания игры"""
        session = self.get_user_session(user_id)
        character_count = session['new_game_data'].get('character_count', 1)
        
        characters_text = ""
        for i, char in enumerate(session['new_game_data']['characters'], 1):
            characters_text += f"\n{i}. **{char['name']}** - {char['description']}"
        
        message = f"""
🎲 **Финальный этап создания игры**

Ваши персонажи:{characters_text}

Теперь опишите:

**1. Общее описание истории и мира:**
[Опишите сеттинг, основную историю, конфликт]

**2. Теги игры:**
[Укажите жанр и ключевые слова через запятую]

Пример:
**Описание:** Группа авантюристов исследует заброшенный замок, полный магических ловушек и древних секретов. Их цель - найти артефакт, способный остановить надвигающуюся войну.

**Теги:** фэнтези, приключения, магия, подземелья, артефакт
        """
        
        self.send_message(chat_id, message)
        session['new_game_data']['waiting_for_description'] = True
    
    def create_new_game(self, chat_id: int, user_id: int, description: str, tags: str):
        """Создание новой игры"""
        session = self.get_user_session(user_id)
        
        try:
            # Парсим описание и теги
            lines = description.strip().split('\n')
            game_description = ""
            game_tags = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('**Описание:**') or line.startswith('**1.'):
                    game_description = line.split(':', 1)[-1].strip()
                elif line.startswith('**Теги:**') or line.startswith('**2.'):
                    tags_text = line.split(':', 1)[-1].strip()
                    game_tags = [tag.strip() for tag in tags_text.split(',')]
                elif game_description and not line.startswith('**'):
                    game_description += ' ' + line
            
            if not game_description:
                game_description = description
            if not game_tags:
                game_tags = tags.split(',') if tags else ['ролевая игра']
            
            # Создаем уникальный ID игры
            game_id = f"game_{user_id}_{int(time.time())}"
            
            # Создаем игру
            characters = session['new_game_data']['characters']
            char_names = [char['name'] for char in characters]
            game_title = f"Приключения {', '.join(char_names)}"
            
            game = RoleplayGame(game_id, game_title, game_description, game_tags)
            
            # Добавляем персонажей
            for char_data in characters:
                character = Character(
                    char_data['name'],
                    char_data['description'],
                    char_data['traits'],
                    char_data['backstory']
                )
                game.characters.append(character)
            
            # Деактивируем другие игры
            if user_id not in self.saved_games:
                self.saved_games[user_id] = []
            
            for existing_game in self.saved_games[user_id]:
                existing_game.is_active = False
            
            # Активируем новую игру
            game.is_active = True
            self.saved_games[user_id].append(game)
            
            # Создаем начальный чекпоинт
            initial_messages = [{"role": "system", "content": f"Создана новая игра: {game_title}"}]
            checkpoint_pdf = self.create_checkpoint_pdf(game, initial_messages)
            
            if checkpoint_pdf:
                checkpoint_uri = self.upload_file_to_google(
                    checkpoint_pdf, 
                    f"checkpoint_{game_id}.pdf"
                )
                game.checkpoint_file_uri = checkpoint_uri
            
            # Сохраняем игры
            self.save_games_to_file()
            
            # Обновляем статистику
            self.increment_counter('games_created')
            
            # Очищаем данные создания
            session['creating_new_game'] = False
            session['new_game_data'] = {}
            session['character_creation_step'] = 0
            session['chat_history'] = []
            
            # Генерируем начальное сообщение
            self.start_roleplay(chat_id, user_id, game)
            
        except Exception as e:
            logger.error(f"Ошибка создания игры: {e}")
            self.send_message(chat_id, f"❌ Ошибка создания игры: {e}")
    
    def start_roleplay(self, chat_id: int, user_id: int, game: RoleplayGame):
        """Начало ролевой игры"""
        try:
            # Формируем контекст для начала игры
            context = f"""{self.system_prompt}

НОВАЯ РОЛЕВАЯ ИГРА: {game.title}

ОПИСАНИЕ МИРА И ИСТОРИИ:
{game.description}

ПЕРСОНАЖИ:"""
            
            for char in game.characters:
                context += f"""

{char.name}:
- Описание: {char.description}
- Черты характера: {char.traits}
- Предыстория: {char.backstory}"""
            
            context += f"""

ТЕГИ: {', '.join(game.tags)}

Нейкон, начни эту ролевую игру! Создай захватывающую начальную сцену, которая введет персонажей в мир и покажет основной конфликт или задачу. Обращайся к персонажам по именам и учитывай их характеристики."""
            
            # Если есть чекпоинт, используем его
            file_uris = []
            if game.checkpoint_file_uri:
                file_uris.append(game.checkpoint_file_uri)
            
            if file_uris:
                response = self.generate_with_files(context, file_uris)
            else:
                response = self.model.generate_content(context).text.strip()
            
            # Добавляем задержку
            time.sleep(5)
            
            # Сохраняем в историю
            session = self.get_user_session(user_id)
            session['chat_history'].append({"role": "assistant", "content": response})
            
            # Отправляем сообщение
            success_message = f"""
✅ **Игра "{game.title}" создана и запущена!**

🎮 **Ваши персонажи:** {', '.join([char.name for char in game.characters])}
🏷️ **Теги:** {', '.join(game.tags)}

---
"""
            
            self.send_message(chat_id, success_message + response)
            
        except Exception as e:
            logger.error(f"Ошибка начала игры: {e}")
            self.send_message(chat_id, f"❌ Ошибка начала игры: {e}")
    
    def handle_games_command(self, chat_id: int, user_id: int):
        """Обработка команды /games"""
        saved_games = self.saved_games.get(user_id, [])
        
        if not saved_games:
            message = """
📚 **Список игр пуст**

У вас пока нет сохраненных ролевых игр. Создайте новую игру командой /new
            """
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Создать новую игру', 'callback_data': 'new_game'}]
                ]
            }
            self.send_message(chat_id, message, keyboard)
            return
        
        message = "📚 **Ваши ролевые игры:**\n\n"
        keyboard_buttons = []
        
        for i, game in enumerate(saved_games):
            status = "🟢 Активна" if game.is_active else "⚪ Неактивна"
            characters = ', '.join([char.name for char in game.characters])
            
            message += f"""
**{i+1}. {game.title}** {status}
👥 Персонажи: {characters}
🏷️ Теги: {', '.join(game.tags)}
📅 Создана: {game.created_at.strftime('%d.%m.%Y')}
📝 Описание: {game.description[:100]}{'...' if len(game.description) > 100 else ''}

"""
            
            # Добавляем кнопки для игры
            if game.is_active:
                keyboard_buttons.append([
                    {'text': f'💾 Сохранить "{game.title}"', 'callback_data': f'save_game_{game.game_id}'}
                ])
            else:
                keyboard_buttons.append([
                    {'text': f'▶️ Продолжить "{game.title}"', 'callback_data': f'load_game_{game.game_id}'}
                ])
        
        keyboard_buttons.append([{'text': '🎮 Новая игра', 'callback_data': 'new_game'}])
        
        keyboard = {'inline_keyboard': keyboard_buttons}
        self.send_message(chat_id, message, keyboard)
    
    def save_current_game(self, chat_id: int, user_id: int, game_id: str):
        """Сохранение текущей игры"""
        try:
            session = self.get_user_session(user_id)
            game = None
            
            # Находим игру
            for g in self.saved_games.get(user_id, []):
                if g.game_id == game_id:
                    game = g
                    break
            
            if not game:
                self.send_message(chat_id, "❌ Игра не найдена")
                return
            
            # Обновляем чекпоинт и чат-лог
            chat_history = session.get('chat_history', [])
            
            if chat_history:
                # Создаем полный чат-лог
                chat_log_pdf = self.create_chat_log_pdf(chat_history, game.title)
                if chat_log_pdf:
                    log_uri = self.upload_file_to_google(
                        chat_log_pdf,
                        f"chat_log_{game_id}_{int(time.time())}.pdf"
                    )
                    game.chat_log_file_uri = log_uri
                
                # Создаем чекпоинт
                checkpoint_pdf = self.create_checkpoint_pdf(game, chat_history)
                if checkpoint_pdf:
                    checkpoint_uri = self.upload_file_to_google(
                        checkpoint_pdf,
                        f"checkpoint_{game_id}_{int(time.time())}.pdf"
                    )
                    game.checkpoint_file_uri = checkpoint_uri
            
            # Деактивируем игру
            game.is_active = False
            game.last_updated = datetime.now()
            
            # Сохраняем в файл
            self.save_games_to_file()
            
            # Очищаем сессию
            session['chat_history'] = []
            
            self.send_message(chat_id, f"💾 Игра \"{game.title}\" сохранена! Все прогресс и персонажи сохранены в памяти.")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения игры: {e}")
            self.send_message(chat_id, f"❌ Ошибка сохранения: {e}")
    
    def load_game(self, chat_id: int, user_id: int, game_id: str):
        """Загрузка игры"""
        try:
            # Деактивируем текущие игры
            for game in self.saved_games.get(user_id, []):
                game.is_active = False
            
            # Активируем выбранную игру
            game = None
            for g in self.saved_games.get(user_id, []):
                if g.game_id == game_id:
                    game = g
                    game.is_active = True
                    break
            
            if not game:
                self.send_message(chat_id, "❌ Игра не найдена")
                return
                
            # Очищаем текущую сессию
            session = self.get_user_session(user_id)
            session['chat_history'] = []
            
            # Формируем приветственное сообщение с последними событиями
            characters = ', '.join([char.name for char in game.characters])
            
            # Получаем информацию о последних событиях из памяти
            last_events_info = ""
            if game.chat_log_file_uri or game.checkpoint_file_uri:
                last_events_prompt = f"""
Проанализируй память игры "{game.title}" и кратко расскажи о последних событиях (2-3 предложения). 
Что происходило в последний раз? Где находятся персонажи? Какая текущая ситуация?

Формат ответа: просто краткое описание ситуации без лишнего форматирования.
                """
                
                try:
                    file_uris = []
                    if game.chat_log_file_uri:
                        file_uris.append(game.chat_log_file_uri)
                    if game.checkpoint_file_uri:
                        file_uris.append(game.checkpoint_file_uri)
                    
                    if file_uris:
                        last_events = self.generate_with_files(last_events_prompt, file_uris)
                        last_events_info = f"\n\n📖 **Последние события:**\n{last_events}"
                        time.sleep(2)  # Задержка для API
                except Exception as e:
                    logger.error(f"Ошибка получения последних событий: {e}")
            
            message = f"""
🎮 **Игра "{game.title}" загружена!**

👥 **Персонажи:** {characters}
🏷️ **Теги:** {', '.join(game.tags)}
📅 **Последнее обновление:** {game.last_updated.strftime('%d.%m.%Y %H:%M')}

📝 **Описание:** {game.description}{last_events_info}

💾 **Память восстановлена** - вся история и состояние персонажей доступны!

Продолжайте свое приключение! 🎲
            """
            
            self.send_message(chat_id, message)
            
            # Сохраняем изменения
            self.save_games_to_file()
            
        except Exception as e:
            logger.error(f"Ошибка загрузки игры: {e}")
            self.send_message(chat_id, f"❌ Ошибка загрузки: {e}")

    def handle_memory_command(self, chat_id: int, user_id: int):
        """Обработка команды /memory"""
        active_game = self.get_active_game(user_id)
        
        if not active_game:
            self.send_message(chat_id, "💾 Нет активной игры. Загрузите игру из списка или создайте новую.")
            return
        
        message = f"""
💾 **Память активной игры: {active_game.title}**

👥 **Персонажи:**
"""
        
        for char in active_game.characters:
            message += f"""
**{char.name}**
- Описание: {char.description}
- Черты: {char.traits}
- Предыстория: {char.backstory}
"""
            if char.current_state:
                message += f"- Текущее состояние: {char.current_state}\n"
        
        message += f"""
🏷️ **Теги:** {', '.join(active_game.tags)}
📝 **Описание мира:** {active_game.description}

📄 **Файлы памяти:**
"""
        
        if active_game.chat_log_file_uri:
            message += "✅ Полный чат-лог сохранен\n"
        else:
            message += "❌ Чат-лог не создан\n"
            
        if active_game.checkpoint_file_uri:
            message += "✅ Чекпоинт сохранен\n"
        else:
            message += "❌ Чекпоинт не создан\n"
        
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
            # Проверяем, есть ли загруженный документ для автоматического создания игры
            session = self.get_user_session(user_id)
            if session.get('uploaded_document_uri') and session.get('uploaded_document_name'):
                self.create_game_from_document(chat_id, user_id, session['uploaded_document_uri'], session['uploaded_document_name'])
            else:
                self.handle_new_command(chat_id, user_id)
        elif callback_data == "help":
            self.handle_help_command(chat_id)
        elif callback_data == "my_games":
            self.handle_games_command(chat_id, user_id)
        elif callback_data == "characters_1":
            self.handle_characters_count(chat_id, user_id, "1")
        elif callback_data == "characters_multiple":
            self.handle_characters_count(chat_id, user_id, "multiple")
        elif callback_data.startswith("save_game_"):
            game_id = callback_data.replace("save_game_", "")
            self.save_current_game(chat_id, user_id, game_id)
        elif callback_data.startswith("load_game_"):
            game_id = callback_data.replace("load_game_", "")
            self.load_game(chat_id, user_id, game_id)
        elif callback_data == "status":
            self.handle_status_command(chat_id, user_id)
        elif callback_data == "status_detailed":
            self.send_status_message(chat_id, "detailed")
        elif callback_data == "status_refresh":
            self.send_status_message(chat_id, "general")
    
    def handle_photo(self, message):
        """Обработка загруженного изображения"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        
        self.send_message(chat_id, """
🖼️ **Изображения временно не поддерживаются**

В новой версии бота сосредоточены на:
- PDF документах для памяти игры
- Продвинутой системе персонажей
- Сохранении ролевых игр

Используйте PDF файлы для лучшей интеграции с системой памяти!
        """)
    
    def handle_document(self, message):
        """Обработка загруженного документа"""
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        user_name = message['from'].get('first_name', 'Пользователь')
        document = message['document']
        
        file_name = document.get('file_name', 'document')
        file_id = document['file_id']
        file_size = document.get('file_size', 0)
        
        # Проверяем размер файла (максимум 20MB)
        if file_size > 20 * 1024 * 1024:
            self.send_message(chat_id, "❌ Файл слишком большой. Максимальный размер: 20MB")
            return
        
        # Отправляем статус обработки
        self.send_message(chat_id, f"📄 Загружаю документ в память игры: {file_name}")
        self.send_chat_action(chat_id, "upload_document")
        
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
            
            # Загружаем файл в Google Files API (MIME-тип определится автоматически)
            file_uri = self.upload_file_to_google(file_content, file_name)
            
            if not file_uri:
                self.send_message(chat_id, "❌ Не удалось загрузить файл в память")
                return
            
            # Проверяем активную игру
            active_game = self.get_active_game(user_id)
            
            if not active_game:
                # Если нет активной игры, начинаем создание новой
                session = self.get_user_session(user_id)
                session['uploaded_document_uri'] = file_uri
                session['uploaded_document_name'] = file_name
                
                message = f"""
📄 **Документ "{file_name}" загружен в память!**

У вас нет активной ролевой игры. Хотите создать новую игру на основе этого документа?

Документ будет использован как основа для мира и истории.
                """
                
                keyboard = {
                    'inline_keyboard': [
                        [{'text': '🎮 Создать игру на основе документа', 'callback_data': 'new_game'}],
                        [{'text': '📚 Показать мои игры', 'callback_data': 'my_games'}]
                    ]
                }
                
                self.send_message(chat_id, message, keyboard)
                return
            
            # Если есть активная игра, добавляем документ в её память
            if file_name.lower().endswith('.pdf'):
                # Обновляем чат-лог или чекпоинт
                if 'chat' in file_name.lower() or 'log' in file_name.lower():
                    active_game.chat_log_file_uri = file_uri
                    message = f"📚 Документ \"{file_name}\" добавлен как чат-лог к игре \"{active_game.title}\""
                else:
                    active_game.checkpoint_file_uri = file_uri
                    message = f"💾 Документ \"{file_name}\" добавлен как чекпоинт к игре \"{active_game.title}\""
                
                # Сохраняем изменения
                self.save_games_to_file()
                
                self.send_message(chat_id, f"✅ {message}\n\nТеперь вся память игры доступна для ролевой игры!")
            else:
                self.send_message(chat_id, "⚠️ Рекомендуется использовать PDF файлы для лучшей совместимости с системой памяти.")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке документа: {e}")
            
            # Проверяем ошибку квоты
            if "429" in str(e) or "quota" in str(e).lower():
                self.send_message(chat_id, 
                    "⚠️ Превышен лимит запросов к Google API. Попробуйте через несколько минут.")
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
        
        # Обновляем статистику активных пользователей
        active_users = len([s for s in self.user_sessions.values() 
                          if (datetime.now() - s.get('last_activity', datetime.now())).seconds < 3600])
        self.update_system_status('active_users', active_users)
        
        # Проверяем, создается ли новая игра
        if session.get('creating_new_game'):
            self.handle_game_creation_message(chat_id, user_id, text)
            return
        
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
            
            # Получаем активную игру
            active_game = self.get_active_game(user_id)
            
            if not active_game:
                # Нет активной игры - предлагаем создать
                self.send_message(chat_id, 
                    "🎮 У вас нет активной ролевой игры. Создайте новую игру командой /new или выберите из сохраненных /games")
                return
            
            # Формируем контекст для ролевой игры
            context_text = f"{self.system_prompt}\n\n"
            context_text += f"АКТИВНАЯ ИГРА: {active_game.title}\n"
            context_text += f"ОПИСАНИЕ МИРА: {active_game.description}\n\n"
            
            # Добавляем информацию о персонажах
            context_text += "ПЕРСОНАЖИ:\n"
            for char in active_game.characters:
                context_text += f"- {char.name}: {char.description}\n"
                context_text += f"  Черты: {char.traits}\n"
                if char.current_state:
                    context_text += f"  Состояние: {char.current_state}\n"
            
            context_text += f"\nТЕГИ: {', '.join(active_game.tags)}\n\n"
            
            # Добавляем историю диалога
            context_text += "ИСТОРИЯ ДИАЛОГА:\n"
            for msg in session['chat_history'][:-5]:  # Старые сообщения
                if msg["role"] == "user":
                    context_text += f"Игрок: {msg['content']}\n"
                else:
                    context_text += f"Нейкон: {msg['content']}\n"
            
            # Последние 5 сообщений для контекста
            recent_messages = session['chat_history'][-5:]
            context_text += "\nПОСЛЕДНИЕ СОБЫТИЯ:\n"
            for msg in recent_messages[:-1]:
                if msg["role"] == "user":
                    context_text += f"Игрок: {msg['content']}\n"
                else:
                    context_text += f"Нейкон: {msg['content']}\n"
            
            # Текущее сообщение
            context_text += f"\nИгрок: {text}\n"
            context_text += "Нейкон:"
            
            # Собираем файлы памяти для подключения
            file_uris = []
            if active_game.chat_log_file_uri:
                file_uris.append(active_game.chat_log_file_uri)
            if active_game.checkpoint_file_uri:
                file_uris.append(active_game.checkpoint_file_uri)
            
            # Добавляем информацию о последних постах из памяти
            if active_game.chat_log_file_uri or active_game.checkpoint_file_uri:
                context_text += "\n💾 ПАМЯТЬ ИГРЫ: В памяти есть сохраненная история и состояние персонажей. Используй эту информацию для продолжения игры.\n"
            
            # Отправляем запрос с подключенными файлами памяти
            if file_uris:
                assistant_message = self.generate_with_files(context_text, file_uris)
            else:
                self.increment_counter('total_requests')
                try:
                    response = self.model.generate_content(context_text)
                    assistant_message = response.text.strip()
                    self.increment_counter('successful_requests')
                except Exception as e:
                    logger.error(f"Ошибка генерации: {e}")
                    self.increment_counter('failed_requests')
                    self.update_system_status('last_error', f"Генерация: {e}")
                    assistant_message = f"❌ Ошибка при обработке запроса: {e}"
            
            # Добавляем задержку для экономии квоты
            time.sleep(3)
            
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
    
    def handle_game_creation_message(self, chat_id: int, user_id: int, text: str):
        """Обработка сообщений во время создания игры"""
        session = self.get_user_session(user_id)
        
        # Ожидание количества персонажей
        if session['new_game_data'].get('waiting_for_count'):
            try:
                count = int(text.strip())
                if 2 <= count <= 20:
                    session['new_game_data']['character_count'] = count
                    session['new_game_data']['waiting_for_count'] = False
                    self.ask_character_info(chat_id, user_id, 1)
                else:
                    self.send_message(chat_id, "❌ Количество персонажей должно быть от 2 до 5. Попробуйте еще раз:")
            except ValueError:
                self.send_message(chat_id, "❌ Введите число от 2 до 5:")
            return
        
        # Создание персонажа
        if session['character_creation_step'] > 0:
            character_data = self.parse_character_info(text)
            if character_data:
                session['new_game_data']['characters'].append(character_data)
                current_step = session['character_creation_step']
                total_chars = session['new_game_data']['character_count']
                
                if current_step < total_chars:
                    # Переходим к следующему персонажу
                    self.ask_character_info(chat_id, user_id, current_step + 1)
                else:
                    # Все персонажи созданы, запрашиваем описание игры
                    self.ask_game_description(chat_id, user_id)
                    session['character_creation_step'] = 0
            else:
                self.send_message(chat_id, "❌ Не удалось распознать информацию о персонаже. Проверьте формат и попробуйте еще раз:")
            return
        
        # Ожидание описания игры
        if session['new_game_data'].get('waiting_for_description'):
            self.create_new_game(chat_id, user_id, text, "")
            return
    
    def process_update(self, update):
        """Обработка обновления"""
        if 'message' in update:
            message = update['message']
            text = message.get('text', '')
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            user_name = message['from'].get('first_name', 'Пользователь')
            
            # Проверяем наличие документа
            if 'document' in message:
                self.handle_document(message)
            # Проверяем наличие фото
            elif 'photo' in message:
                self.handle_photo(message)
            elif text.startswith('/start'):
                self.handle_start_command(chat_id, user_id, user_name)
            elif text.startswith('/help'):
                self.handle_help_command(chat_id)
            elif text.startswith('/new'):
                self.handle_new_command(chat_id, user_id)
            elif text.startswith('/games'):
                self.handle_games_command(chat_id, user_id)
            elif text.startswith('/memory'):
                self.handle_memory_command(chat_id, user_id)
            elif text.startswith('/status'):
                self.handle_status_command(chat_id, user_id)
            else:
                self.handle_message(message)
        
        elif 'callback_query' in update:
            self.handle_callback_query(update['callback_query'])
    
    def run(self):
        """Запуск бота"""
        if not self.telegram_token:
            logger.error("Telegram токен не установлен!")
            self.update_system_status('telegram_connected', False)
            return
        
        logger.info("Бот запущен!")
        self.update_system_status('telegram_connected', True)
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
                self.update_system_status('bot_started', False)
                break
            except Exception as e:
                logger.error(f"Ошибка в главном цикле: {e}")
                self.update_system_status('last_error', f"Главный цикл: {e}")
                continue
    
    def update_system_status(self, key: str, value):
        """Обновление показателя состояния системы"""
        self.system_status[key] = value
        logger.info(f"Статус обновлен: {key} = {value}")
    
    def increment_counter(self, counter_name: str):
        """Увеличение счетчика"""
        if counter_name in self.system_status:
            self.system_status[counter_name] += 1
    
    def get_system_status(self) -> Dict:
        """Получение текущего состояния системы"""
        uptime = None
        if self.system_status['start_time']:
            uptime = datetime.now() - self.system_status['start_time']
        
        return {
            **self.system_status,
            'uptime': str(uptime) if uptime else None,
            'success_rate': (self.system_status['successful_requests'] / max(self.system_status['total_requests'], 1)) * 100
        }
    
    def send_status_message(self, chat_id: int, status_type: str = "general"):
        """Отправка сообщения о состоянии системы"""
        status = self.get_system_status()
        
        if status_type == "detailed":
            message = f"""
🤖 **Состояние системы Нейкона**

📊 **Основные показатели:**
• Бот запущен: {'✅' if status['bot_started'] else '❌'}
• Gemini подключен: {'✅' if status['gemini_connected'] else '❌'}
• Telegram подключен: {'✅' if status['telegram_connected'] else '❌'}

📈 **Статистика:**
• Всего запросов: {status['total_requests']}
• Успешных: {status['successful_requests']}
• Ошибок: {status['failed_requests']}
• Процент успеха: {status['success_rate']:.1f}%

📁 **Файлы и игры:**
• Загружено файлов: {status['files_uploaded']}
• Создано игр: {status['games_created']}
• Активных пользователей: {status['active_users']}

⏱️ **Время работы:** {status['uptime']}

🔧 **Последняя ошибка:** {status['last_error'] or 'Нет'}
            """
        else:
            # Краткий статус
            message = f"""
🤖 **Статус Нейкона**

{'✅' if status['bot_started'] else '❌'} Бот: {'Работает' if status['bot_started'] else 'Остановлен'}
{'✅' if status['gemini_connected'] else '❌'} ИИ: {'Подключен' if status['gemini_connected'] else 'Отключен'}
{'✅' if status['telegram_connected'] else '❌'} Telegram: {'Подключен' if status['telegram_connected'] else 'Отключен'}

📊 Запросов: {status['total_requests']} | Успех: {status['success_rate']:.1f}%
📁 Файлов: {status['files_uploaded']} | Игр: {status['games_created']}
            """
        
        self.send_message(chat_id, message)
    
    def handle_status_command(self, chat_id: int, user_id: int):
        """Обработка команды /status"""
        keyboard = {
            'inline_keyboard': [
                [{'text': '📊 Подробная статистика', 'callback_data': 'status_detailed'}],
                [{'text': '🔄 Обновить', 'callback_data': 'status_refresh'}],
                [{'text': '🏠 Главное меню', 'callback_data': 'start'}]
            ]
        }
        
        self.send_status_message(chat_id, "general")
        self.send_message(chat_id, "Выберите тип отчета:", keyboard)
    
    def split_message_with_ai(self, text: str, max_length: int = 4000) -> List[str]:
        """Разбиение длинного сообщения на части через ИИ"""
        if len(text) <= max_length:
            return [text]
        
        try:
            # Формируем промпт для ИИ
            split_prompt = f"""
Твоя задача — взять предоставленный ниже текст и разделить его на логические части, пригодные для отправки отдельными сообщениями в Telegram (лимит ~{max_length} символов). 

Вставляй разделитель |||---||| МЕЖДУ частями. Не вставляй его в начале или в конце. 
Сохраняй исходное форматирование, особенно блоки кода и markdown. 
Разделяй по абзацам или смысловым блокам.

Текст:

{text}
            """
            
            # Отправляем запрос к ИИ
            self.increment_counter('total_requests')
            try:
                response = self.model.generate_content(split_prompt)
                result = response.text.strip()
                self.increment_counter('successful_requests')
                
                # Разбиваем по разделителю
                if "|||---|||" in result:
                    parts = result.split("|||---|||")
                    # Очищаем части от лишних пробелов
                    parts = [part.strip() for part in parts if part.strip()]
                    return parts
                else:
                    # Если ИИ не использовал разделитель, разбиваем вручную
                    return self.split_long_message(text, max_length)
                    
            except Exception as e:
                logger.error(f"Ошибка разбиения через ИИ: {e}")
                self.increment_counter('failed_requests')
                self.update_system_status('last_error', f"Разбиение через ИИ: {e}")
                # Возвращаемся к ручному разбиению
                return self.split_long_message(text, max_length)
                
        except Exception as e:
            logger.error(f"Ошибка в split_message_with_ai: {e}")
            return self.split_long_message(text, max_length)

def main():
    """Главная функция"""
    bot = SimpleTelegramBot()
    bot.run()

if __name__ == "__main__":
    main() 