from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pguser: str = "postgres"
    pgpassword: str = "password"
    pghost: str = "localhost"
    pgport: int = 5432
    pgdatabase: str = "postgis"

    database_search_path: str = "pgstac,public"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.pguser}:{self.pgpassword}"
            f"@{self.pghost}:{self.pgport}/{self.pgdatabase}"
        )

settings = Settings()
