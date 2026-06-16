from pathlib import Path
from zipfile import ZipFile

from src.services.mcdc_generator import (
    ExcelExportMetadata,
    extract_decisions,
    extract_function_parameters,
    find_tool_path,
    generate_mcdc_report,
    summarize_coverage_readiness,
    testcase_table_rows as build_testcase_table_rows,
    write_report_artifacts,
)


def test_extracts_conditions_from_boolean_decision() -> None:
    decisions = extract_decisions("int f(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; }")

    assert len(decisions) == 1
    assert decisions[0].conditions == ("a > 0", "b < 10", "flag")


def test_extracts_target_function_input_parameters() -> None:
    source = """
    static int helper(int ignored) { return ignored; }
    int logic(const uint8_t f_canrxok, uint16_t VU16srs_lat_g_fd_imrx, float *VF24blatgfd_s) {
        if (f_canrxok && VU16srs_lat_g_fd_imrx > 0) return 1;
        return 0;
    }
    """

    assert extract_function_parameters(source, "logic") == (
        "f_canrxok",
        "VU16srs_lat_g_fd_imrx",
        "VF24blatgfd_s",
    )


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


def test_testcase_table_is_input_first_with_boundary_values(tmp_path: Path) -> None:
    source = tmp_path / "bounds.c"
    source.write_text("int f(int a,int b){ if (a > 3 && b < 4) return 1; return 0; }")

    report = generate_mcdc_report(
        source,
        input_variables=("a", "b", "IN_gear", "IN_ignition"),
        manual_inputs={"IN_gear": "D", "IN_ignition": 1},
        output_variables=("VF24blatgfd_s", "VS15lat_grev"),
        manual_outputs={"VF24blatgfd_s": -24.5, "VS15lat_grev": -2.5},
    )
    rows = build_testcase_table_rows(report)

    assert rows[0] == ["Mode", "Inputs", "Inputs", "Inputs", "Inputs", "Outputs", "Outputs"]
    assert rows[1] == ["Step", "a", "b", "IN_gear", "IN_ignition", "VF24blatgfd_s", "VS15lat_grev"]
    assert rows[2:5] == [
        [0, 4, 3, "D", 1, -24.5, -2.5],
        [1, 3, 3, "D", 1, -24.5, -2.5],
        [2, 4, 4, "D", 1, -24.5, -2.5],
    ]
    assert all(cell != "" for row in rows for cell in row)


def test_testcase_table_fills_missing_manual_values(tmp_path: Path) -> None:
    source = tmp_path / "bounds.c"
    source.write_text("int f(int a,int b){ if (a > 3 && b < 4) return 1; return 0; }")

    report = generate_mcdc_report(
        source,
        input_variables=("a", "b", "not_in_condition"),
        output_variables=("expected_signal",),
    )
    rows = build_testcase_table_rows(report)

    assert rows[1] == ["Step", "a", "b", "not_in_condition", "expected_signal"]
    assert [row[3] for row in rows[2:]] == ["MANUAL", "MANUAL", "MANUAL"]
    assert [row[4] for row in rows[2:]] == ["MANUAL", "MANUAL", "MANUAL"]
    assert all(cell != "" for row in rows for cell in row)


def test_testcase_table_columns_default_to_c_function_inputs(tmp_path: Path) -> None:
    source = tmp_path / "logic.c"
    source.write_text(
        "int logic(int a,int b,int extra_input){ if (a > 3 && b < 4) return 1; return 0; }"
    )

    report = generate_mcdc_report(source, target_function="logic")
    rows = build_testcase_table_rows(report)

    assert report.input_variables == ("a", "b", "extra_input")
    assert rows[1] == ["Step", "a", "b", "extra_input", "Decision_Result"]
    assert [row[3] for row in rows[2:]] == ["MANUAL", "MANUAL", "MANUAL"]
    assert all(cell != "" for row in rows for cell in row)


def test_report_returns_structured_testcase_table_from_c_inputs(tmp_path: Path) -> None:
    source = tmp_path / "logic.c"
    source.write_text(
        "int logic(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; return 0; }"
    )

    report = generate_mcdc_report(source, target_function="logic", mcdc_mode="masking")
    payload = report.to_dict()

    assert payload["score"] == 1.0
    assert payload["source_text"].startswith("int logic")
    assert payload["mcdc_complete"] is True
    assert payload["testcase_table"]["score"] == 1.0
    assert payload["testcase_table"]["mcdc_complete"] is True
    assert payload["testcase_table"]["input_columns"] == ["a", "b", "flag"]
    assert payload["testcase_table"]["output_columns"] == ["Decision_Result"]
    assert payload["testcase_table"]["rows"]
    for index, row in enumerate(payload["testcase_table"]["rows"]):
        assert row["step"] == index
        assert set(row["inputs"]) == {"a", "b", "flag"}
        assert row["outputs"].keys() == {"Decision_Result"}
        assert row["covers"]


