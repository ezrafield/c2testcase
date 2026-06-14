from pathlib import Path

from scripts.run_llvm_mcdc_coverage import (
    FunctionSignature,
    build_condition_aware_domains,
    compute_adjusted_mcdc,
    extract_integer_constants,
    extract_struct_fields,
    extract_confirmed_mcdc_scores,
    parse_parameter,
    parse_llvm_decision_pairs,
    render_executable_harness,
    solve_case_assignments,
)


def test_extracts_confirmed_mcdc_scores() -> None:
    report = """
    MC/DC Coverage for Decision: 100.00%
    MC/DC Coverage for Decision: 50.00%
    """

    assert extract_confirmed_mcdc_scores(report) == [1.0, 0.5]


def test_render_harness_uses_c_boolean_literals() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="logic",
        parameters=(("int", "a"), ("int", "flag")),
        source_path=Path(__file__),
        constants={},
    )
    report = {
        "decisions": [
            {
                "conditions": ["a", "flag"],
                "cases": [
                    {"values": [True, True], "assignments": {"a": 1, "flag": True}},
                    {"values": [False, False], "assignments": {"a": 0, "flag": False}},
                ],
            },
        ],
    }

    harness = render_executable_harness(signature, report)

    assert "logic(1, 1)" in harness
    assert "logic(0, 0)" in harness


def test_parse_parameter_handles_scalars_and_pointers() -> None:
    assert parse_parameter("ProjectPhase phase") == ("ProjectPhase", "phase")
    assert parse_parameter("const LifecycleEvidence *evidence") == ("const LifecycleEvidence *", "evidence")


def test_solves_missing_variable_comparison_assignments() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="medium_nested_logic",
        parameters=(("int", "ready"), ("int", "mode"), ("int", "count"), ("int", "limit")),
        source_path=Path(__file__),
        constants={},
    )

    assignments = solve_case_assignments(
        signature,
        ["ready", "mode == 1", "count > limit"],
        [True, True, True],
        {"ready": True, "mode": 1},
    )

    assert assignments["count"] > assignments["limit"]


def test_extracts_enum_constants_for_solver() -> None:
    source = """
    typedef enum {
        STATE_INIT = 0,
        STATE_ACTIVE = 1,
        STATE_ERROR = 2
    } State;
    """

    assert extract_integer_constants(source)["STATE_ACTIVE"] == 1


def test_extracts_typedef_struct_int_fields() -> None:
    source = """
    typedef struct {
        int ready;
        int done;
    } Evidence;
    """

    assert extract_struct_fields(source)["Evidence"] == ("ready", "done")


def test_solves_enum_constant_comparison() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="medium_enum_state",
        parameters=(("State", "state"), ("int", "retries")),
        source_path=Path(__file__),
        constants={"STATE_ACTIVE": 1},
    )

    assignments = solve_case_assignments(
        signature,
        ["state == STATE_ACTIVE", "retries <= 3"],
        [True, True],
        {"retries": 3},
    )

    assert assignments["state"] == 1


def test_repairs_conflicting_enum_and_integer_assignments() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="system_acceptance_matrix",
        parameters=(("ProjectPhase", "phase"), ("int", "risk_class")),
        source_path=Path(__file__),
        constants={"PHASE_SYSTEM_TEST": 6, "PHASE_HARDWARE_TEST": 7},
    )

    assignments = solve_case_assignments(
        signature,
        ["phase == PHASE_SYSTEM_TEST", "risk_class == 0"],
        [True, True],
        {"phase": 0, "risk_class": 2},
    )

    assert assignments == {"phase": 6, "risk_class": 0}


def test_condition_aware_domains_keep_enum_search_small() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="system_acceptance_matrix",
        parameters=(("ProjectPhase", "phase"), ("int", "risk_class"), ("int", "requirement_pass")),
        source_path=Path(__file__),
        constants={"PHASE_SYSTEM_TEST": 6, "PHASE_HARDWARE_TEST": 7},
    )

    domains = build_condition_aware_domains(
        signature,
        ["phase == PHASE_SYSTEM_TEST", "risk_class <= 2", "requirement_pass"],
    )

    assert domains[0] == (6, 7, 5)
    assert set(domains[1]) == {1, 2, 3}
    assert domains[2] == (0, 1)


def test_parses_llvm_covered_pairs() -> None:
    report = """
    |  Number of Conditions: 4
    |  C1-Pair: covered: (1,3)
    |  C2-Pair: not covered
    |  C3-Pair: covered: (2,4)
    """

    assert parse_llvm_decision_pairs(report) == [{"condition_count": 4, "covered": {0, 2}}]


def test_adjusts_strongly_coupled_tautological_decision() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="hard_coupled_conditions",
        parameters=(("int", "x"), ("int", "y")),
        source_path=Path(__file__),
        constants={},
    )
    generated_report = {
        "decisions": [
            {
                "id": "D1",
                "expression": "(x > 3 && y > 2) || (x > 3 && y < 10)",
                "conditions": ["x > 3", "y > 2", "x > 3", "y < 10"],
            }
        ]
    }
    llvm_report = """
    |  Number of Conditions: 4
    |  C1-Pair: covered: (1,3)
    |  C2-Pair: not covered
    |  C3-Pair: not covered
    |  C4-Pair: not covered
    """

    adjustment = compute_adjusted_mcdc(generated_report, signature, llvm_report)

    assert adjustment["adjusted_average"] == 1.0
    assert len(adjustment["justifications"]) == 3
    reasons = {item["condition"]: item["reason"] for item in adjustment["justifications"]}
    assert reasons["x > 3"] == "duplicate-condition"
    assert reasons["y > 2"] == "no-independence-pair"
    assert reasons["y < 10"] == "no-independence-pair"


def test_render_harness_initializes_struct_pointer_fields() -> None:
    signature = FunctionSignature(
        return_type="int",
        name="gate",
        parameters=(("const Evidence *", "e"), ("int", "override")),
        source_path=Path(__file__),
        constants={},
        structs={"Evidence": ("ready", "count")},
    )
    report = {
        "decisions": [
            {
                "conditions": ["e != 0", "e->ready", "e->count == 0", "override"],
                "cases": [
                    {
                        "values": [True, True, True, False],
                        "assignments": {"override": False},
                    },
                ],
            },
        ],
    }

    harness = render_executable_harness(signature, report)

    assert "Evidence e_1 = {0};" in harness
    assert "e_1.ready = 1;" in harness
    assert "e_1.count = 0;" in harness
    assert "gate(&e_1, 0)" in harness
