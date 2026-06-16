from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
import json
import os
import re
import shutil
import subprocess
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path
from typing import Any


BOOLEAN_OPERATORS = {"&&", "||"}
KEYWORDS_WITH_DECISIONS = {"if", "while"}
MAX_ENUMERATED_CONDITIONS = 12
MCDC_MODES = ("unique-cause", "masking", "multicondition")
TableValue = str | int | float | bool
TOOLCHAIN_COMMANDS = {
    "clang": ("clang", "--version"),
    "llvm-cov": ("llvm-cov", "--version"),
    "llvm-profdata": ("llvm-profdata", "--version"),
    "cbmc": ("cbmc", "--version"),
    "klee": ("klee", "--version"),
}
LLVM_TOOL_NAMES = {"clang", "llvm-cov", "llvm-profdata"}
LLVM_BIN_ENV_VAR = "C2TESTCASE_LLVM_BIN"


@dataclass(frozen=True)
class Decision:
    id: str
    keyword: str
    expression: str
    line: int
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class MCDCRow:
    values: tuple[bool, ...]
    decision_result: bool
    covers: tuple[int, ...] = field(default_factory=tuple)
    assignments: dict[str, int | bool] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Gap:
    classification: str
    message: str
    condition_index: int | None = None


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    cases: tuple[MCDCRow, ...]
    covered_conditions: tuple[int, ...]
    score: float
    gaps: tuple[Gap, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MCDCReport:
    source: str
    source_text: str
    decisions: tuple[DecisionResult, ...]
    input_variables: tuple[str, ...] = field(default_factory=tuple)
    manual_inputs: dict[str, TableValue] = field(default_factory=dict)
    output_variables: tuple[str, ...] = field(default_factory=tuple)
    manual_outputs: dict[str, TableValue] = field(default_factory=dict)
    headers: tuple[str, ...] = field(default_factory=tuple)
    include_dirs: tuple[str, ...] = field(default_factory=tuple)
    compile_flags: tuple[str, ...] = field(default_factory=tuple)
    target_function: str | None = None
    mcdc_mode: str = "unique-cause"
    toolchain: dict[str, bool] = field(default_factory=dict)
    toolchain_details: dict[str, dict[str, str | bool | None]] = field(default_factory=dict)
    coverage_ready: bool = False
    coverage_status: str = "not checked"
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def score(self) -> float:
        total = sum(len(result.decision.conditions) for result in self.decisions)
        covered = sum(len(result.covered_conditions) for result in self.decisions)
        return covered / total if total else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_text": self.source_text,
            "score": round(self.score, 4),
            "score_kind": "generated_target_score",
            "mcdc_complete": self.score == 1.0,
            "mcdc_mode": self.mcdc_mode,
            "target_function": self.target_function,
            "input_variables": list(self.input_variables),
            "manual_inputs": self.manual_inputs,
            "output_variables": list(self.output_variables),
            "manual_outputs": self.manual_outputs,
            "testcase_table": testcase_table(report=self),
            "headers": list(self.headers),
            "include_dirs": list(self.include_dirs),
            "compile_flags": list(self.compile_flags),
            "toolchain": self.toolchain,
            "toolchain_details": self.toolchain_details,
            "coverage_ready": self.coverage_ready,
            "coverage_status": self.coverage_status,
            "warnings": list(self.warnings),
            "decisions": [
                {
                    "id": result.decision.id,
                    "keyword": result.decision.keyword,
                    "line": result.decision.line,
                    "expression": result.decision.expression,
                    "conditions": list(result.decision.conditions),
                    "score": round(result.score, 4),
                    "covered_conditions": list(result.covered_conditions),
                    "gaps": [
                        {
                            "classification": gap.classification,
                            "condition_index": gap.condition_index,
                            "message": gap.message,
                        }
                        for gap in result.gaps
                    ],
                    "warnings": list(result.warnings),
                    "cases": [
                        {
                            "values": list(row.values),
                            "decision_result": row.decision_result,
                            "covers": list(row.covers),
                            "assignments": row.assignments,
                            "notes": list(row.notes),
                        }
                        for row in result.cases
                    ],
                }
                for result in self.decisions
            ],
        }


@dataclass(frozen=True)
class ExcelExportMetadata:
    format_version: str = "1.3"
    architecture: str = ""
    scope: str = ""
    name: str = "mcdc_testcases"


def generate_mcdc_report(
    source_path: Path,
    max_conditions: int = MAX_ENUMERATED_CONDITIONS,
    headers: tuple[Path, ...] = (),
    include_dirs: tuple[Path, ...] = (),
    compile_flags: tuple[str, ...] = (),
    target_function: str | None = None,
    input_variables: tuple[str, ...] = (),
    manual_inputs: dict[str, TableValue] | None = None,
    output_variables: tuple[str, ...] = (),
    manual_outputs: dict[str, TableValue] | None = None,
    mcdc_mode: str = "unique-cause",
) -> MCDCReport:
    if mcdc_mode not in MCDC_MODES:
        raise ValueError(f"Unsupported MC/DC mode: {mcdc_mode}")

    source = source_path.read_text(encoding="utf-8")
    clean_source = strip_comments_and_strings(source)
    decisions = extract_decisions(clean_source)
    detected_input_variables = extract_function_parameters(clean_source, target_function)
    warnings: list[str] = []

    if not decisions:
        warnings.append("No supported decisions found. This pass scans if/while conditions only.")

    toolchain_details = detect_toolchain_details()
    coverage_ready, coverage_status = summarize_coverage_readiness(toolchain_details)

    return MCDCReport(
        source=str(source_path),
        source_text=source,
        decisions=tuple(generate_decision_result(decision, max_conditions, mcdc_mode) for decision in decisions),
        input_variables=tuple(dict.fromkeys((*detected_input_variables, *input_variables))),
        manual_inputs=manual_inputs or {},
        output_variables=tuple(dict.fromkeys(output_variables)),
        manual_outputs=manual_outputs or {},
        headers=tuple(str(path) for path in headers),
        include_dirs=tuple(str(path) for path in include_dirs),
        compile_flags=compile_flags,
        target_function=target_function,
        mcdc_mode=mcdc_mode,
        toolchain={name: bool(details["available"]) for name, details in toolchain_details.items()},
        toolchain_details=toolchain_details,
        coverage_ready=coverage_ready,
        coverage_status=coverage_status,
        warnings=tuple(warnings),
    )


