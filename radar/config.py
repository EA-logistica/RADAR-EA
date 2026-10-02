from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://radar:radar_local@localhost:5432/radar"
    raw_dir: Path = Path("data/raw")
    web_dist: Path = Path("web/dist")
    scrape_delay_seconds: float = 2
    alert_price_percent: float = 20
    alert_volume_percent: float = 30
    api_token: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
