# Исправление ошибки BytesIO

## Проблема
```
ERROR - Ошибка при обработке документа: Could not create `Blob`, expected `Blob`, `dict` or an `Image` type(`PIL.Image.Image` or `IPython.display.Image`).
Got a: <class '_io.BytesIO'>
```

## Причина
Gemini API не принимает объекты `BytesIO` напрямую. Нужно использовать правильные типы данных.

## Решение

### Для документов
```python
# ❌ Неправильно
file_bytes = io.BytesIO(file_content)
response = self.model.generate_content([context_text, file_bytes])

# ✅ Правильно
response = self.model.generate_content(context_text)
```

### Для изображений
```python
# ✅ Правильно
image = Image.open(io.BytesIO(file_content))
response = vision_model.generate_content([context_text, image])
```

## Типы данных для Gemini API

### Поддерживаемые типы:
- `str` - Текст
- `PIL.Image.Image` - Изображения
- `dict` - Структурированные данные
- `Blob` - Бинарные данные (специальный формат)

### Не поддерживаются:
- `BytesIO` - Потоки байтов
- `bytes` - Сырые байты
- `file` - Файловые объекты

## Обработка ошибок
```python
if "Blob" in str(e) or "BytesIO" in str(e):
    self.send_message(chat_id, 
        "❌ Ошибка формата файла. Попробуйте другой документ.")
```

## Рекомендации

### Для документов:
1. Извлекайте текст из документа
2. Передавайте только текст в API
3. Сохраняйте файл в памяти для контекста

### Для изображений:
1. Используйте PIL.Image
2. Конвертируйте в правильный формат
3. Передавайте изображение напрямую

## Пример правильной обработки
```python
def handle_document(self, message):
    # Извлекаем текст
    document_text = self.extract_text_from_document(file_content, file_name)
    
    # Формируем контекст
    context_text = f"Документ: {document_text}"
    
    # Отправляем только текст
    response = self.model.generate_content(context_text)
    
    # Сохраняем файл в памяти
    self.save_file_to_memory(user_id, file_info, file_content, 'document')
``` 