def test_testcase_table_uses_targetlink_template_shape_with_mcdc_rows() -> None:
    fixture_dir = Path("tests/fixtures/c")
    source = fixture_dir / "io-canii03ad5d24cnv-osm-cskn-1 1.c"
    header = fixture_dir / "io-canii03ad5d24cnv-osm-cskn-1.h"
    template = fixture_dir / "result_template.md"

    report = generate_mcdc_report(
        source,
        headers=(header,),
        target_function="J_canrv_03ad5d24_cnvt",
    )
    rows = build_testcase_table_rows(report)

    expected_rows = [
        [cell for cell in line.split("\t") if cell != ""]
        for line in template.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actual_rows = [[format_table_cell(cell) for cell in row] for row in rows]

    assert actual_rows[:2] == expected_rows[:2]
    assert len(actual_rows) > len(expected_rows)
    assert report.score == 1.0
    assert [result.decision.line for result in report.decisions] == [174, 186, 201, 216]

    table = report.to_dict()["testcase_table"]
    assert table["mcdc_complete"] is True
    assert table["input_columns"] == expected_rows[1][1:10]
    assert table["output_columns"] == expected_rows[1][10:]
    assert table["input_columns"][0] == "f_canrxok"
    assert table["input_columns"][1:] == [
        "VU16srs_lat_g_fd_imrx",
        "VU16srs_lat_g_fdrx",
        "VU16srs_lon_g_fd_imrx",
        "VU16srs_lon_g_fdrx",
        "VU16srs_pitch_fdrx",
        "VU16srs_roll_fdrx",
        "VU16srs_ver_g_fdrx",
        "VU16srs_yaw_fd_imrx",
    ]
    assert {row["decision_id"] for row in table["rows"]} == {"D1", "D2", "D3", "D4"}
    input_rows = [row["inputs"] for row in table["rows"]]
    assert any(row["f_canrxok"] == 0 for row in input_rows)
    assert any(row["VU16srs_pitch_fdrx"] == 65535 for row in input_rows)
    assert any(row["VU16srs_roll_fdrx"] == 65535 for row in input_rows)
    assert any(row["VU16srs_yaw_fd_imrx"] == 65535 for row in input_rows)
    assert any(row["outputs"]["VF24bpitchfd_s"] == 124.996 for row in table["rows"])
    assert any(row["outputs"]["VF24brollfd_s"] == 124.996 for row in table["rows"])
    assert any(row["outputs"]["VF24byawfd_s"] == 124.996 for row in table["rows"])


def format_table_cell(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


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
        manual_inputs={"manual_input": 99},
        output_variables=("expected",),
        manual_outputs={"expected": 1},
    )
    json_path, harness_path, gap_report_path, excel_path = write_report_artifacts(report, tmp_path / "out")

    assert json_path.exists()
    assert harness_path.exists()
    assert gap_report_path.exists()
    assert excel_path.exists()
    assert '"score_kind": "generated_target_score"' in json_path.read_text()
    assert '"mcdc_mode": "unique-cause"' in json_path.read_text()
    assert '"input_variables": [' in json_path.read_text()
    assert '"manual_inputs": {' in json_path.read_text()
    assert '"output_variables": [' in json_path.read_text()
    assert '"manual_outputs": {' in json_path.read_text()
    assert "Generated MC/DC testcase scaffold" in harness_path.read_text()
    assert "Generated target score: 100.0%" in gap_report_path.read_text()
    assert "Confirmed LLVM MC/DC coverage ready:" in gap_report_path.read_text()
    with ZipFile(excel_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert "Step" in sheet_xml
    assert "Inputs" in sheet_xml
    assert "Outputs" in sheet_xml
    assert "expected" in sheet_xml
    assert "ready" in sheet_xml
    assert "x" in sheet_xml
    assert "manual_input" in sheet_xml
    assert "99" in sheet_xml
    assert "Format Version" in sheet_xml
    assert "Comment" in sheet_xml
    assert "<mergeCells" in sheet_xml


def test_excel_export_uses_metadata_name_and_sample_layout(tmp_path: Path) -> None:
    source = tmp_path / "sample.c"
    source.write_text("int f(int ready,int x){ if (ready && x > 2) return 1; return 0; }")

    report = generate_mcdc_report(
        source,
        target_function="f",
        output_variables=("expected",),
        manual_outputs={"expected": 1},
    )
    metadata = ExcelExportMetadata(
        format_version="1.3",
        architecture="Example Architecture [C-Code]",
        scope="sample.c:1:f",
        name="SIL_SV_ATG_1",
    )
    _, _, _, excel_path = write_report_artifacts(report, tmp_path / "out", excel_metadata=metadata)

    assert excel_path.name == "SIL_SV_ATG_1.xlsx"
    with ZipFile(excel_path) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode()
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert 'name="SIL_SV_ATG_1"' in workbook_xml
    assert "Format Version" in sheet_xml
    assert "Example Architecture [C-Code]" in sheet_xml
    assert "sample.c:1:f" in sheet_xml
    assert "SIL_SV_ATG_1" in sheet_xml
    assert "Comment" in sheet_xml
    assert "<mergeCells" in sheet_xml
    assert 'topLeftCell="A7"' in sheet_xml


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
