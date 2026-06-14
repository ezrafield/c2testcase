from src.models.example import Example


def test_example_model_holds_values() -> None:
    example = Example(id="example-1", name="Sample")

    assert example.id == "example-1"
    assert example.name == "Sample"