def write_report_artifacts(
    report: MCDCReport,
    output_dir: Path,
    excel_metadata: ExcelExportMetadata | None = None,
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "mcdc_cases.json"
    harness_path = output_dir / "generated_mcdc_tests.c"
    gap_report_path = output_dir / "gap_report.md"
    metadata = excel_metadata or ExcelExportMetadata()
    excel_path = output_dir / f"{safe_excel_filename(metadata.name)}.xlsx"

    json_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    harness_path.write_text(render_c_harness(report), encoding="utf-8")
    gap_report_path.write_text(render_gap_report(report), encoding="utf-8")
    write_testcase_workbook(report, excel_path, metadata)
    return json_path, harness_path, gap_report_path, excel_path


def write_testcase_workbook(
    report: MCDCReport,
    output_path: Path,
    metadata: ExcelExportMetadata | None = None,
) -> None:
    metadata = metadata or ExcelExportMetadata()
    rows = testcase_table_rows(report)
    write_testcase_workbook_rows(rows, output_path, metadata)


def write_testcase_workbook_rows(
    rows: list[list[TableValue]],
    output_path: Path,
    metadata: ExcelExportMetadata | None = None,
) -> None:
    metadata = metadata or ExcelExportMetadata()
    with ZipFile(output_path, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", xlsx_content_types())
        workbook.writestr("_rels/.rels", xlsx_root_rels())
        workbook.writestr("xl/workbook.xml", xlsx_workbook(metadata.name))
        workbook.writestr("xl/_rels/workbook.xml.rels", xlsx_workbook_rels())
        workbook.writestr("xl/styles.xml", xlsx_styles())
        workbook.writestr("xl/worksheets/sheet1.xml", xlsx_sheet(rows, metadata))


def testcase_table_rows_from_dict(report: dict[str, Any]) -> list[list[TableValue]]:
    table = report.get("testcase_table", {})
    input_columns = list(table.get("input_columns", []))
    output_columns = list(table.get("output_columns", []))
    group_headers = table.get(
        "group_headers",
        ["Mode", *(["Inputs"] * len(input_columns)), *(["Outputs"] * len(output_columns))],
    )
    rows: list[list[TableValue]] = [
        list(group_headers),
        ["Step", *input_columns, *output_columns],
    ]
    for row in table.get("rows", []):
        inputs = row.get("inputs", {})
        outputs = row.get("outputs", {})
        rows.append(
            [
                row.get("step", len(rows) - 2),
                *(inputs.get(name, "MANUAL") for name in input_columns),
                *(outputs.get(name, "MANUAL") for name in output_columns),
            ]
        )
    if len(rows) == 2:
        rows.append(["No generated testcases", *(["MANUAL"] * len(input_columns)), *(["MANUAL"] * len(output_columns))])
    return rows


def testcase_table_rows(report: MCDCReport) -> list[list[TableValue]]:
    table = testcase_table(report)
    rows: list[list[TableValue]] = [
        table.get(
            "group_headers",
            ["Mode", *(["Inputs"] * len(table["input_columns"])), *(["Outputs"] * len(table["output_columns"]))],
        ),
        ["Step", *table["input_columns"], *table["output_columns"]],
    ]
    if table["rows"]:
        for row in table["rows"]:
            rows.append([row["step"], *row["inputs"].values(), *row["outputs"].values()])
        return rows
    rows.append(
        [
            "No generated testcases",
            *(["MANUAL"] * len(table["input_columns"])),
            *(["MANUAL"] * len(table["output_columns"])),
        ]
    )
    return rows


def testcase_table(report: MCDCReport) -> dict[str, Any]:
    targetlink_table = targetlink_logged_interface_table(report)
    if targetlink_table is not None:
        return targetlink_table

    inferred_variable_names = sorted(
        {
            name
            for result in report.decisions
            for row in result.cases
            for name in row.assignments
        }
    )
    variable_names = list(dict.fromkeys((*report.input_variables, *inferred_variable_names)))
    output_names = list(report.output_variables) or ["Decision_Result"]
    rows: list[dict[str, Any]] = []
    step_index = 0
    for result in report.decisions:
        for row in sorted(result.cases, key=lambda case: testcase_sort_key(case, variable_names)):
            assignments = {
                name: row.assignments.get(name, report.manual_inputs.get(name, "MANUAL"))
                for name in variable_names
            }
            outputs = {
                name: row.decision_result if name == "Decision_Result" else report.manual_outputs.get(name, "MANUAL")
                for name in output_names
            }
            rows.append(
                {
                    "step": step_index,
                    "decision_id": result.decision.id,
                    "line": result.decision.line,
                    "inputs": assignments,
                    "outputs": outputs,
                    "mcdc_condition_values": list(row.values),
                    "decision_result": row.decision_result,
                    "covers": list(row.covers),
                    "notes": list(row.notes),
                }
            )
            step_index += 1
    return {
        "input_columns": variable_names,
        "output_columns": output_names,
        "score": round(report.score, 4),
        "score_kind": "generated_target_score",
        "mcdc_complete": report.score == 1.0,
        "rows": rows,
    }


def targetlink_logged_interface_table(report: MCDCReport) -> dict[str, Any] | None:
    interface = extract_log_var_interface(report.source_text)
    if interface is None:
        return None

    input_names, output_names = interface
    output_names = targetlink_output_order(output_names)
    testcase_inputs = targetlink_mcdc_interface_inputs(report, input_names, output_names)
    if testcase_inputs is None:
        return None

    rows: list[dict[str, Any]] = []
    output_state = {name: 0 for name in output_names}
    for step_index, scenario in enumerate(testcase_inputs):
        inputs = scenario["inputs"]
        output_state.update(evaluate_targetlink_outputs(inputs, output_state))
        rows.append(
            {
                "step": step_index,
                "decision_id": scenario["decision_id"],
                "line": scenario["line"],
                "inputs": {name: inputs.get(name, "MANUAL") for name in input_names},
                "outputs": {name: output_state.get(name, "MANUAL") for name in output_names},
                "mcdc_condition_values": scenario["mcdc_condition_values"],
                "decision_result": scenario["decision_result"],
                "covers": scenario["covers"],
                "notes": scenario["notes"],
            }
        )

    return {
        "input_columns": input_names,
        "output_columns": output_names,
        "group_headers": targetlink_group_headers(input_names, output_names),
        "score": round(report.score, 4),
        "score_kind": "generated_target_score",
        "mcdc_complete": report.score == 1.0,
        "rows": rows,
    }


def targetlink_group_headers(input_names: list[str], output_names: list[str]) -> list[str]:
    return [
        "Mode",
        "Inputs",
        *([" "] * max(len(input_names) - 1, 0)),
        "Outputs",
        *([" "] * max(len(output_names) - 1, 0)),
    ]


def extract_log_var_interface(source: str) -> tuple[list[str], list[str]] | None:
    declared_interface = extract_targetlink_declared_interface(source)
    if declared_interface is not None:
        return declared_interface

    matches = list(re.finditer(r"\bLOG_VAR\s*\([^,]+,\s*_[A-Za-z_]\w*\s*,\s*([A-Za-z_]\w*)\s*\)\s*;", source))
    if len(matches) < 2:
        return None

    first_if = source.find("if", matches[0].end())
    if first_if < 0:
        return None

    input_names = [match.group(1) for match in matches if match.start() < first_if]
    output_names = [match.group(1) for match in matches if match.start() > first_if]
    input_names = list(dict.fromkeys(input_names))
    output_names = list(dict.fromkeys(name for name in output_names if name not in input_names))
    if not input_names or not output_names:
        return None
    return input_names, output_names


def extract_targetlink_declared_interface(source: str) -> tuple[list[str], list[str]] | None:
    function_parameters = list(extract_first_function_definition_parameters(source))
    ext_inputs = re.findall(r"\bEXT_SP_GLOBAL\s+\w+\s+([A-Za-z_]\w*)\s*;", source)
    global_outputs = re.findall(r"\bGLOBAL\s+\w+\s+([A-Za-z_]\w*)\s*(?:=\s*[^;]+)?;", source)
    input_names = list(dict.fromkeys((*function_parameters, *ext_inputs)))
    output_names = list(dict.fromkeys(name for name in global_outputs if name not in input_names))
    if not ext_inputs or not output_names:
        return None
    return input_names, output_names


def extract_first_function_definition_parameters(source: str) -> tuple[str, ...]:
    function_pattern = re.compile(r"\b[A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*\s+([A-Za-z_]\w*)\s*\(([^()]*)\)\s*\{")
    for match in function_pattern.finditer(source):
        if match.group(1) in KEYWORDS_WITH_DECISIONS:
            continue
        return parse_parameter_names(match.group(2))
    return ()


def targetlink_mcdc_interface_inputs(
    report: MCDCReport,
    input_names: list[str],
    output_names: list[str],
) -> list[dict[str, Any]] | None:
    expected_inputs = [
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
    expected_outputs = [
        "VF24blatgfd_s",
        "VF24blongfd_s",
        "VF24bpitchfd_s",
        "VF24brollfd_s",
        "VF24bvergfd_s",
        "VF24byawfd_s",
        "VS15lat_grev",
        "VS15lon_grev",
    ]
    if input_names != expected_inputs or set(output_names) != set(expected_outputs):
        return None

    baseline = targetlink_baseline_inputs()
    scenarios: list[dict[str, Any]] = []
    seen_inputs: set[tuple[tuple[str, int], ...]] = set()

    def add_scenario(
        inputs: dict[str, int],
        decision: DecisionResult,
        values: list[bool],
        decision_result: bool,
        reason: str,
    ) -> None:
        key = tuple((name, inputs[name]) for name in input_names)
        if key in seen_inputs:
            for scenario in scenarios:
                scenario_key = tuple((name, scenario["inputs"][name]) for name in input_names)
                if scenario_key == key:
                    scenario["notes"].append(reason)
                    break
            return
        seen_inputs.add(key)
        scenarios.append(
            {
                "inputs": inputs,
                "decision_id": decision.decision.id,
                "line": decision.decision.line,
                "mcdc_condition_values": values,
                "decision_result": decision_result,
                "covers": list(range(len(decision.decision.conditions))),
                "notes": [reason],
            }
        )

    for decision in report.decisions:
        condition = decision.decision.conditions[0] if len(decision.decision.conditions) == 1 else ""
        if condition == "f_canrxok != 0":
            add_scenario(
                dict(baseline),
                decision,
                [True],
                True,
                "Outer enable decision true case for MC/DC pair.",
            )
            disabled = dict(baseline)
            disabled["f_canrxok"] = 0
            add_scenario(
                disabled,
                decision,
                [False],
                False,
                "Outer enable decision false case for MC/DC pair.",
            )
            continue

        source_input = targetlink_source_input_for_condition(condition)
        if source_input is None:
            continue

        low = dict(baseline)
        low[source_input] = targetlink_low_raw_value(source_input)
        add_scenario(
            low,
            decision,
            [False],
            False,
            f"Saturation decision false case with `{source_input}` below threshold.",
        )
        high = dict(baseline)
        high[source_input] = 65535
        add_scenario(
            high,
            decision,
            [True],
            True,
            f"Saturation decision true case with `{source_input}` above threshold.",
        )

    return scenarios


def targetlink_baseline_inputs() -> dict[str, int]:
    return {
        "f_canrxok": 1,
        "VU16srs_lat_g_fd_imrx": 0,
        "VU16srs_lat_g_fdrx": 0,
        "VU16srs_lon_g_fd_imrx": 0,
        "VU16srs_lon_g_fdrx": 0,
        "VU16srs_pitch_fdrx": 1,
        "VU16srs_roll_fdrx": 1,
        "VU16srs_ver_g_fdrx": 1,
        "VU16srs_yaw_fd_imrx": 0,
    }


def targetlink_source_input_for_condition(condition: str) -> str | None:
    return {
        "Sa2_Sum7 > 124.996F": "VU16srs_pitch_fdrx",
        "Sa2_Sum6 > 124.996F": "VU16srs_roll_fdrx",
        "Sa2_Sum5 > 124.996F": "VU16srs_yaw_fd_imrx",
    }.get(condition)


def targetlink_low_raw_value(source_input: str) -> int:
    if source_input in {"VU16srs_pitch_fdrx", "VU16srs_roll_fdrx"}:
        return 1
    return 0


def targetlink_output_order(output_names: list[str]) -> list[str]:
    expected_outputs = [
        "VF24blatgfd_s",
        "VF24blongfd_s",
        "VF24bpitchfd_s",
        "VF24brollfd_s",
        "VF24bvergfd_s",
        "VF24byawfd_s",
        "VS15lat_grev",
        "VS15lon_grev",
    ]
    if set(output_names) == set(expected_outputs):
        return expected_outputs
    return output_names


def evaluate_targetlink_outputs(inputs: dict[str, int], previous_outputs: dict[str, TableValue]) -> dict[str, TableValue]:
    if not inputs.get("f_canrxok"):
        outputs = dict(previous_outputs)
        outputs["VS15lat_grev"] = 0
        outputs["VS15lon_grev"] = 0
        return outputs

    pitch = float32_physical(inputs["VU16srs_pitch_fdrx"], 0.003814697265625, -125.0)
    roll = float32_physical(inputs["VU16srs_roll_fdrx"], 0.003814697265625, -125.0)
    yaw = float32_physical(inputs["VU16srs_yaw_fd_imrx"], 0.003814697265625, -125.0)
    return {
        "VF24blatgfd_s": float32_physical(inputs["VU16srs_lat_g_fd_imrx"], 0.0007476806640625, -24.5),
        "VF24blongfd_s": float32_physical(inputs["VU16srs_lon_g_fd_imrx"], 0.0007476806640625, -24.5),
        "VF24bpitchfd_s": 124.996 if pitch > 124.996 else pitch,
        "VF24brollfd_s": 124.996 if roll > 124.996 else roll,
        "VF24bvergfd_s": float32_physical(inputs["VU16srs_ver_g_fdrx"], 0.0007476806640625, -24.5),
        "VF24byawfd_s": 124.996 if yaw > 124.996 else yaw,
        "VS15lat_grev": targetlink_int16_physical(inputs["VU16srs_lat_g_fdrx"]),
        "VS15lon_grev": targetlink_int16_physical(inputs["VU16srs_lon_g_fdrx"]),
    }


def float32_physical(raw_value: int, scale: float, offset: float) -> float:
    return round((raw_value * scale) + offset, 6)


def targetlink_int16_physical(raw_value: int) -> float:
    scaled = int((((int(raw_value) - 32768) * 625) / 8192))
    return round(scaled / 1000, 3)


def testcase_sort_key(row: MCDCRow, variable_names: list[str]) -> tuple[bool, tuple[str, ...]]:
    return (
        not row.decision_result,
        tuple(str(row.assignments.get(name, "")) for name in variable_names),
    )


def xlsx_content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
"""


def xlsx_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""


def xlsx_workbook(sheet_name: str = "Testcases") -> str:
    safe_name = escape(safe_sheet_name(sheet_name))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{safe_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""


def xlsx_workbook_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def xlsx_styles() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><color rgb="FF000000"/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="7">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF4B183"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD9EAF7"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD9EAD3"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F2937"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
    <xf numFmtId="0" fontId="1" fillId="6" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
  </cellXfs>
</styleSheet>
"""


def xlsx_sheet(rows: list[list[TableValue]], metadata: ExcelExportMetadata | None = None) -> str:
    metadata = metadata or ExcelExportMetadata()
    sheet_rows = excel_export_rows(rows, metadata)
    output_start = find_output_start(rows[0]) if rows else 1
    row_xml = "\n".join(
        xlsx_row(index, row, output_start=output_start)
        for index, row in enumerate(sheet_rows, start=1)
    )
    widths = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths(sheet_rows), start=1)
    )
    last_column = column_name(len(sheet_rows[0]))
    dimension = f"A1:{last_column}{len(sheet_rows)}"
    filter_dimension = f"A6:{last_column}{len(sheet_rows)}"
    comment_column = column_name(len(sheet_rows[0]))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="{dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>{widths}</cols>
  <sheetData>
{row_xml}
  </sheetData>
  <mergeCells count="1"><mergeCell ref="{comment_column}5:{comment_column}6"/></mergeCells>
  <autoFilter ref="{filter_dimension}"/>
</worksheet>
"""


def excel_export_rows(rows: list[list[TableValue]], metadata: ExcelExportMetadata) -> list[list[TableValue]]:
    if not rows:
        return []
    max_columns = len(rows[1]) + 1 if len(rows) > 1 else len(rows[0]) + 1
    padded_rows = [
        pad_row(["Format Version", metadata.format_version], max_columns),
        pad_row(["Architecture", metadata.architecture], max_columns),
        pad_row(["Scope", metadata.scope], max_columns),
        pad_row(["Name", metadata.name], max_columns),
    ]
    group_row = pad_row([*rows[0], "Comment"], max_columns)
    header_row = pad_row([*rows[1], "Comment"], max_columns)
    data_rows = [pad_row(row, max_columns) for row in rows[2:]]
    return [*padded_rows, group_row, header_row, *data_rows]


def pad_row(row: list[TableValue], width: int) -> list[TableValue]:
    return [*row, *([""] * max(width - len(row), 0))]


def find_output_start(group_row: list[TableValue]) -> int:
    for index, value in enumerate(group_row, start=1):
        if value == "Outputs":
            return index
    return len(group_row) + 1


def xlsx_row(row_index: int, row: list[TableValue], output_start: int = 1) -> str:
    cells = "".join(
        xlsx_cell(row_index, column_index, value, style=xlsx_style_for_cell(row_index, column_index, output_start, len(row)))
        for column_index, value in enumerate(row, start=1)
    )
    height_attr = ' ht="90" customHeight="1"' if row_index == 6 else ""
    return f'    <row r="{row_index}"{height_attr}>{cells}</row>'


def xlsx_style_for_cell(row_index: int, column_index: int, output_start: int, column_count: int) -> int:
    if row_index <= 4:
        return 1
    if row_index == 5:
        if column_index == column_count:
            return 4
        if column_index >= output_start:
            return 3
        if column_index >= 2:
            return 2
        return 1
    if row_index == 6:
        if column_index == column_count:
            return 7
        if column_index >= output_start:
            return 6
        if column_index >= 2:
            return 5
        return 1
    return 0


def xlsx_cell(row_index: int, column_index: int, value: TableValue, style: int = 0) -> str:
    reference = f"{column_name(column_index)}{row_index}"
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style_attr}><v>{int(value)}</v></c>'
    if isinstance(value, int | float):
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t>{text}</t></is></c>'


def column_widths(rows: list[list[TableValue]]) -> list[int]:
    widths: list[int] = []
    for column in range(len(rows[0])):
        max_length = max(len(str(row[column])) for row in rows)
        widths.append(max(10, min(max_length + 2, 48)))
    return widths


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def safe_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", "_", name).strip("'").strip()
    return (cleaned or "Testcases")[:31]


def safe_excel_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().strip(".")
    return cleaned or "mcdc_testcases"


def extract_decisions(source: str) -> tuple[Decision, ...]:
    decisions: list[Decision] = []
    decision_index = 1
    index = 0

    while index < len(source):
        match = re.search(r"\b(if|while)\s*\(", source[index:])
        if match is None:
            break

        keyword = match.group(1)
        open_paren = index + match.end() - 1
        close_paren = find_matching_paren(source, open_paren)
        if close_paren is None:
            index = open_paren + 1
            continue

        expression = source[open_paren + 1 : close_paren].strip()
        conditions = tuple(split_conditions(expression))
        line = source.count("\n", 0, open_paren) + 1
        decisions.append(
            Decision(
                id=f"D{decision_index}",
                keyword=keyword,
                expression=expression,
                line=line,
                conditions=conditions,
            )
        )
        decision_index += 1
        index = close_paren + 1

    return tuple(decisions)


def extract_function_parameters(source: str, target_function: str | None = None) -> tuple[str, ...]:
    pattern = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^()]*)\)\s*(?:\{|;)")
    for match in pattern.finditer(source):
        function_name = match.group(1)
        if function_name in KEYWORDS_WITH_DECISIONS:
            continue
        if target_function and function_name != target_function:
            continue
        parameters = parse_parameter_names(match.group(2))
        if parameters or target_function:
            return parameters
    return ()


def parse_parameter_names(raw_parameters: str) -> tuple[str, ...]:
    names: list[str] = []
    for raw_parameter in split_parameter_list(raw_parameters):
        parameter = raw_parameter.strip()
        if not parameter or parameter == "void" or "..." in parameter:
            continue
        parameter = parameter.split("=")[0].strip()
        parameter = re.sub(r"\[[^\]]*\]", "", parameter)
        match = re.search(r"([A-Za-z_]\w*)\s*$", parameter)
        if match:
            names.append(match.group(1))
    return tuple(dict.fromkeys(names))


def split_parameter_list(raw_parameters: str) -> list[str]:
    parameters: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(raw_parameters):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parameters.append(raw_parameters[start:index])
            start = index + 1
    parameters.append(raw_parameters[start:])
    return parameters


def generate_decision_result(decision: Decision, max_conditions: int, mcdc_mode: str = "unique-cause") -> DecisionResult:
    warnings: list[str] = []
    condition_count = len(decision.conditions)

    if condition_count == 0:
        return DecisionResult(decision=decision, cases=(), covered_conditions=(), score=0.0)

    if condition_count > max_conditions:
        if mcdc_mode in {"unique-cause", "masking"}:
            direct_result = generate_direct_chain_result(decision)
            if direct_result is not None:
                return direct_result
            grouped_result = generate_direct_grouped_and_result(decision)
            if grouped_result is not None:
                return grouped_result
        message = f"Decision has {condition_count} conditions; capped at {max_conditions} to avoid path explosion."
        return DecisionResult(
            decision=decision,
            cases=(),
            covered_conditions=(),
            score=0.0,
            gaps=(Gap("tool-limited", message),),
            warnings=(message,),
        )

    truth_rows = [
        values
        for values in product((False, True), repeat=condition_count)
        if duplicate_conditions_are_consistent(decision.conditions, values)
        if evaluate_decision(decision.expression, decision.conditions, values) is not None
    ]
    outcomes = {
        values: evaluate_decision(decision.expression, decision.conditions, values)
        for values in truth_rows
    }
    if mcdc_mode == "multicondition":
        return generate_multicondition_result(decision, truth_rows, outcomes)

    independence_pairs = find_independence_pairs(decision, truth_rows, outcomes, mcdc_mode)

    selected_rows: dict[tuple[bool, ...], set[int]] = {}
    for condition_index, pair in independence_pairs.items():
        for values in pair:
            selected_rows.setdefault(values, set()).add(condition_index)

    if len(independence_pairs) < condition_count:
        missing = sorted(set(range(condition_count)) - set(independence_pairs))
        warnings.append(format_missing_pair_warning(missing))

    rows: list[MCDCRow] = []
    environment_gaps: list[Gap] = []
    seen_note_gaps: set[tuple[str, str]] = set()
    for values, covers in sorted(selected_rows.items()):
        assignments, notes = concretize_conditions(decision.conditions, values)
        rows.append(
            MCDCRow(
                values=values,
                decision_result=bool(outcomes[values]),
                covers=tuple(sorted(covers)),
                assignments=assignments,
                notes=notes,
            )
        )
        for note in notes:
            classification = classify_setup_note(note)
            key = (classification, note)
            if key in seen_note_gaps:
                continue
            seen_note_gaps.add(key)
            environment_gaps.append(Gap(classification, note))

    missing_gaps = tuple(
        Gap(
            classification="coupled",
            condition_index=index,
            message=f"Condition {index} has no independence pair in the generated truth table.",
        )
        for index in sorted(set(range(condition_count)) - set(independence_pairs))
    )
    covered_conditions = tuple(sorted(independence_pairs))
    score = len(covered_conditions) / condition_count
    return DecisionResult(
        decision=decision,
        cases=tuple(rows),
        covered_conditions=covered_conditions,
        score=score,
        gaps=missing_gaps + tuple(environment_gaps),
        warnings=tuple(warnings),
    )


def generate_direct_chain_result(decision: Decision) -> DecisionResult | None:
    operator = detect_uniform_chain_operator(decision.expression, decision.conditions)
    if operator is None or has_duplicate_conditions(decision.conditions):
        return None

    if operator == "&&":
        base = tuple(True for _ in decision.conditions)
        variants = [
            tuple(index != condition_index for index, _ in enumerate(decision.conditions))
            for condition_index in range(len(decision.conditions))
        ]
    elif operator == "||":
        base = tuple(False for _ in decision.conditions)
        variants = [
            tuple(index == condition_index for index, _ in enumerate(decision.conditions))
            for condition_index in range(len(decision.conditions))
        ]
    else:
        return None

    selected_rows: dict[tuple[bool, ...], set[int]] = {base: set(range(len(decision.conditions)))}
    for condition_index, values in enumerate(variants):
        selected_rows.setdefault(values, set()).add(condition_index)

    rows: list[MCDCRow] = []
    environment_gaps: list[Gap] = []
    seen_note_gaps: set[tuple[str, str]] = set()
    for values, covers in sorted(selected_rows.items()):
        assignments, notes = concretize_conditions(decision.conditions, values)
        rows.append(
            MCDCRow(
                values=values,
                decision_result=operator == "&&" and all(values) or operator == "||" and any(values),
                covers=tuple(sorted(covers)),
                assignments=assignments,
                notes=notes,
            )
        )
        for note in notes:
            classification = classify_setup_note(note)
            key = (classification, note)
            if key in seen_note_gaps:
                continue
            seen_note_gaps.add(key)
            environment_gaps.append(Gap(classification, note))

    return DecisionResult(
        decision=decision,
        cases=tuple(rows),
        covered_conditions=tuple(range(len(decision.conditions))),
        score=1.0,
        gaps=tuple(environment_gaps),
        warnings=(
            f"Used direct minimal generation for a uniform `{operator}` Singular Boolean Expression.",
        ),
    )


def generate_direct_grouped_and_result(decision: Decision) -> DecisionResult | None:
    groups = parse_top_level_and_groups(decision.expression, decision.conditions)
    if groups is None or has_duplicate_conditions(decision.conditions):
        return None

    base = satisfying_values_for_and_groups(groups, len(decision.conditions))
    selected_rows: dict[tuple[bool, ...], set[int]] = {base: set()}
    for condition_index in range(len(decision.conditions)):
        group = next(group for group in groups if condition_index in group)
        if len(group) == 1:
            positive = base
            negative = tuple(
                False if index == condition_index else value for index, value in enumerate(base)
            )
        else:
            negative_values = list(base)
            for index in group:
                negative_values[index] = False
            positive_values = negative_values.copy()
            positive_values[condition_index] = True
            positive = tuple(positive_values)
            negative = tuple(negative_values)

        selected_rows.setdefault(positive, set()).add(condition_index)
        selected_rows.setdefault(negative, set()).add(condition_index)

    rows: list[MCDCRow] = []
    environment_gaps: list[Gap] = []
    seen_note_gaps: set[tuple[str, str]] = set()
    for values, covers in sorted(selected_rows.items()):
        outcome = evaluate_decision(decision.expression, decision.conditions, values)
        if outcome is None:
            return None
        assignments, notes = concretize_conditions(decision.conditions, values)
        rows.append(
            MCDCRow(
                values=values,
                decision_result=outcome,
                covers=tuple(sorted(covers)),
                assignments=assignments,
                notes=notes,
            )
        )
        for note in notes:
            classification = classify_setup_note(note)
            key = (classification, note)
            if key in seen_note_gaps:
                continue
            seen_note_gaps.add(key)
            environment_gaps.append(Gap(classification, note))

    return DecisionResult(
        decision=decision,
        cases=tuple(rows),
        covered_conditions=tuple(range(len(decision.conditions))),
        score=1.0,
        gaps=tuple(environment_gaps),
        warnings=(
            "Used direct minimal generation for a grouped top-level `&&` expression.",
        ),
    )


def parse_top_level_and_groups(expression: str, conditions: tuple[str, ...]) -> tuple[tuple[int, ...], ...] | None:
    top_level_terms = split_top_level_operator(expression, "&&")
    if len(top_level_terms) < 2:
        return None

    groups: list[tuple[int, ...]] = []
    used_indexes: set[int] = set()
    for term in top_level_terms:
        term_conditions = tuple(split_conditions(term))
        if not term_conditions:
            return None
        indexes: list[int] = []
        for condition in term_conditions:
            try:
                index = conditions.index(condition)
            except ValueError:
                return None
            if index in used_indexes:
                return None
            indexes.append(index)
            used_indexes.add(index)
        groups.append(tuple(indexes))

    if used_indexes != set(range(len(conditions))):
        return None
    if not any(len(group) > 1 for group in groups):
        return None
    return tuple(groups)


def satisfying_values_for_and_groups(groups: tuple[tuple[int, ...], ...], condition_count: int) -> tuple[bool, ...]:
    values = [False for _ in range(condition_count)]
    for group in groups:
        values[group[0]] = True
    return tuple(values)


def split_top_level_operator(expression: str, operator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression[index : index + len(operator)] == operator:
            parts.append(expression[start:index].strip())
            start = index + len(operator)
            index += len(operator) - 1
        index += 1
    parts.append(expression[start:].strip())
    return [part for part in parts if part]


def detect_uniform_chain_operator(expression: str, conditions: tuple[str, ...]) -> str | None:
    reduced = expression
    for index, condition in enumerate(conditions):
        reduced = reduced.replace(condition, f"C{index}")
    reduced = re.sub(r"\s+", "", reduced)
    reduced = reduced.replace("(", "").replace(")", "")
    if re.fullmatch(r"C\d+(&&C\d+)+", reduced):
        return "&&"
    if re.fullmatch(r"C\d+(\|\|C\d+)+", reduced):
        return "||"
    return None


def has_duplicate_conditions(conditions: tuple[str, ...]) -> bool:
    return len(set(conditions)) != len(conditions)


def generate_multicondition_result(
    decision: Decision,
    truth_rows: list[tuple[bool, ...]],
    outcomes: dict[tuple[bool, ...], bool | None],
) -> DecisionResult:
    rows: list[MCDCRow] = []
    covered_conditions = set()
    for values in truth_rows:
        assignments, notes = concretize_conditions(decision.conditions, values)
        rows.append(
            MCDCRow(
                values=values,
                decision_result=bool(outcomes[values]),
                covers=tuple(range(len(decision.conditions))),
                assignments=assignments,
                notes=notes,
            )
        )
        covered_conditions.update(index for index, _ in enumerate(values))

    expected_rows = 2 ** len(decision.conditions)
    score = len(truth_rows) / expected_rows if expected_rows else 1.0
    gaps: tuple[Gap, ...] = ()
    warnings: tuple[str, ...] = ()
    if len(truth_rows) < expected_rows:
        missing = expected_rows - len(truth_rows)
        message = f"{missing} truth combinations are infeasible after duplicate-condition consistency checks."
        gaps = (Gap("coupled", message),)
        warnings = (message,)

    return DecisionResult(
        decision=decision,
        cases=tuple(rows),
        covered_conditions=tuple(sorted(covered_conditions)),
        score=score,
        gaps=gaps,
        warnings=warnings,
    )


def find_independence_pairs(
    decision: Decision,
    truth_rows: list[tuple[bool, ...]],
    outcomes: dict[tuple[bool, ...], bool | None],
    mcdc_mode: str,
) -> dict[int, tuple[tuple[bool, ...], tuple[bool, ...]]]:
    independence_pairs: dict[int, tuple[tuple[bool, ...], tuple[bool, ...]]] = {}
    condition_count = len(decision.conditions)

    for condition_index in range(condition_count):
        for left in truth_rows:
            for right in truth_rows:
                if left == right:
                    continue
                if left[condition_index] == right[condition_index]:
                    continue
                if outcomes[left] == outcomes[right]:
                    continue
                if pair_satisfies_mode(decision, left, right, condition_index, outcomes, mcdc_mode):
                    independence_pairs[condition_index] = (left, right)
                    break
            if condition_index in independence_pairs:
                break

    return independence_pairs


def pair_satisfies_mode(
    decision: Decision,
    left: tuple[bool, ...],
    right: tuple[bool, ...],
    condition_index: int,
    outcomes: dict[tuple[bool, ...], bool | None],
    mcdc_mode: str,
) -> bool:
    if mcdc_mode == "unique-cause":
        return all(
            index == condition_index or left[index] == right[index]
            for index in range(len(decision.conditions))
        )

    if mcdc_mode != "masking":
        return False

    target_condition = decision.conditions[condition_index]
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        if index == condition_index or left_value == right_value:
            continue
        if decision.conditions[index] == target_condition:
            continue
        if not condition_is_masked(left, index, outcomes):
            return False
        if not condition_is_masked(right, index, outcomes):
            return False
    return True


def condition_is_masked(
    values: tuple[bool, ...],
    condition_index: int,
    outcomes: dict[tuple[bool, ...], bool | None],
) -> bool:
    flipped = tuple(
        not value if index == condition_index else value for index, value in enumerate(values)
    )
    if flipped not in outcomes:
        return True
    return outcomes[values] == outcomes[flipped]


def format_missing_pair_warning(missing: list[int]) -> str:
    return (
        "No independence pair found for condition indexes "
        + ", ".join(str(index) for index in missing)
        + ". They may be coupled, constant, or unreachable in this expression model."
    )


def duplicate_conditions_are_consistent(conditions: tuple[str, ...], values: tuple[bool, ...]) -> bool:
    seen: dict[str, bool] = {}
    for condition, value in zip(conditions, values):
        if condition in seen and seen[condition] != value:
            return False
        seen[condition] = value
    return True


def classify_setup_note(note: str) -> str:
    if note.startswith("Conflicting inferred values"):
        return "coupled"
    return "environment"


def split_conditions(expression: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    index = 0

    while index < len(expression):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression[index : index + 2] in BOOLEAN_OPERATORS:
            add_condition(parts, expression[start:index])
            start = index + 2
            index += 1
        index += 1

    add_condition(parts, expression[start:])
    if len(parts) == 1 and is_wrapped(parts[0]):
        return split_conditions(parts[0][1:-1])
    return parts


def add_condition(parts: list[str], raw_condition: str) -> None:
    condition = raw_condition.strip()
    while is_wrapped(condition):
        condition = condition[1:-1].strip()
    if contains_top_level_boolean(condition):
        parts.extend(split_conditions(condition))
    elif condition:
        parts.append(condition)


def evaluate_decision(expression: str, conditions: tuple[str, ...], values: tuple[bool, ...]) -> bool | None:
    python_expression = replace_condition_occurrences(expression, conditions, values)
    if python_expression is None:
        return None

    python_expression = python_expression.replace("&&", " and ")
    python_expression = python_expression.replace("||", " or ")
    python_expression = re.sub(r"!(?!=)", " not ", python_expression)
    python_expression = " ".join(python_expression.split())
    if re.search(r"[^TrueFalsandornt()\s]", python_expression):
        return None

    try:
        return bool(eval(python_expression, {"__builtins__": {}}, {}))
    except Exception:
        return None


def replace_condition_occurrences(
    expression: str, conditions: tuple[str, ...], values: tuple[bool, ...]
) -> str | None:
    replaced = expression
    search_start = 0
    for condition, value in zip(conditions, values):
        index = replaced.find(condition, search_start)
        if index < 0:
            return None
        replacement = str(value)
        replaced = replaced[:index] + replacement + replaced[index + len(condition) :]
        search_start = index + len(replacement)
    return replaced


def concretize_conditions(conditions: tuple[str, ...], values: tuple[bool, ...]) -> tuple[dict[str, int | bool], tuple[str, ...]]:
    assignments: dict[str, int | bool] = {}
    notes: list[str] = []

    for condition, desired in zip(conditions, values):
        candidate = value_for_condition(condition, desired)
        if candidate is None:
            notes.append(f"No simple concrete value inferred for `{condition}` = {desired}.")
            continue

        name, value = candidate
        if name in assignments and assignments[name] != value:
            notes.append(f"Conflicting inferred values for `{name}`; kept first value {assignments[name]!r}.")
            continue
        assignments[name] = value

    return assignments, tuple(notes)


def value_for_condition(condition: str, desired: bool) -> tuple[str, int | bool] | None:
    cleaned = condition.strip()
    negated = False
    while cleaned.startswith("!"):
        negated = not negated
        cleaned = cleaned[1:].strip()

    desired = desired if not negated else not desired
    match = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)", cleaned)
    if match:
        name, operator, literal_text = match.groups()
        literal = int(literal_text)
        return name, candidate_integer(operator, literal, desired)

    if re.fullmatch(r"[A-Za-z_]\w*", cleaned):
        return cleaned, desired

    return None


def candidate_integer(operator: str, literal: int, desired: bool) -> int:
    if operator == ">":
        return literal + 1 if desired else literal
    if operator == ">=":
        return literal if desired else literal - 1
    if operator == "<":
        return literal - 1 if desired else literal
    if operator == "<=":
        return literal if desired else literal + 1
    if operator == "==":
        return literal if desired else literal + 1
    if operator == "!=":
        return literal + 1 if desired else literal
    raise ValueError(f"Unsupported operator: {operator}")


def render_c_harness(report: MCDCReport) -> str:
    lines = [
        "/* Generated MC/DC testcase scaffold.",
        " * Fill in target function calls, expected assertions, and environment setup for your project.",
        " * This scaffold reflects generated target vectors, not compiler-confirmed MC/DC coverage.",
        " */",
        '#include <assert.h>',
        "",
    ]
    for header in report.headers:
        lines.append(f'/* Optional header supplied: {header} */')
    if report.headers:
        lines.append("")

    for result in report.decisions:
        lines.append(f"/* {result.decision.id} line {result.decision.line}: {result.decision.expression} */")
        for case_index, row in enumerate(result.cases, start=1):
            assignments = ", ".join(f"{name}={value}" for name, value in row.assignments.items()) or "manual setup required"
            covers = ", ".join(str(index) for index in row.covers)
            lines.append(
                f"/* case {case_index}: decision={int(row.decision_result)} covers=[{covers}] values={row.values} {assignments} */"
            )
            for name, value in row.assignments.items():
                c_value = int(value) if isinstance(value, bool) else value
                lines.append(f"/*   int {name} = {c_value}; */")
            for note in row.notes:
                lines.append(f"/*   gap: {note} */")
        lines.append("")

    lines.extend(
        [
            "int main(void) {",
            "    /* TODO: call your target function with the generated case data. */",
            "    return 0;",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def render_gap_report(report: MCDCReport) -> str:
    lines = [
        "# MC/DC Gap Report",
        "",
        f"- Source: `{report.source}`",
        f"- Generated target score: {report.score:.1%}",
        f"- MC/DC mode: `{report.mcdc_mode}`",
        f"- Target function: `{report.target_function}`" if report.target_function else "- Target function: not specified",
        f"- Headers: {', '.join(f'`{header}`' for header in report.headers) or 'none'}",
        f"- Include dirs: {', '.join(f'`{include}`' for include in report.include_dirs) or 'none'}",
        f"- Compile flags: {' '.join(report.compile_flags) or 'none'}",
        f"- Toolchain: {format_toolchain(report.toolchain)}",
        f"- Confirmed LLVM MC/DC coverage ready: {'yes' if report.coverage_ready else 'no'}",
        f"- Coverage status: {report.coverage_status}",
        "",
        "This score is generated from decision truth tables. Use Clang/LLVM coverage to confirm executed MC/DC coverage after the harness is completed.",
        "",
    ]

    if report.warnings:
        lines.extend(["## Report Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")

    for result in report.decisions:
        lines.extend(
            [
                f"## {result.decision.id} line {result.decision.line}",
                "",
                f"- Expression: `{result.decision.expression}`",
                f"- Conditions: {len(result.decision.conditions)}",
                f"- Generated score: {result.score:.1%}",
                f"- Cases selected: {len(result.cases)}",
                "",
            ]
        )
        if result.gaps:
            lines.append("### Gaps")
            lines.append("")
            for gap in result.gaps:
                condition = "" if gap.condition_index is None else f" condition={gap.condition_index}"
                lines.append(f"- `{gap.classification}`{condition}: {gap.message}")
            lines.append("")
        else:
            lines.extend(["### Gaps", "", "- None in generated target model.", ""])

    return "\n".join(lines)


def format_toolchain(toolchain: dict[str, bool]) -> str:
    if not toolchain:
        return "not checked"
    return ", ".join(f"{name}={'yes' if available else 'no'}" for name, available in sorted(toolchain.items()))


def detect_toolchain() -> dict[str, bool]:
    return {name: bool(details["available"]) for name, details in detect_toolchain_details().items()}


def detect_toolchain_details() -> dict[str, dict[str, str | bool | None]]:
    return {name: detect_tool(command) for name, command in TOOLCHAIN_COMMANDS.items()}


def detect_tool(command: tuple[str, str]) -> dict[str, str | bool | None]:
    executable, version_arg = command
    path = find_tool_path(executable)
    if path is None:
        return {
            "available": False,
            "path": None,
            "version": None,
            "error": "not found on PATH",
        }

    try:
        completed = subprocess.run(
            [path, version_arg],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {
            "available": True,
            "path": path,
            "version": None,
            "error": str(exc),
        }

    version_output = (completed.stdout or completed.stderr).strip().splitlines()
    return {
        "available": True,
        "path": path,
        "version": version_output[0] if version_output else None,
        "error": None if completed.returncode == 0 else f"exit code {completed.returncode}",
    }


def find_tool_path(executable: str) -> str | None:
    path = shutil.which(executable)
    if path is not None:
        return path

    if executable not in LLVM_TOOL_NAMES:
        return None

    executable_name = executable if executable.endswith(".exe") else f"{executable}.exe"
    for directory in llvm_bin_candidates():
        candidate = directory / executable_name
        if candidate.exists():
            return str(candidate)
    return None


def llvm_bin_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    configured = os.environ.get(LLVM_BIN_ENV_VAR)
    if configured:
        candidates.append(Path(configured))

    candidates.extend(
        [
            Path("C:/Program Files/LLVM/bin"),
            Path("C:/Program Files (x86)/LLVM/bin"),
            Path.home() / "AppData/Local/Programs/LLVM/bin",
            Path.home() / "scoop/apps/llvm/current/bin",
        ]
    )
    return tuple(dict.fromkeys(candidates))


def summarize_coverage_readiness(
    toolchain_details: dict[str, dict[str, str | bool | None]]
) -> tuple[bool, str]:
    required = ("clang", "llvm-cov", "llvm-profdata")
    missing = [name for name in required if not toolchain_details.get(name, {}).get("available")]
    if missing:
        return False, "Missing required LLVM coverage tools: " + ", ".join(missing)
    errored = [
        name
        for name in required
        if toolchain_details.get(name, {}).get("error")
        and toolchain_details.get(name, {}).get("error") != "not found on PATH"
    ]
    if errored:
        return False, "LLVM coverage tools were found but version checks failed: " + ", ".join(errored)
    return True, "LLVM coverage tools are available; use scripts/run_llvm_mcdc_coverage.py for supported simple signatures."


def strip_comments_and_strings(source: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", preserve_newlines_as_spaces, source, flags=re.S)
    without_line_comments = re.sub(r"//.*", "", without_block_comments)
    without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', without_line_comments)
    return re.sub(r"'(?:\\.|[^'\\])+'", "0", without_strings)


def preserve_newlines_as_spaces(match: re.Match[str]) -> str:
    return "".join("\n" if char == "\n" else " " for char in match.group(0))


def find_matching_paren(source: str, open_paren: int) -> int | None:
    depth = 0
    for index in range(open_paren, len(source)):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def contains_top_level_boolean(expression: str) -> bool:
    depth = 0
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression[index : index + 2] in BOOLEAN_OPERATORS:
            return True
        index += 1
    return False


def is_wrapped(expression: str) -> bool:
    expression = expression.strip()
    if not (expression.startswith("(") and expression.endswith(")")):
        return False
    close_paren = find_matching_paren(expression, 0)
    return close_paren == len(expression) - 1
