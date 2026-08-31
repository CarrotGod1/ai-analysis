from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1"
    charts_dir: str = "output/charts"
    prompts_dir: str = "prompts"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    max_pandas_rows: int = 5000
    chart_width: int = 1000
    chart_height: int = 600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def charts_path(self) -> Path:
        path = Path(self.charts_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def prompts_path(self) -> Path:
        path = Path(self.prompts_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
