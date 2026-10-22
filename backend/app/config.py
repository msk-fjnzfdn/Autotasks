from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "H256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


settings = Settings()
