"""
Проект: GigaChat_Content_Assistant
Версия: 1.0
Статус: Первая deploy версия

Модуль: src/services/llm_client.py
Разработчик: GEN AI + @AI_NeuroStaff / Dubinin Vladimir

LLM Client: Интеграция с GigaChat API
=====================================

Модуль отвечает за безопасное подключение к API GigaChat, обработку SSL-сертификатов,
загрузку промптов из файловой системы и потоковую/синхронную генерацию текста.

Основные возможности:
- Инициализация клиента GigaChat с умным фоллбэком (сначала ищет в st.secrets, затем в .env).
- Загрузка текстовых шаблонов (промптов) из защищенной системной директории.
- Потоковая генерация ответа (streaming) для создания эффекта "печати в реальном времени".
- Синхронная генерация ответа (ожидание полного ответа для работы с форматами JSON).
- Динамическое применение пользовательских настроек (модель и температура) из st.session_state.

Переменные:
- Внешние (состояние): 
    - st.secrets: хранит конфигурацию GigaChat (ключи, сертификаты, дефолтную модель).
    - st.session_state: хранит пользовательские настройки ('llm_model', 'llm_temperature').
- Внутренние (локальные/глобальные константы):
    - BASE_DIR: абсолютный путь к корневой директории проекта.
    - PROMPTS_DIR: абсолютный путь к директории с текстовыми шаблонами (assets/prompts).
    - DEFAULT_MODEL_PARAMS: словарь с дефолтными параметрами нейросети (temperature, max_tokens).

Функции:
- load_prompt(template_name: str) -> str
    Читает файл {template_name}.txt из папки промптов и возвращает его содержимое.
- _get_gigachat_client() -> GigaChat
    Фабрика для создания и настройки экземпляра клиента GigaChat с учетом сертификатов.
- generate_stream(prompt: str, temperature: Optional[float] = None) -> Generator[str, None, None]
    Отправляет запрос к LLM и возвращает ответ по частям (yield) для потоковой отрисовки.
- generate_sync(prompt: str, temperature: Optional[float] = None) -> str
    Обертка над generate_stream для получения всего текста единой строкой (блокирующий вызов).

Связи с другими модулями:
- src.services.content_gen.py: 
    Импортирует функции этого модуля (load_prompt, generate_stream, generate_sync) 
    для выполнения конкретных бизнес-задач генерации (план, посты, статьи).
- assets/prompts/*.txt:
    Источники текстовых инструкций (промптов) для нейросети.

Требуемые переменные окружения (в .env или .streamlit/secrets.toml):
- [gigachat] credentials: Ключ авторизации API (Base64).
- [gigachat] scope: Область действия API (обычно GIGACHAT_API_PERS).
- [gigachat] model: Используемая модель по умолчанию (GigaChat-2-Max).
- [gigachat] ca_bundle_file: Относительный путь к SSL-сертификату Минцифры (.cer).
"""

import os
import streamlit as st
from typing import Generator, Optional

# Безопасный импорт библиотеки GigaChat с понятной ошибкой для разработчика
try:
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole
except ImportError as e:
    raise ImportError("Библиотека 'gigachat' не найдена. Установите её: pip install gigachat") from e

# --- 1. БАЗОВЫЕ НАСТРОЙКИ ПУТЕЙ И ПАРАМЕТРОВ ---

# Вычисляем абсолютные пути к проекту и папке с промптами относительно текущего файла
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PROMPTS_DIR = os.path.join(BASE_DIR, "assets", "prompts")

# Базовые параметры генерации, используемые, если пользователь не задал свои
DEFAULT_MODEL_PARAMS = {
    "temperature": 0.7,
    "max_tokens": 4000,
}

# --- 2. РАБОТА С ПРОМПТАМИ ---

def load_prompt(template_name: str) -> str:
    """
    Загружает текстовый шаблон промпта из папки assets/prompts/.
    
    Args:
        template_name (str): Имя файла промпта без расширения (например, 'content_plan').
        
    Returns:
        str: Содержимое текстового файла.
        
    Raises:
        FileNotFoundError: Если указанный шаблон не существует.
    """
    file_path = os.path.join(PROMPTS_DIR, f"{template_name}.txt")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл шаблона промпта не найден: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# --- 3. КЛИЕНТ GIGACHAT ---

