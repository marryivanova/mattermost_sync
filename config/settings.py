from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool
    HOST: str
    PORT: str
    LDAP_SERVER: str
    LDAP_USER: str
    LDAP_PASSWORD: str
    LDAP_SEARCH_BASE: str
    SENTRY_DSN: str | None = None

    # mattermost
    TEAM_FOR_MM: str | None = None
    MATTERMOST_API: str
    MATTERMOST_TOKEN: str
    TIMEOUT: int | None = None
    MAX_RETRIES: int | None = None
    RETRY_DELAY: int | float | None = None

    DEFAULT_TYPE_CHANNEL_OFF_TOPIC: str | None = None
    DEFAULT_TYPE_CHANNEL_TOWN_SQUARE: str | None = None

    # db
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str | int
    POSTGRES_PORT: str | int
    POSTGRES_DB: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
