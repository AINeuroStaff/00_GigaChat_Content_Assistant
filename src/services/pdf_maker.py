"""
Проект: GigaChat_Content_Assistant
Версия: 1.0
Статус: Первая deploy версия

Модуль: src/services/pdf_maker.py
Разработчик: GEN AI + @AI_NeuroStaff / Dubinin Vladimir

PDF Maker: Динамическая верстка документов
==========================================

Модуль отвечает за преобразование сгенерированного нейросетью Markdown-текста 
в профессионально отформатированные PDF-документы (Лид-магниты) "на лету" (в оперативной памяти).
Использует мощную библиотеку ReportLab Platypus.

Основные возможности:
- Загрузка и регистрация кастомных TTF шрифтов (Roboto), поддерживающих кириллицу.
- Умный "фоллбэк" шрифтов: безопасная обработка отсутствующих начертаний (например, курсива).
- Парсинг базового Markdown (заголовки #, жирный текст **, курсив *) и перевод в HTML-теги для ReportLab.
- Сборка документа в байтовый поток (BytesIO) без создания временных файлов на жестком диске.

Переменные:
- Глобальные константы:
    - BASE_DIR, FONTS_DIR: Абсолютные пути к системным папкам шрифтов.
    - FONT_FAMILY, FONT_REGULAR, FONT_BOLD: Названия и пути к файлам шрифтов.
    - _FONTS_REGISTERED: Флаг (Singleton) для предотвращения повторной регистрации шрифтов при генерации.

Функции:
- _setup_fonts() -> None
    (Внутренняя) Загружает TTF-шрифты в реестр ReportLab и прописывает правила отображения 
    (mapping) для жирного и курсивного начертаний.
- _md_to_html_tags(text: str) -> str
    (Внутренняя) Заменяет маркдаун-звездочки на HTML-теги <b> и <i>.
- generate_pdf(title: str, sections: List[str]) -> bytes
    Основная функция. Принимает заголовок и массив абзацев текста, применяет стили (Heading, Normal),
    собирает PDF в памяти и возвращает готовые байты для кнопки скачивания в Streamlit.

Связи с другими модулями:
- src.views.lead_tab: Вызывает generate_pdf для упаковки результатов работы генератора.
- assets/fonts/*.ttf: Требует наличия шрифтов Roboto для корректного отображения русского языка.
"""

import os
import re
from io import BytesIO
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# --- 1. ПУТИ И НАСТРОЙКИ ШРИФТОВ ---

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")

FONT_FAMILY = "Roboto"
FONT_REGULAR = os.path.join(FONTS_DIR, "Roboto-Regular.ttf")
FONT_BOLD = os.path.join(FONTS_DIR, "Roboto-Bold.ttf")

# Глобальный флаг, чтобы не регистрировать шрифты при каждом скачивании PDF
_FONTS_REGISTERED = False

def _setup_fonts():
    """
    Регистрирует шрифты в системе ReportLab.
    Обрабатывает фоллбэки (замены) на случай, если какой-то файл шрифта (например, italic) отсутствует.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED: return

    if not os.path.exists(FONT_REGULAR):
        raise FileNotFoundError(f"Не найден базовый шрифт {FONT_REGULAR}. Добавьте его в папку assets/fonts/.")
    
    # Регистрация обычного начертания
    pdfmetrics.registerFont(TTFont(f"{FONT_FAMILY}-Regular", FONT_REGULAR))

    # Регистрация жирного начертания (если файл существует)
    if os.path.exists(FONT_BOLD):
        pdfmetrics.registerFont(TTFont(f"{FONT_FAMILY}-Bold", FONT_BOLD))
        # Маппинг: 0=Обычный, 1=Жирный, 0=Курсив, 1=ЖирныйКурсив
        addMapping(FONT_FAMILY, 0, 0, f"{FONT_FAMILY}-Regular")
        addMapping(FONT_FAMILY, 1, 0, f"{FONT_FAMILY}-Bold")
        addMapping(FONT_FAMILY, 0, 1, f"{FONT_FAMILY}-Regular") # Фоллбэк курсива на обычный
        addMapping(FONT_FAMILY, 1, 1, f"{FONT_FAMILY}-Bold")    # Фоллбэк жирного курсива на жирный
    else:
        # Если жирного шрифта нет, мапим всё на обычный, чтобы избежать падения программы
        addMapping(FONT_FAMILY, 0, 0, f"{FONT_FAMILY}-Regular")
        addMapping(FONT_FAMILY, 1, 0, f"{FONT_FAMILY}-Regular")
        addMapping(FONT_FAMILY, 0, 1, f"{FONT_FAMILY}-Regular")
        addMapping(FONT_FAMILY, 1, 1, f"{FONT_FAMILY}-Regular")

    _FONTS_REGISTERED = True

# --- 2. УТИЛИТЫ ПАРСИНГА ---

def _md_to_html_tags(text: str) -> str:
    """Конвертирует базовые теги Markdown в теги XML/HTML, понятные ReportLab Platypus."""
    # Сначала заменяем двойные звездочки на <b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Затем одинарные звездочки на <i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    return text

# --- 3. ГЕНЕРАТОР PDF ---

def generate_pdf(title: str, sections: List[str]) -> bytes:
    """
    Создает PDF документ в оперативной памяти на основе массива текстов.
    
    Args:
        title (str): Главный заголовок документа (выводится по центру).
        sections (List[str]): Список абзацев или блоков текста.
        
    Returns:
        bytes: Бинарные данные PDF-файла (готовые для отдачи пользователю).
    """
    _setup_fonts()
    
    # Используем BytesIO, чтобы не сохранять промежуточные файлы на диск
    buffer = BytesIO()
    
    # Настройка параметров страницы (A4)
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50
    )

    # Получаем базовую таблицу стилей ReportLab и создаем свои кастомные стили
    styles = getSampleStyleSheet()
    font_reg = f"{FONT_FAMILY}-Regular"
    font_bold = f"{FONT_FAMILY}-Bold" if os.path.exists(FONT_BOLD) else font_reg

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'], fontName=font_bold, fontSize=18, spaceAfter=20, alignment=TA_CENTER
    )
    h2_style = ParagraphStyle(
        'CustomH2', parent=styles['Heading2'], fontName=font_bold, fontSize=14, spaceBefore=15, spaceAfter=10, alignment=TA_LEFT
    )
    body_style = ParagraphStyle(
        'CustomBody', parent=styles['Normal'], fontName=font_reg, fontSize=11, spaceAfter=8, leading=15, alignment=TA_JUSTIFY
    )

    # Сборка документа (Story)
    story = []
    
    # Добавляем главный заголовок (очищенный от символов маркдауна)
    clean_title = _md_to_html_tags(title).replace("#", "").strip()
    story.append(Paragraph(clean_title, title_style))

    # Перебираем текстовые блоки и форматируем их в зависимости от уровня заголовка
    for section in sections:
        paragraphs = section.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para: continue
            
            # Парсинг заголовков второго уровня (##)
            if para.startswith('##'):
                story.append(Paragraph(_md_to_html_tags(para.lstrip('#').strip()), h2_style))
            # Парсинг заголовков первого уровня (#) внутри текста
            elif para.startswith('#'):
                story.append(Paragraph(_md_to_html_tags(para.lstrip('#').strip()), title_style))
            # Парсинг обычного текста
            else:
                story.append(Paragraph(_md_to_html_tags(para), body_style))
                
        # Добавляем отступ в конце каждой большой секции
        story.append(Spacer(1, 15))

    # Рендерим документ в буфер
    doc.build(story)
    
    # Извлекаем байты и закрываем буфер
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes