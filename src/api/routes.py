from src.services.example_service import ExampleService
from src.services.mcdc_generator import detect_toolchain


def health() -> dict[str, str]:
    service = ExampleService()
    return {"status": service.health_status()}


def mcdc_toolchain() -> dict[str, bool]:
    return detect_toolchain()
