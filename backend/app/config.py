from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://localhost:5432/time_travel"

    # Neon Object Storage (S3-compatible). Matches vars from `neon deploy` / `neon env pull`.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "us-east-2"
    s3_bucket_name: str = "time-travel-blocks"

    chunk_size_bytes: int = 256 * 1024  # 256 KB
    cors_origins: str = "http://localhost:5173"
    use_local_storage: bool = False
    local_storage_path: str = "./data/blocks"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_s3_endpoint(self) -> str:
        return (self.aws_endpoint_url_s3 or "").rstrip("/")

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite"):
            return url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql://") and "+psycopg2" not in url:
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
