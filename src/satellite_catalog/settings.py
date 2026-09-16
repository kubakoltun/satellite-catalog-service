from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja aplikacji, czytana ze zmiennych środowiskowych / pliku .env.

    Póki co tylko połączenie do bazy danych.
    Kolejne pola (np. konfiguracja brokera), w późniejszym etapi
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql://username:password@localhost:5432/postgis"
    )


settings = Settings()
