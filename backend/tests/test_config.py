from app.config import Settings


def test_render_postgres_url_uses_asyncpg_driver() -> None:
    settings = Settings(database_url="postgresql://user:password@host/database")

    assert settings.database_url == "postgresql+asyncpg://user:password@host/database"


def test_postgres_url_with_async_driver_is_unchanged() -> None:
    url = "postgresql+asyncpg://user:password@host/database"

    assert Settings(database_url=url).database_url == url


def test_cors_origins_normalize_trailing_slashes() -> None:
    settings = Settings(database_url="postgresql+asyncpg://u:p@h/db", cors_origins="https://example.vercel.app/")

    assert settings.cors_origin_list == ["https://example.vercel.app"]