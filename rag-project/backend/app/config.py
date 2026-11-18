"""실행 환경(.env -> Docker 환경 변수)만 모아 관리합니다."""
from dataclasses import dataclass, field
import os


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = field(default_factory=lambda: env("OLLAMA_BASE_URL", "http://ollama:11434"))
    embedding_model: str = field(default_factory=lambda: env("EMBEDDING_MODEL", "qwen3-embedding:8b"))
    llm_model: str = field(default_factory=lambda: env("LLM_MODEL", "exaone3.5:7.8b"))
    weaviate_http_host: str = field(default_factory=lambda: env("WEAVIATE_HTTP_HOST", "weaviate"))
    weaviate_http_port: int = field(default_factory=lambda: int(env("WEAVIATE_HTTP_PORT", "8080")))
    weaviate_grpc_host: str = field(default_factory=lambda: env("WEAVIATE_GRPC_HOST", "weaviate"))
    weaviate_grpc_port: int = field(default_factory=lambda: int(env("WEAVIATE_GRPC_PORT", "50051")))
    weaviate_collection: str = field(default_factory=lambda: env("WEAVIATE_COLLECTION", "Test"))
    weaviate_text_property: str = field(default_factory=lambda: env("WEAVIATE_TEXT_PROPERTY", "text"))
    search_top_k: int = field(default_factory=lambda: int(env("SEARCH_TOP_K", "4")))
    max_context_chars: int = field(default_factory=lambda: int(env("MAX_CONTEXT_CHARS", "10000")))

    def __post_init__(self):
        if self.search_top_k < 1 or self.search_top_k > 20:
            raise ValueError("SEARCH_TOP_K는 1~20이어야 합니다.")
        if self.max_context_chars < 500:
            raise ValueError("MAX_CONTEXT_CHARS는 500 이상이어야 합니다.")
