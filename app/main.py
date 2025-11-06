"""FastAPI 애플리케이션 엔트리포인트."""

from fastapi import Depends, FastAPI

from .config import Settings, get_settings
from .routers import indicators, positions
from .services.sqlite import get_sqlite_path


def create_app() -> FastAPI:
    """설정을 로드하고 FastAPI 인스턴스를 생성한다."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.get("/health", tags=["health"])
    def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
        """헬스체크 및 현재 앱 이름 확인."""

        return {"status": "ok", "app": settings.app_name}

    app.include_router(indicators.router, prefix=settings.api_v1_prefix)
    app.include_router(positions.router, prefix=settings.api_v1_prefix)

    @app.get("/db/info", tags=["database"])
    def database_info() -> dict[str, str]:
        """현재 API가 사용하는 SQLite 파일 경로를 반환."""

        return {"sqlite_path": str(get_sqlite_path())}

    return app


app = create_app()
