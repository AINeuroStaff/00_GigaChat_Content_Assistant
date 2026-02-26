"""
Проект: GigaChat_Content_Assistant
Версия: 1.0
Статус: Первая deploy версия

Модуль: __init__.py
Разработчик: GEN AI + @AI_NeuroStaff / Dubinin Vladimir

=====================================

Файлы __init__.py нужны Python для того, чтобы понимать, что папка является модулем (пакетом), из которого можно импортировать код. 
Теперь в других файлах можно импортировать схемы короче: from src.models import ContentPlan, вместо длинного from src.models.schemas import ContentPlan.

"""

from .schemas import ContentPlanItem, ContentPlan