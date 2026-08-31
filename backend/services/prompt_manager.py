import uuid
from pathlib import Path

from config import settings
from models.schemas import Prompt, PromptCreate, PromptUpdate

DEFAULT_SYSTEM_PROMPT = """Ты — AI-аналитик продаж. Твоя задача — анализировать данные продаж и строить визуализации.

Правила:
1. Когда пользователь загружает файл — изучи его структуру (столбцы, типы данных, примеры) и предложи анализ.
2. Для анализа данных используй инструмент pandas — пиши Python-код для обработки DataFrame.
3. Для визуализации используй plotly — генерируй интерактивные графики.
4. Все графики сохраняются в формате HTML.
5. Отвечай на русском языке.
6. Будь точен с цифрами — округляй до 2 знаков после запятой.
7. Если данных недостаточно для анализа — скажи об этом.

Формат ответа:
- Текстовый комментарий с выводами
- Если нужен график — вызови инструмент create_chart с кодом plotly
- Если нужен расчёт — вызови инструмент run_pandas с кодом pandas
"""

TEMPLATES = {
    "overview": {
        "name": "Обзор продаж",
        "content": "Сделай общий обзор данных продаж: выручка, количество заказов, средний чек, топ товаров/клиентов. Построй график динамики продаж по месяцам.",
    },
    "top_products": {
        "name": "Топ товаров",
        "content": "Определи топ-10 товаров по выручке и по количеству продаж. Построй горизонтальные bar-чарты для обоих рейтингов.",
    },
    "comparison": {
        "name": "Сравнение периодов",
        "content": "Сравни продажи между двумя периодами (месяц к месяцу или квартал к кварталу). Покажи динамику роста/снижения.",
    },
    "anomalies": {
        "name": "Аномалии",
        "content": "Найди аномальные значения в данных продаж — выбросы, резкие скачки, неожиданные спады. Объясни возможные причины.",
    },
}


class PromptManager:
    def __init__(self):
        self.prompts_dir = settings.prompts_path
        self._ensure_default_prompt()

    def _ensure_default_prompt(self):
        default_path = self.prompts_dir / "system.txt"
        if not default_path.exists():
            default_path.write_text(DEFAULT_SYSTEM_PROMPT, encoding="utf-8")
        for key, tmpl in TEMPLATES.items():
            tpl_path = self.prompts_dir / f"template_{key}.txt"
            if not tpl_path.exists():
                tpl_path.write_text(tmpl["content"], encoding="utf-8")

    def get_system_prompt(self) -> str:
        path = self.prompts_dir / "system.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return DEFAULT_SYSTEM_PROMPT

    def save_system_prompt(self, content: str):
        path = self.prompts_dir / "system.txt"
        path.write_text(content, encoding="utf-8")

    def list_prompts(self) -> list[Prompt]:
        prompts = []
        for p in self.prompts_dir.glob("*.txt"):
            if p.name == "system.txt":
                continue
            content = p.read_text(encoding="utf-8")
            name = p.stem
            is_template = name.startswith("template_")
            prompts.append(
                Prompt(
                    id=p.name,
                    name=name.replace("template_", "") if is_template else name,
                    content=content,
                    description="Шаблон" if is_template else "Пользовательский промпт",
                )
            )
        return prompts

    def get_prompt(self, prompt_id: str) -> Prompt | None:
        path = self.prompts_dir / prompt_id
        if not path.exists():
            return None
        return Prompt(
            id=prompt_id,
            name=path.stem,
            content=path.read_text(encoding="utf-8"),
            description="",
        )

    def create_prompt(self, data: PromptCreate) -> Prompt:
        prompt_id = f"{data.name.lower().replace(' ', '_')}.txt"
        path = self.prompts_dir / prompt_id
        if path.exists():
            raise ValueError(f"Промпт '{data.name}' уже существует")
        path.write_text(data.content, encoding="utf-8")
        return Prompt(id=prompt_id, name=data.name, content=data.content, description=data.description)

    def update_prompt(self, prompt_id: str, data: PromptUpdate) -> Prompt | None:
        path = self.prompts_dir / prompt_id
        if not path.exists():
            return None
        content = data.content if data.content is not None else path.read_text(encoding="utf-8")
        path.write_text(content, encoding="utf-8")
        return Prompt(
            id=prompt_id,
            name=data.name or path.stem,
            content=content,
            description=data.description or "",
        )

    def delete_prompt(self, prompt_id: str) -> bool:
        path = self.prompts_dir / prompt_id
        if path.exists():
            path.unlink()
            return True
        return False

    def get_template(self, template_key: str) -> str | None:
        path = self.prompts_dir / f"template_{template_key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None


prompt_manager = PromptManager()
