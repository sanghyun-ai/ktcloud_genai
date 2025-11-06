"""애플리케이션 환경설정을 중앙에서 관리하는 모듈."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정값 정의."""

    app_name: str = "VibeTrading Backend"
    api_v1_prefix: str = "/api/v1"

    upbit_access_key: str
    upbit_secret_key: str

    database_url: str = "sqlite:///./indicators.db"
    usd_krw_rate: float = 1350.0
    positions_config_path: str = "./positions_config.json"

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """싱글턴 패턴으로 설정 인스턴스 반환."""

    return Settings()  # type: ignore[call-arg]


settings = get_settings()
