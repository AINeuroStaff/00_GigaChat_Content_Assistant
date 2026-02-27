"""
Проект: GigaChat_Content_Assistant
Версия: 1.0
Статус: Первая deploy версия

Модуль: src/views/longread_tab.py
Разработчик: GEN AI + @AI_NeuroStaff / Dubinin Vladimir

SEO Longreads Tab: Генерация SEO-статей
=======================================

Модуль пользовательского интерфейса (Streamlit Page) для создания длинных,
структурированных статей (лонгридов) для блогов (VC.ru, Habr, Яндекс.Дзен,
корпоративный сайт), оптимизированных под поисковые системы (SEO).

Основные возможности:
- Настройка параметров статьи: тема, ключевые слова (SEO-ядро), объем текста.
- Потоковая генерация текста (streaming) для немедленной обратной связи.
- Вывод готового Markdown-кода с визуализацией структуры (заголовки, списки).

Переменные:
- Внешние (состояние):
    - st.session_state.current_niche: текущая ниша бизнеса (для автозаполнения).
- Внутренние (локальные):
    - topic: главная тема статьи.
    - target_keywords: список ключевых слов, которые нейросеть должна вписать в текст.
    - length: требуемый объем (в символах/словах).
    - full_text: полный сгенерированный текст статьи от LLM.

Функции:
- render_longread_tab() -> None
    Главная функция отрисовки интерфейса. Содержит форму ввода параметров 
    и логику вызова потокового генератора.

Связи с другими модулями:
- src.services.content_gen:
    - generate_seo_article_stream(): вызывается для потоковой генерации SEO-контента.
- main.py:
    - Подключает этот файл как страницу через st.Page().
"""

import streamlit as st
import json
from src.services.content_gen import generate_seo_article_stream

def create_html_export(markdown_text: str, title: str) -> str:
    """
    Оборачивает Markdown-текст в HTML-шаблон с подключенным скриптом marked.js.
    Это позволяет получить красиво сверстанный оффлайн-документ без установки тяжелых Python-библиотек.
    """
    # Экранируем обратные кавычки для безопасной вставки в JS
    safe_md = markdown_text.replace("`", "\\`").replace("$", "\\$")
    
    html_template = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        h1, h2, h3 {{ color: #2c3e50; margin-top: 1.5em; }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 4px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 8px; overflow-x: auto; }}
        blockquote {{ border-left: 4px solid #6c63ff; margin-left: 0; padding-left: 15px; color: #555; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
    <div id="content">Загрузка контента...</div>
    <script>
        const rawMarkdown = `{safe_md}`;
        document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
    </script>
</body>
</html>"""
    return html_template

def render_longread_tab():
    st.title("📝 Лонгриды и SEO-статьи")
    st.markdown("Генерация объемных, структурированных статей для блога с учетом SEO-требований.")

    # Инициализация состояния для хранения сгенерированной статьи
    if "current_longread" not in st.session_state:
        st.session_state.current_longread = None

    col_settings, col_result = st.columns([1, 2.5])

    # --- КОЛОНКА НАСТРОЕК ---
    with col_settings:
        st.subheader("Настройки SEO")
        with st.form("seo_article_form"):
            niche = st.text_input("Ниша бизнеса", value=st.session_state.get("current_niche", ""))
            
            # Интеллектуальный выбор темы
            saved_topics = st.session_state.get("generated_topics", [])
            if saved_topics:
                topic = st.selectbox("Тема статьи:", ["-- Своя тема --"] + saved_topics)
                if topic == "-- Своя тема --":
                    topic = st.text_input("Введите свою тему:")
            else:
                topic = st.text_input("Тема статьи:")

            target_keywords = st.text_area(
                "Ключевые слова (SEO)",
                placeholder="Например: купить онлайн, тренды 2026, отзывы экспертов (оставьте пустым, чтобы AI подобрал сам)"
            )
            
            length = st.selectbox(
                "Ориентировочный объем",
                ["1500 слов (Стандартная статья)", "2500 слов (Подробный лонгрид)", "4000 слов (Ultimate Guide)"],
                index=1
            )

            generate_btn = st.form_submit_button("Написать статью 🚀", width="stretch")

    # --- КОЛОНКА РЕЗУЛЬТАТА ---
    with col_result:
        if generate_btn:
            if not topic.strip():
                st.error("Пожалуйста, укажите тему статьи.")
            else:
                st.session_state.current_longread = None # Сброс прошлого результата
                
                st.subheader(f"Генерация: {topic}")
                with st.spinner("AI собирает информацию и пишет статью. Это может занять около минуты..."):
                    # Запускаем потоковую генерацию
                    stream = generate_seo_article_stream(
                        business_niche=niche,
                        topic=topic,
                        target_keywords=target_keywords if target_keywords.strip() else "Определить автоматически на основе темы",
                        length=length
                    )
                    
                    # st.write_stream отображает текст по мере его появления
                    full_article = st.write_stream(stream)
                    st.session_state.current_longread = full_article
                    
                st.success("Статья успешно написана!")
                st.rerun() # Обновляем UI, чтобы показать кнопки экспорта

        # Если в сессии есть готовая статья, показываем её и кнопки действий
        if st.session_state.current_longread:
            st.markdown("### Готовая статья")
            
            # Используем st.code для удобного копирования (в правом верхнем углу блока есть кнопка Copy)
            st.caption("Вы можете скопировать текст, нажав на иконку в правом верхнем углу блока ниже:")
            st.code(st.session_state.current_longread, language="markdown")

            st.markdown("---")
            st.markdown("#### Экспорт")
            
            col_dl1, col_dl2 = st.columns(2)
            
            # Подготовка файлов
            md_bytes = st.session_state.current_longread.encode('utf-8')
            html_string = create_html_export(st.session_state.current_longread, topic)
            html_bytes = html_string.encode('utf-8')
            
            safe_filename = "".join([c if c.isalnum() else "_" for c in topic])[:20]
            
            with col_dl1:
                st.download_button(
                    label="📄 Скачать как Markdown (.md)",
                    data=md_bytes,
                    file_name=f"article_{safe_filename}.md",
                    mime="text/markdown",
                    width="stretch"
                )
                
            with col_dl2:
                st.download_button(
                    label="🌐 Скачать как веб-страницу (.html)",
                    data=html_bytes,
                    file_name=f"article_{safe_filename}.html",
                    mime="text/html",
                    width="stretch"
                )

# Запуск рендера страницы
render_longread_tab()