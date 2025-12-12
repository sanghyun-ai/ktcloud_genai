"""Configuration Management"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL 데이터베이스 설정"""
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "legal_db")
    user: str = os.getenv("POSTGRES_USER", "postgres")
    password: str = os.getenv("POSTGRES_PASSWORD", "")

    def to_dict(self):
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


@dataclass
class SearchConfig:
    """검색 설정"""
    hybrid_search_alpha: float = float(os.getenv("HYBRID_SEARCH_ALPHA", "0.5"))
    top_k_results: int = int(os.getenv("TOP_K_RESULTS", "10"))
    rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "5"))
    use_reranking: bool = os.getenv("USE_RERANKING", "true").lower() == "true"


@dataclass
class ModelConfig:
    """모델 설정"""
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "jhgan/ko-sroberta-multitask")
    cross_encoder_model: str = os.getenv(
        "CROSS_ENCODER_MODEL",
        "cross-encoder/ms-marco-MiniLM-L-12-v2"
    )
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")


@dataclass
class APIConfig:
    """외부 API 설정"""
    moleg_api_key: Optional[str] = os.getenv("MOLEG_API_KEY")


@dataclass
class AppConfig:
    """전체 애플리케이션 설정"""
    db: DatabaseConfig
    search: SearchConfig
    model: ModelConfig
    api: APIConfig

    @classmethod
    def load(cls):
        """환경 변수에서 설정 로드"""
        return cls(
            db=DatabaseConfig(),
            search=SearchConfig(),
            model=ModelConfig(),
            api=APIConfig()
        )


# 전역 설정 인스턴스
config = AppConfig.load()
