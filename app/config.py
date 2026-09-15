from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    collibra_base_url: str = "https://next.collibra.com/rest/2.0"
    collibra_username: str
    collibra_password: str
    anthropic_api_key: str
    delta_sharing_config_path: str = "config.json"
    delta_sharing_limit: int = 0
    log_level: str = "INFO"


settings = Settings()
