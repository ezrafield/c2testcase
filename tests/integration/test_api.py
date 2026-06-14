from src.api.routes import health


def test_health_route_returns_ok() -> None:
    assert health() == {"status": "ok"}
