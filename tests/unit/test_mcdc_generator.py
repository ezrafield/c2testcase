from pathlib import Path
from zipfile import ZipFile

from src.services.mcdc_generator import (
    extract_decisions,
    find_tool_path,
    generate_mcdc_report,
    summarize_coverage_readiness,
    write_report_artifacts,
)


def test_extracts_conditions_from_boolean_decision() -> None:
    decisions = extract_decisions("int f(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; }")

    assert len(decisions) == 1
    assert decisions[0].conditions == ("a > 0", "b < 10", "flag")


def test_generates_full_mcdc_for_simple_expression(tmp_path: Path) -> None:
    source = tmp_path / "sample.c"
    source.write_text("int f(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; return 0; }")

    report = generate_mcdc_report(source)

    assert report.score == 1.0
    assert len(report.decisions[0].cases) >= 4
    assert set(report.decisions[0].covered_conditions) == {0, 1, 2}
    assert any(row.assignments.get("a") == 1 for row in report.decisions[0].cases)


def test_reports_gap_for_coupled_condition(tmp_path: Path) -> None:
    source = tmp_path / "coupled.c"
    source.write_text("int f(int x){ if ((x > 3) || (x > 3)) return 1; return 0; }")

    report = generate_mcdc_report(source)

    assert report.score == 0.0
    assert report.decisions[0].decision.conditions == ("x > 3", "x > 3")
    assert "No independence pair found" in report.decisions[0].warnings[0]
    assert report.decisions[0].gaps[0].classification == "coupled"


def test_masking_mode_improves_coupled_condition_score(tmp_path: Path) -> None:
    source = tmp_path / "coupled.c"
    source.write_text("int f(int x,int y){ if ((x > 3 && y > 2) || (x > 3 && y < 10)) return 1; return 0; }")

    unique = generate_mcdc_report(source, mcdc_mode="unique-cause")
    masking = generate_mcdc_report(source, mcdc_mode="masking")

    assert unique.score == 0.5
    assert masking.score >= 0.75
    assert masking.to_dict()["mcdc_mode"] == "masking"


def test_multicondition_mode_reports_truth_combination_score(tmp_path: Path) -> None:
    source = tmp_path / "sample.c"
    source.write_text("int f(int a,int b){ if (a && b) return 1; return 0; }")

    report = generate_mcdc_report(source, mcdc_mode="multicondition")

    assert report.score == 1.0
    assert len(report.decisions[0].cases) == 4


def test_direct_generation_handles_large_uniform_and_chain(tmp_path: Path) -> None:
    source = tmp_path / "large.c"
    parameters = ",".join(f"int v{index}" for index in range(13))
    conditions = " && ".join(f"v{index} > 0" for index in range(13))
    source.write_text(f"int f({parameters}){{ if ({conditions}) return 1; return 0; }}")

    report = generate_mcdc_report(source, max_conditions=12)

    assert report.score == 1.0
    assert len(report.decisions[0].cases) == 14
    assert "direct minimal generation" in report.decisions[0].warnings[0]


def test_writes_json_harness_and_gap_report(tmp_path: Path) -> None:
    source = tmp_path / "sample.c"
    header = tmp_path / "sample.h"
    source.write_text("int f(int ready,int x){ if (ready && x > 2) return 1; return 0; }")
    header.write_text("int f(int ready, int x);\n")

    report = generate_mcdc_report(
        source,
        headers=(header,),
        include_dirs=(tmp_path,),
        compile_flags=("-DUNIT_TEST",),
        target_function="f",
        input_variables=("ready", "x", "manual_input"),
    )
    json_path, harness_path, gap_report_path, excel_path = write_report_artifacts(report, tmp_path / "out")

    assert json_path.exists()
    assert harness_path.exists()
    assert gap_report_path.exists()
    assert excel_path.exists()
    assert '"score_kind": "generated_target_score"' in json_path.read_text()
    assert '"mcdc_mode": "unique-cause"' in json_path.read_text()
    assert '"input_variables": [' in json_path.read_text()
    assert "Generated MC/DC testcase scaffold" in harness_path.read_text()
    assert "Generated target score: 100.0%" in gap_report_path.read_text()
    assert "Confirmed LLVM MC/DC coverage ready:" in gap_report_path.read_text()
    with ZipFile(excel_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert "Testcase" in sheet_xml
    assert "TC1" in sheet_xml
    assert "ready" in sheet_xml
    assert "x" in sheet_xml
    assert "manual_input" in sheet_xml


def test_summarizes_missing_llvm_coverage_tools() -> None:
    ready, status = summarize_coverage_readiness(
        {
            "clang": {"available": True, "path": "clang", "version": "clang 1", "error": None},
            "llvm-cov": {"available": False, "path": None, "version": None, "error": "not found on PATH"},
            "llvm-profdata": {"available": False, "path": None, "version": None, "error": "not found on PATH"},
        }
    )

    assert ready is False
    assert "llvm-cov" in status
    assert "llvm-profdata" in status


def test_summarizes_ready_llvm_coverage_tools() -> None:
    ready, status = summarize_coverage_readiness(
        {
            "clang": {"available": True, "path": "clang", "version": "clang 1", "error": None},
            "llvm-cov": {"available": True, "path": "llvm-cov", "version": "llvm-cov 1", "error": None},
            "llvm-profdata": {
                "available": True,
                "path": "llvm-profdata",
                "version": "llvm-profdata 1",
                "error": None,
            },
        }
    )

    assert ready is True
    assert "available" in status


def test_finds_llvm_tool_from_configured_bin_directory(tmp_path: Path, monkeypatch) -> None:
    tool = tmp_path / "clang.exe"
    tool.write_text("")
    monkeypatch.setenv("C2TESTCASE_LLVM_BIN", str(tmp_path))
    monkeypatch.setenv("PATH", "")

    assert find_tool_path("clang") == str(tool)
