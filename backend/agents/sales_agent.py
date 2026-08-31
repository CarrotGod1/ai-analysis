import json
import re
import traceback
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from services.llm import ollama
from services.chart_service import chart_service
from config import settings


class SalesAgent:
    def __init__(self):
        self.sessions: dict[str, pd.DataFrame] = {}

    def _build_tools_description(self) -> str:
        return """Доступные инструменты:

1. run_pandas — выполнить Python-код на pandas. DataFrame доступен как `df`. Результат — строковое представление.
   Формат: [TOOL:run_pandas]\n```python\nкод\n```\n[/TOOL]

2. create_chart — создать график на plotly. Используй go.Figure() или px.*. График сохраняется как HTML.
   Доступные переменные: df (DataFrame), go (graph_objects), px (express), go (import plotly.graph_objects as go)
   Формат: [TOOL:create_chart]\n```python\nкод\n```\n[/TOOL]

3. get_data_info — получить информацию о текущем DataFrame (схема, типы, примеры, статистика).
   Формат: [TOOL:get_data_info][/TOOL]

Правила:
- Для одного шага — один инструмент.
- Используй [DONE] когда завершишь анализ и готов дать финальный ответ.
- Всегда заключай код в блоки ```python ... ```
- Начни с get_data_info если пользователь загрузил новый файл."""

    def register_dataframe(self, session_id: str, df: pd.DataFrame):
        self.sessions[session_id] = df

    def get_dataframe(self, session_id: str) -> pd.DataFrame | None:
        return self.sessions.get(session_id)

    def _execute_tool(self, tool_name: str, code: str, session_id: str) -> str:
        df = self.sessions.get(session_id)
        if df is None and tool_name != "get_data_info":
            return "Ошибка: данные не загружены. Пользователь должен загрузить файл."

        try:
            if tool_name == "run_pandas":
                return self._run_pandas(code, df)
            elif tool_name == "create_chart":
                return self._run_chart(code, df, session_id)
            elif tool_name == "get_data_info":
                return self._get_data_info(df)
            else:
                return f"Неизвестный инструмент: {tool_name}"
        except Exception as e:
            return f"Ошибка выполнения: {traceback.format_exc()}"

    def _run_pandas(self, code: str, df: pd.DataFrame) -> str:
        local_vars: dict[str, Any] = {"df": df, "pd": pd}
        exec(code, {"__builtins__": __builtins__}, local_vars)
        result = local_vars.get("result", local_vars.get("output"))
        if result is not None:
            if isinstance(result, pd.DataFrame):
                return result.head(50).to_string()
            return str(result)
        if "print" not in code:
            return "Код выполнен (без вывода). Используй print() или присвой переменную result."
        return "Код выполнен."

    def _run_chart(self, code: str, df: pd.DataFrame, session_id: str) -> str:
        chart_globals: dict[str, Any] = {
            "df": df,
            "pd": pd,
            "px": px,
            "go": go,
            "__builtins__": __builtins__,
        }
        exec(code, chart_globals)
        fig = chart_globals.get("fig")
        if fig is None:
            return "Ошибка: код не создал переменную fig. Убедись, что присваиваешь результат в fig."
        fig.update_layout(
            width=settings.chart_width,
            height=settings.chart_height,
            template="plotly_white",
        )
        html_content = chart_service.fig_to_html(fig)
        chart_id, chart_path = chart_service.save_html(html_content, f"{session_id}_chart")
        return f"График создан: {chart_path}"

    def _get_data_info(self, df: pd.DataFrame | None) -> str:
        if df is None:
            return "Данные не загружены."
        lines = [
            f"Размер: {df.shape[0]} строк, {df.shape[1]} столбцов",
            f"\nСтолбцы и типы:",
        ]
        for col in df.columns:
            dtype = df[col].dtype
            non_null = df[col].notna().sum()
            sample = df[col].dropna().head(3).tolist()
            lines.append(f"  - {col} ({dtype}): {non_null} значений, примеры: {sample}")

        numeric = df.select_dtypes(include="number").columns.tolist()
        if numeric:
            desc = df[numeric].describe().round(2)
            lines.append(f"\nЧисловая статистика:\n{desc.to_string()}")

        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        if cat_cols:
            lines.append(f"\nКатегориальные столбцы: {cat_cols}")
            for col in cat_cols[:3]:
                top = df[col].value_counts().head(5)
                lines.append(f"  {col}: {top.to_dict()}")

        return "\n".join(lines)

    def _parse_tool_calls(self, text: str) -> list[dict]:
        pattern = r"\[TOOL:(\w+)\]\s*```(?:python)?\s*\n(.*?)\n```\s*\[/TOOL\]"
        matches = re.findall(pattern, text, re.DOTALL)
        return [{"tool": m[0], "code": m[1].strip()} for m in matches]

    def _has_done(self, text: str) -> bool:
        return "[DONE]" in text

    def _strip_tool_calls(self, text: str) -> str:
        text = re.sub(r"\[TOOL:\w+\]\s*```(?:python)?\s*\n.*?\n```\s*\[/TOOL\]", "", text, flags=re.DOTALL)
        text = text.replace("[DONE]", "").strip()
        return text

    async def chat(
        self,
        user_message: str,
        session_id: str,
        model: str | None = None,
        system_prompt: str | None = None,
    ):
        from services.prompt_manager import prompt_manager

        system = system_prompt or prompt_manager.get_system_prompt()
        df = self.sessions.get(session_id)

        if df is not None:
            df_info = self._get_data_info(df)
            system += f"\n\nТекущие данные:\n{df_info}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        max_iterations = 8
        all_text = ""

        for _ in range(max_iterations):
            response = await ollama.chat(messages, model=model, stream=False)
            assistant_msg = response if isinstance(response, str) else ""
            all_text += assistant_msg
            messages.append({"role": "assistant", "content": assistant_msg})

            if self._has_done(assistant_msg):
                break

            tool_calls = self._parse_tool_calls(assistant_msg)
            if not tool_calls:
                break

            for tc in tool_calls:
                tool_result = self._execute_tool(tc["tool"], tc["code"], session_id)
                messages.append({"role": "user", "content": f"Результат [{tc['tool']}]:\n{tool_result}"})

        clean_text = self._strip_tool_calls(all_text)

        charts = chart_service.list_charts()
        chart_path = None
        if charts:
            session_charts = [c for c in charts if session_id in c]
            if session_charts:
                chart_path = str(settings.charts_path / session_charts[-1])

        return {
            "reply": clean_text,
            "chart_path": chart_path,
            "model_used": model or settings.default_model,
        }


sales_agent = SalesAgent()