def _get_gigachat_client() -> GigaChat:
    """
    Инициализирует клиент GigaChat на основе конфигурации из st.secrets или .env.
    Автоматически подхватывает настройки модели из пользовательской сессии.
    
    Returns:
        GigaChat: Готовый к использованию клиент API.
        
    Raises:
        ValueError: Если не заданы учетные данные (credentials).
    """
    secrets = st.secrets.get("gigachat", {})
    
    # Пытаемся взять креды из конфига, иначе ищем в переменных ОС
    credentials = secrets.get("credentials") or os.getenv("GIGACHAT_CREDENTIALS")
    if not credentials:
        raise ValueError("Не настроены ключи доступа GigaChat.")

    scope = secrets.get("scope") or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    
    # Приоритет выбора модели: 1. Сессия пользователя -> 2. Secrets -> 3. .env -> 4. Хардкод
    model = st.session_state.get(
        "llm_model", 
        secrets.get("model") or os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max")
    )
    
    ca_bundle = secrets.get("ca_bundle_file") or os.getenv("GIGACHAT_CA_BUNDLE_FILE")
    
    # Обработка SSL-сертификатов (особенно актуально для корпоративных сетей и сертификатов Минцифры)
    if ca_bundle:
        ca_bundle = os.path.join(BASE_DIR, ca_bundle)
        verify_ssl = True
    else:
        verify_ssl = secrets.get("verify_ssl", False)

    return GigaChat(
        credentials=credentials,
        scope=scope,
        model=model,
        ca_bundle_file=ca_bundle if ca_bundle and os.path.exists(ca_bundle) else None,
        verify_ssl_certs=verify_ssl
    )

# --- 4. МЕТОДЫ ГЕНЕРАЦИИ ---

def generate_stream(prompt: str, temperature: Optional[float] = None) -> Generator[str, None, None]:
    """
    Генерирует ответ потоком (Streaming) по частям.
    Идеально подходит для UI, чтобы пользователь видел процесс написания текста.
    
    Args:
        prompt (str): Полный текст запроса к LLM.
        temperature (float, optional): Уровень креативности. Если None, берется из настроек.
        
    Yields:
        str: Фрагменты (чанки) сгенерированного текста по мере их поступления от API.
        
    Raises:
        RuntimeError: При возникновении сетевых ошибок или сбоев на стороне API.
    """
    # Определяем параметры креативности и модели
    temp = temperature or st.session_state.get("llm_temperature", DEFAULT_MODEL_PARAMS["temperature"])
    model_name = st.session_state.get("llm_model", "GigaChat-2-Max")

    try:
        with _get_gigachat_client() as giga:
            # Формируем структуру сообщения согласно документации GigaChat SDK
            messages = [Messages(role=MessagesRole.USER, content=prompt)]
            
            response_stream = giga.stream(Chat(
                messages=messages,
                temperature=temp,
                max_tokens=DEFAULT_MODEL_PARAMS["max_tokens"],
                model=model_name
            ))
            
            # Читаем поток и отдаем дельты текста "наверх"
            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
    except Exception as e:
        raise RuntimeError(f"Ошибка GigaChat API: {str(e)}") from e

def generate_sync(prompt: str, temperature: Optional[float] = None) -> str:
    """
    Синхронная генерация (блокирующий вызов).
    Собирает все потоковые фрагменты под капотом и возвращает финальную строку.
    Используется там, где нужен строгий машиночитаемый ответ (например, парсинг JSON).
    
    Args:
        prompt (str): Полный текст запроса к LLM.
        temperature (float, optional): Уровень креативности.
        
    Returns:
        str: Полностью сгенерированный текст.
    """
    # Превращаем генератор в список строк и склеиваем в один текст
    return "".join(list(generate_stream(prompt, temperature)))