from src.services.example_service import ExampleService


def test_health_status_is_ok() -> None:
    assert ExampleService().health_status() == "ok"
