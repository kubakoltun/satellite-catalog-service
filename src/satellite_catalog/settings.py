from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja aplikacji, czytana ze zmiennych środowiskowych / pliku .env.

    Na razie (Krok 0) potrzebujemy tylko połączenia do bazy danych.
    Kolejne pola (np. konfiguracja brokera) dojdą wraz z kolejnymi krokami.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql://username:password@localhost:5432/postgis"
    )


settings = Settings()
