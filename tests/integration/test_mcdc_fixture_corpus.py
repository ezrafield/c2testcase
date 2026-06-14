from pathlib import Path

from src.services.mcdc_generator import generate_mcdc_report


FIXTURE_DIR = Path("tests/fixtures/c")


def test_fixture_corpus_has_expected_generated_scores() -> None:
    expectations = {
        "easy_boolean_logic.c": (1.0, set()),
        "easy_multiple_decisions.c": (1.0, set()),
        "architecture_lifecycle_gate.c": (1.0, {"environment"}),
        "medium_nested_logic.c": (1.0, {"environment"}),
        "medium_enum_state.c": (1.0, {"environment"}),
        "hard_coupled_conditions.c": (0.5, {"coupled"}),
        "hard_environment_dependencies.c": (1.0, {"environment"}),
        "hard_too_many_conditions.c": (1.0, set()),
        "hardware_in_loop_diagnostics.c": (1.0, {"environment"}),
        "hardware_register_safety.c": (1.0, {"environment"}),
        "mbd_autocode_controller.c": (1.0, {"environment"}),
        "simple_logic.c": (1.0, set()),
        "system_acceptance_matrix.c": (0.8181818181818182, {"environment"}),
        "unit_integration_gate.c": (1.0, {"environment"}),
    }

    assert {path.name for path in FIXTURE_DIR.glob("*.c")} == set(expectations)

    for filename, (score, expected_gap_types) in expectations.items():
        report = generate_mcdc_report(FIXTURE_DIR / filename)
        gap_types = {
            gap.classification
            for decision in report.decisions
            for gap in decision.gaps
        }
        assert report.score == score, filename
        assert expected_gap_types.issubset(gap_types), filename

    hard_coupled = generate_mcdc_report(FIXTURE_DIR / "hard_coupled_conditions.c")
    assert {
        gap.classification
        for decision in hard_coupled.decisions
        for gap in decision.gaps
    } == {"coupled"}

    hard_coupled_masking = generate_mcdc_report(FIXTURE_DIR / "hard_coupled_conditions.c", mcdc_mode="masking")
    assert hard_coupled_masking.score >= 0.75

    lifecycle = generate_mcdc_report(FIXTURE_DIR / "architecture_lifecycle_gate.c")
    assert lifecycle.score == 1.0
    assert any(
        "grouped top-level `&&` expression" in warning
        for decision in lifecycle.decisions
        for warning in decision.warnings
    )

    lifecycle_multicondition = generate_mcdc_report(
        FIXTURE_DIR / "architecture_lifecycle_gate.c",
        mcdc_mode="multicondition",
    )
    assert lifecycle_multicondition.score == 0.0
    assert {
        gap.classification
        for decision in lifecycle_multicondition.decisions
        for gap in decision.gaps
    } == {"tool-limited"}
