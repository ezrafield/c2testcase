from pathlib import Path
import shutil
import subprocess
from xml.etree import ElementTree
from zipfile import ZipFile

from src.services import mcdc_generator
from src.services.mcdc_generator import (
    ExcelExportMetadata,
    extract_decisions,
    extract_function_parameters,
    find_tool_path,
    generate_mcdc_report,
    summarize_coverage_readiness,
    testcase_table_rows as build_testcase_table_rows,
    testcase_table_rows_from_dict as build_testcase_table_rows_from_dict,
    value_for_condition,
    write_report_artifacts,
    write_testcase_workbook_rows,
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


def test_testcase_table_can_fill_manual_values_for_btc_export() -> None:
    report = {
        "testcase_table": {
            "input_columns": ["a", "b", "missing"],
            "parameter_columns": ["cal"],
            "output_columns": ["y"],
            "input_column_keys": ["a", "b", "missing"],
            "parameter_column_keys": ["cal[0]"],
            "output_column_keys": ["y"],
            "rows": [
                {
                    "inputs": {"a": "MANUAL", "b": 5, "missing": "MANUAL"},
                    "parameters": {"cal[0]": "MANUAL"},
                    "outputs": {"y": "MANUAL"},
                },
                {
                    "inputs": {"a": -2, "b": "MANUAL", "missing": "MANUAL"},
                    "parameters": {"cal[0]": 3},
                    "outputs": {"y": 1},
                },
            ],
        }
    }

    default_rows = build_testcase_table_rows_from_dict(report)
    btc_rows = build_testcase_table_rows_from_dict(report, fill_manual_for_btc=True)

    assert default_rows[2:] == [
        [0, "MANUAL", 5, "MANUAL", "MANUAL", "MANUAL"],
        [1, -2, "MANUAL", "MANUAL", 3, 1],
    ]
    assert btc_rows[2:] == [
        [0, -2, 5, 0, 3, 1],
        [1, -2, 5, 0, 3, 1],
    ]
    assert "MANUAL" not in [cell for row in btc_rows[2:] for cell in row]


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
    assert payload["testcase_table"]["target_rows"] == len(payload["testcase_table"]["rows"])
    assert payload["testcase_table"]["concrete_rows"] == len(payload["testcase_table"]["rows"])
    assert payload["testcase_table"]["input_columns"] == ["a", "b", "flag"]
    assert payload["testcase_table"]["output_columns"] == ["Decision_Result"]
    assert payload["testcase_table"]["rows"]
    for index, row in enumerate(payload["testcase_table"]["rows"]):
        assert row["step"] == index
        assert set(row["inputs"]) == {"a", "b", "flag"}
        assert row["outputs"].keys() == {"Decision_Result"}
        assert row["setup_status"] == "concrete"
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

    assert actual_rows[0] == [
        "Mode",
        "Inputs",
        *([" "] * 8),
        "Outputs",
        *([" "] * 7),
    ]
    assert actual_rows[1] == [
        "Step",
        "f_canrxok",
        *expected_rows[1][2:10],
        *expected_rows[1][10:],
    ]
    assert len(actual_rows) > len(expected_rows)
    assert report.score == 1.0
    assert [result.decision.line for result in report.decisions] == [174, 186, 201, 216]

    table = report.to_dict()["testcase_table"]
    assert table["mcdc_complete"] is True
    assert table["target_rows"] == len(table["rows"])
    assert table["concrete_rows"] == len(table["rows"])
    assert table["manual_required_rows"] == 0
    assert table["input_columns"] == expected_rows[1][1:10]
    assert table["parameter_columns"] == []
    assert table["output_columns"] == expected_rows[1][10:]
    assert table["input_columns"] == [
        "f_canrxok",
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
    assert {row["f_canrxok"] for row in input_rows} == {0, 1}
    assert any(row["VU16srs_pitch_fdrx"] == 65535 for row in input_rows)
    assert any(row["VU16srs_roll_fdrx"] == 65535 for row in input_rows)
    assert any(row["VU16srs_yaw_fd_imrx"] == 65535 for row in input_rows)
    assert any(row["outputs"]["VF24bpitchfd_s"] == 124.996 for row in table["rows"])
    assert any(row["outputs"]["VF24brollfd_s"] == 124.996 for row in table["rows"])
    assert any(row["outputs"]["VF24byawfd_s"] == 124.996 for row in table["rows"])


def test_targetlink_table_traces_condition_locals_to_root_interface_variables() -> None:
    source = Path("tests/fixtures/c/C_source_tp-lnpr_lnrsh_cal-e10at-2.c")

    report = generate_mcdc_report(source, target_function="J_tplnpr_lnrsh_cal", mcdc_mode="masking")
    table = report.to_dict()["testcase_table"]

    assert "Sa2_bgratiof_s_" not in table["input_columns"]
    assert "Sa4_Sum2" not in table["input_columns"]
    assert "VF24bgratiof_s" in table["input_columns"]
    assert "VU16rsh" in table["input_columns"]
    assert table["input_columns"].count("AF24ln_bgratiofi_s") == 3
    assert table["input_column_keys"][table["input_columns"].index("AF24ln_bgratiofi_s")] == "AF24ln_bgratiofi_s[0]"
    assert table["output_columns"].count("AF24ln_bgratiofi_s") == 3
    assert "VU16ln_rsh" in table["output_columns"]
    assert "XS15ln_bgratiofd12" in table["parameter_columns"]
    assert "XS15ln_bgratiofd12[0]" in table["parameter_column_keys"]
    ratio_rows = [row for row in table["rows"] if row["line"] in {437, 442}]
    assert ratio_rows
    assert {row["inputs"]["VF24bgratiof_s"] for row in ratio_rows} >= {-1.0, 0.0, 8.0, 9.0}
    assert all("VU16rsh" in row["inputs"] for row in table["rows"])
    assert all(row["inputs"]["VU16rsh"] == "MANUAL" for row in table["rows"])
    assert all("Sa2_bgratiof_s_" not in row["inputs"] for row in ratio_rows)
    assert any("traced VF24bgratiof_s -> Sa2_bgratiof_s_" in " ".join(row["notes"]) for row in ratio_rows)

    graph = report.to_dict()["interface_graph"]
    assert graph["nodes"]
    assert graph["edges"]
    assert graph["condition_traces"]["D18:0"]["roots"] == ["VF24bgratiof_s"]
    assert graph["condition_traces"]["D18:0"]["chain"] == ["VF24bgratiof_s", "Sa2_bgratiof_s_"]


def test_value_for_condition_accepts_c_float_and_scientific_literals() -> None:
    assert value_for_condition("Sa2_bgratiof_s_ > 8.F", True) == ("Sa2_bgratiof_s_", 9.0)
    assert value_for_condition("Sa2_bgratiof_s_ < 0.F", False) == ("Sa2_bgratiof_s_", 0.0)
    assert value_for_condition("x <= 1.52587890625e-05F", False) == ("x", 1.0000152587890625)


def test_targetlink_data_flow_traces_pointer_array_field_and_call_roots(tmp_path: Path) -> None:
    source = tmp_path / "data_flow.c"
    source.write_text(
        """
/*+++ $RAM_EXTERN$ +++*/
extern UInt16 sensor_raw;
extern UInt16 source_arr[2];
extern State state;

/*+++ $RAM_PUBLIC$ +++*/
UInt16 output_flag;

UInt16 filter(UInt16 value);

void f(void)
{
   UInt16 *p;
   UInt16 from_ptr;
   UInt16 from_call;
   UInt16 from_arr;

   p = &sensor_raw;
   from_ptr = *p;
   from_call = filter(from_ptr);
   from_arr = source_arr[1];

   if (from_call > 10U) {
      output_flag = 1;
   }
   if (from_arr <= 20U) {
      output_flag = 2;
   }
   if (state.ready != 0) {
      output_flag = 3;
   }
}
""",
        encoding="utf-8",
    )

    report = generate_mcdc_report(source, target_function="f", mcdc_mode="masking")
    table = report.to_dict()["testcase_table"]

    assert table["input_columns"] == ["sensor_raw", "source_arr", "source_arr", "state"]
    assert table["input_column_keys"] == ["sensor_raw", "source_arr[0]", "source_arr[1]", "state"]
    assert table["parameter_columns"] == []
    assert table["output_columns"] == ["output_flag"]
    assert "from_ptr" not in table["input_columns"]
    assert "from_call" not in table["input_columns"]
    assert "from_arr" not in table["input_columns"]

    rows_by_line = {}
    for row in table["rows"]:
        rows_by_line.setdefault(row["line"], []).append(row)

    call_rows = rows_by_line[24]
    assert {row["inputs"]["sensor_raw"] for row in call_rows} == {10, 11}
    assert any("traced sensor_raw -> p -> from_ptr -> from_call" in " ".join(row["notes"]) for row in call_rows)

    array_rows = rows_by_line[27]
    assert {row["inputs"]["source_arr[0]"] for row in array_rows} == {20, 21}
    assert {row["inputs"]["source_arr[1]"] for row in array_rows} == {20, 21}
    assert any("traced source_arr -> from_arr" in " ".join(row["notes"]) for row in array_rows)

    field_rows = rows_by_line[30]
    assert {row["inputs"]["state"] for row in field_rows} == {0, 1}

    graph = report.to_dict()["interface_graph"]
    assert graph["condition_traces"]["D1:0"]["chain"] == ["sensor_raw", "p", "from_ptr", "from_call"]
    assert graph["condition_traces"]["D2:0"]["chain"] == ["source_arr", "from_arr"]
    assert graph["condition_traces"]["D3:0"]["chain"] == ["state", "state.ready"]


def test_targetlink_graph_marks_ambiguous_multi_root_inputs_manual(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous.c"
    source.write_text(
        """
/*+++ $RAM_EXTERN$ +++*/
extern UInt16 a;
extern UInt16 b;

/*+++ $RAM_PUBLIC$ +++*/
UInt16 output_flag;

void f(void)
{
   UInt16 mixed;
   mixed = a + b;
   if (mixed > 5U) {
      output_flag = 1;
   }
}
""",
        encoding="utf-8",
    )

    report = generate_mcdc_report(source, target_function="f", mcdc_mode="masking")
    payload = report.to_dict()
    table = payload["testcase_table"]
    graph = payload["interface_graph"]

    assert graph["condition_traces"]["D1:0"]["roots"] == ["a", "b"]
    assert graph["condition_traces"]["D1:0"]["chain"] == ["a", "b", "mixed"]
    assert table["input_columns"] == ["a", "b"]
    assert all(row["inputs"] == {"a": "MANUAL", "b": "MANUAL"} for row in table["rows"])
    assert all(row["setup_status"] == "manual_required" for row in table["rows"])
    assert table["manual_required_rows"] == len(table["rows"])
    assert table["concrete_rows"] == 0
    assert all("MANUAL: ambiguous roots [a, b] for `mixed`." in row["notes"] for row in table["rows"])
    assert all("Manual setup required" in " ".join(row["setup_notes"]) for row in table["rows"])


def test_value_for_condition_accepts_pointer_array_and_field_lvalues() -> None:
    assert value_for_condition("(*p) > 3U", True) == ("*p", 4)
    assert value_for_condition("source_arr[1] <= 20U", False) == ("source_arr[1]", 21)
    assert value_for_condition("state.ready != 0", False) == ("state.ready", 0)


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


def test_excel_export_styles_inputs_parameters_outputs_sections(tmp_path: Path) -> None:
    output_path = tmp_path / "sections.xlsx"

    write_testcase_workbook_rows(
        [
            ["Mode", "Inputs", "Parameters", "Outputs"],
            ["Step", "input_a", "cal_a", "output_y"],
            [0, 1, 2, 3],
        ],
        output_path,
        ExcelExportMetadata(name="Section_Test"),
        normalize_with_libreoffice=False,
    )

    with ZipFile(output_path) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
        styles_xml = workbook.read("xl/styles.xml").decode()

    assert 'count="10"' in styles_xml
    assert "Parameters" in sheet_xml
    assert 'r="B5" t="inlineStr" s="2"' in sheet_xml
    assert 'r="C5" t="inlineStr" s="4"' in sheet_xml
    assert 'r="D5" t="inlineStr" s="3"' in sheet_xml
    assert 'r="E5" t="inlineStr" s="8"' in sheet_xml
    assert 'r="B6" t="inlineStr" s="5"' in sheet_xml
    assert 'r="C6" t="inlineStr" s="9"' in sheet_xml
    assert 'r="D6" t="inlineStr" s="6"' in sheet_xml
    assert 'r="E6" t="inlineStr" s="7"' in sheet_xml


def test_excel_export_is_sharepoint_friendly_ooxml(tmp_path: Path) -> None:
    output_path = tmp_path / "sharepoint.xlsx"
    metadata = ExcelExportMetadata(
        format_version="1.3",
        architecture='Example "Architecture" & <C-Code>',
        scope="sample.c:1:f\x08",
        name='SIL "SV" ATG',
    )

    write_testcase_workbook_rows(
        [
            ["Mode", "Inputs", "Outputs"],
            ["Step", "a", "y"],
            [0, " MANUAL ", 1],
        ],
        output_path,
        metadata,
    )

    with ZipFile(output_path) as workbook:
        names = set(workbook.namelist())
        assert "docProps/core.xml" in names
        assert "docProps/app.xml" in names
        workbook_xml = workbook.read("xl/workbook.xml").decode()
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode()
        styles_xml = workbook.read("xl/styles.xml").decode()
        root_rels = workbook.read("_rels/.rels").decode()
        for part in names:
            if part.endswith((".xml", ".rels")):
                ElementTree.fromstring(workbook.read(part))

    assert "SIL &quot;SV&quot; ATG" in workbook_xml or 'SIL "SV" ATG' in workbook_xml
    assert "core-properties" in root_rels
    assert "extended-properties" in root_rels
    assert "<cellStyles" in styles_xml
    assert "<dxfs" in styles_xml
    assert "<tableStyles" in styles_xml
    assert "sample.c:1:f " in sheet_xml
    assert 'xml:space="preserve"' in sheet_xml


def test_excel_export_can_be_normalized_by_libreoffice_when_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "normalized.xlsx"
    calls: list[list[str]] = []

    def fake_run(command, check, capture_output, text, timeout):
        calls.append(list(command))
        output_dir = Path(command[command.index("--outdir") + 1])
        source_path = Path(command[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, output_dir / source_path.name)
        return subprocess.CompletedProcess(command, 0, "convert ok", "")

    monkeypatch.setattr(mcdc_generator, "find_libreoffice_executable", lambda: "soffice")
    monkeypatch.setattr(mcdc_generator.subprocess, "run", fake_run)

    write_testcase_workbook_rows(
        [["Mode", "Inputs"], ["Step", "a"], [0, 1]],
        output_path,
        ExcelExportMetadata(name="LibreOffice_Format"),
    )

    assert calls
    command = calls[0]
    assert command[0] == "soffice"
    assert "--headless" in command
    assert "--convert-to" in command
    assert "xlsx" in command
    assert output_path.exists()


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
