from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    default_ttl: int = 300      # 5 min
    news_ttl: int = 60          # 1 min — news changes often
    category_ttl: int = 600     # 10 min — categories rarely change
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
