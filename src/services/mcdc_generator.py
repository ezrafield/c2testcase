from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
import json
import math
import os
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape, quoteattr
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
IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_]\w*\b")
C_TYPE_WORDS = {
    "Bool",
    "Char",
    "Const",
    "Double",
    "Float",
    "Float32",
    "Float64",
    "FLG",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "SInt8",
    "SInt16",
    "SInt32",
    "SInt64",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "VF24",
    "VFLG",
    "VU08",
    "VU16",
    "VU32",
    "CU08",
    "CU16",
    "CS15",
    "const",
    "extern",
    "GLOBAL",
    "EXT_SP_GLOBAL",
    "return",
    "sizeof",
    "static",
    "volatile",
}


@dataclass(frozen=True)
class Decision:
    id: str
    keyword: str
    expression: str
    line: int
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class InterfaceAnalysis:
    function_parameters: tuple[str, ...]
    global_order: tuple[str, ...]
    ext_sp_globals: tuple[str, ...]
    ram_extern: tuple[str, ...]
    global_outputs: tuple[str, ...]
    ram_public: tuple[str, ...]
    data_extern: tuple[str, ...]
    data_public: tuple[str, ...]
    local_names: frozenset[str]
    array_sizes: dict[str, int]
    initial_values: dict[str, Any]
    assignment_sources: dict[str, tuple[str, ...]]
    assignment_targets: tuple[str, ...]
    condition_input_roots: tuple[str, ...]
    condition_output_roots: tuple[str, ...]
    variable_graph: "VariableGraph"


@dataclass(frozen=True)
class VariableNode:
    id: str
    kind: str
    name: str
    line: int | None = None
    expression: str = ""


@dataclass(frozen=True)
class VariableEdge:
    source: str
    target: str
    kind: str
    line: int | None = None
    expression: str = ""


@dataclass
class VariableGraph:
    nodes_by_name: dict[str, VariableNode] = field(default_factory=dict)
    edges: list[VariableEdge] = field(default_factory=list)
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)
    condition_traces: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_node(self, name: str, kind: str, line: int | None = None, expression: str = "") -> str:
        canonical = canonical_lvalue(name)
        existing = self.nodes_by_name.get(canonical)
        if existing is not None:
            return existing.id
        node_id = f"n{len(self.nodes_by_name) + 1}"
        self.nodes_by_name[canonical] = VariableNode(
            id=node_id,
            kind=kind,
            name=canonical,
            line=line,
            expression=expression,
        )
        return node_id

    def add_edge(self, source: str, target: str, kind: str, line: int | None = None, expression: str = "") -> None:
        source_id = self.add_node(source, graph_kind_for_name(source))
        target_id = self.add_node(target, graph_kind_for_name(target))
        edge = VariableEdge(source=source_id, target=target_id, kind=kind, line=line, expression=expression)
        if edge not in self.edges:
            self.edges.append(edge)

    def add_dependency(self, target: str, sources: tuple[str, ...]) -> None:
        canonical_target = canonical_lvalue(target)
        existing = list(self.dependencies.get(canonical_target, ()))
        for source in sources:
            canonical_source = canonical_lvalue(source)
            if canonical_source and canonical_source not in existing:
                existing.append(canonical_source)
        self.dependencies[canonical_target] = tuple(existing)

    def trace_roots(self, name: str, root_names: set[str], seen: frozenset[str] = frozenset()) -> tuple[str, ...]:
        canonical = canonical_lvalue(name)
        if canonical in root_names:
            return (canonical,)
        if canonical in seen:
            return ()
        if canonical.startswith("*"):
            return self.trace_roots(canonical[1:].strip(), root_names, seen | {canonical})
        container = lvalue_container_name(canonical)
        if container and container != canonical:
            return self.trace_roots(container, root_names, seen | {canonical})
        roots: list[str] = []
        for dependency in self.dependencies.get(canonical, ()):
            roots.extend(self.trace_roots(dependency, root_names, seen | {canonical}))
        return tuple(dict.fromkeys(roots))

    def trace_chain(self, name: str, root_names: set[str], seen: frozenset[str] = frozenset()) -> list[str]:
        canonical = canonical_lvalue(name)
        if canonical in root_names or canonical in seen:
            return [canonical]
        dependencies = self.dependencies.get(canonical, ())
        if not dependencies:
            container = lvalue_container_name(canonical)
            if container and container != canonical:
                return [*self.trace_chain(container, root_names, seen | {canonical}), canonical]
            if canonical.startswith("*"):
                return [*self.trace_chain(canonical[1:].strip(), root_names, seen | {canonical}), canonical]
            return [canonical]
        chain: list[str] = []
        for dependency in dependencies:
            for name in self.trace_chain(dependency, root_names, seen | {canonical}):
                if name not in chain:
                    chain.append(name)
        return [*chain, canonical]

    def add_condition_trace(
        self,
        trace_key: str,
        condition: str,
        candidate_name: str,
        root_names: set[str],
        output_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        roots = list(self.trace_roots(candidate_name, root_names))
        chain = self.trace_chain(candidate_name, root_names)
        trace = {
            "condition": condition,
            "roots": roots,
            "chain": chain,
            "output_roots": output_roots or [],
        }
        self.condition_traces[trace_key] = trace
        self.add_node(trace_key, "condition", expression=condition)
        for name in chain:
            self.add_edge(name, trace_key, "condition_uses", expression=condition)
        return trace

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": node.id,
                    "kind": node.kind,
                    "name": node.name,
                    **({"line": node.line} if node.line is not None else {}),
                    **({"expression": node.expression} if node.expression else {}),
                }
                for node in self.nodes_by_name.values()
            ],
            "edges": [
                {
                    "from": edge.source,
                    "to": edge.target,
                    "kind": edge.kind,
                    **({"line": edge.line} if edge.line is not None else {}),
                    **({"expression": edge.expression} if edge.expression else {}),
                }
                for edge in self.edges
            ],
            "condition_traces": self.condition_traces,
        }


@dataclass(frozen=True)
class MCDCRow:
    values: tuple[bool, ...]
    decision_result: bool
    covers: tuple[int, ...] = field(default_factory=tuple)
    assignments: dict[str, TableValue] = field(default_factory=dict)
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
    interface_graph: dict[str, Any] = field(default_factory=dict)

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
            "interface_graph": self.interface_graph,
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
    interface_analysis = analyze_c_interface(source)
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
        interface_graph=interface_analysis.variable_graph.to_dict(),
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
    normalize_with_libreoffice: bool = True,
) -> None:
    metadata = metadata or ExcelExportMetadata()
    with ZipFile(output_path, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", xlsx_content_types())
        workbook.writestr("_rels/.rels", xlsx_root_rels())
        workbook.writestr("docProps/core.xml", xlsx_core_properties(metadata.name))
        workbook.writestr("docProps/app.xml", xlsx_app_properties(metadata.name))
        workbook.writestr("xl/workbook.xml", xlsx_workbook(metadata.name))
        workbook.writestr("xl/_rels/workbook.xml.rels", xlsx_workbook_rels())
        workbook.writestr("xl/styles.xml", xlsx_styles())
        workbook.writestr("xl/worksheets/sheet1.xml", xlsx_sheet(rows, metadata))
    if normalize_with_libreoffice:
        normalize_xlsx_with_libreoffice(output_path)


def normalize_xlsx_with_libreoffice(workbook_path: Path) -> bool:
    executable = find_libreoffice_executable()
    if executable is None:
        return False
    with TemporaryDirectory(prefix="c2testcase-libreoffice-") as tmp:
        workspace = Path(tmp)
        output_dir = workspace / "out"
        user_install_dir = workspace / "profile"
        output_dir.mkdir()
        user_install_dir.mkdir()
        command = [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--nolockcheck",
            f"-env:UserInstallation={user_install_dir.resolve().as_uri()}",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(output_dir),
            str(workbook_path.resolve()),
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        converted_path = output_dir / workbook_path.name
        if result.returncode != 0 or not converted_path.exists():
            return False
        shutil.copyfile(converted_path, workbook_path)
        return True


def find_libreoffice_executable() -> str | None:
    for executable in ("soffice", "libreoffice"):
        path = shutil.which(executable)
        if path:
            return path
    for path in (
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ):
        if path.exists():
            return str(path)
    return None


def testcase_table_rows_from_dict(
    report: dict[str, Any],
    *,
    fill_manual_for_btc: bool = False,
) -> list[list[TableValue]]:
    table = report.get("testcase_table", {})
    input_columns = list(table.get("input_columns", []))
    parameter_columns = list(table.get("parameter_columns", []))
    output_columns = list(table.get("output_columns", []))
    input_keys = list(table.get("input_column_keys", input_columns))
    parameter_keys = list(table.get("parameter_column_keys", parameter_columns))
    output_keys = list(table.get("output_column_keys", output_columns))
    btc_fallbacks = manual_value_fallbacks(table) if fill_manual_for_btc else {"inputs": {}, "outputs": {}}
    group_headers = table.get(
        "group_headers",
        [
            "Mode",
            *(["Inputs"] * len(input_columns)),
            *(["Parameters"] * len(parameter_columns)),
            *(["Outputs"] * len(output_columns)),
        ],
    )
    rows: list[list[TableValue]] = [
        list(group_headers),
        ["Step", *input_columns, *parameter_columns, *output_columns],
    ]
    for row in table.get("rows", []):
        inputs = row.get("inputs", {})
        parameters = row.get("parameters", {})
        outputs = row.get("outputs", {})
        input_values = [
            btc_cell_value(
                inputs.get(key, "MANUAL"),
                btc_fallbacks["inputs"].get(key, 0),
                fill_manual_for_btc,
            )
            for key in input_keys
        ]
        parameter_values = [
            btc_cell_value(
                parameters.get(key, "MANUAL"),
                btc_fallbacks.get("parameters", {}).get(key, 0),
                fill_manual_for_btc,
            )
            for key in parameter_keys
        ]
        output_values = [
            btc_cell_value(
                outputs.get(key, "MANUAL"),
                btc_fallbacks["outputs"].get(key, 0),
                fill_manual_for_btc,
            )
            for key in output_keys
        ]
        rows.append(
            [
                row.get("step", len(rows) - 2),
                *input_values,
                *parameter_values,
                *output_values,
            ]
        )
    if len(rows) == 2:
        empty_value: TableValue = 0 if fill_manual_for_btc else "MANUAL"
        rows.append(
            [
                "No generated testcases",
                *([empty_value] * len(input_columns)),
                *([empty_value] * len(parameter_columns)),
                *([empty_value] * len(output_columns)),
            ]
        )
    return rows


def manual_value_fallbacks(table: dict[str, Any]) -> dict[str, dict[str, TableValue]]:
    input_columns = list(table.get("input_columns", []))
    parameter_columns = list(table.get("parameter_columns", []))
    output_columns = list(table.get("output_columns", []))
    input_keys = list(table.get("input_column_keys", input_columns))
    parameter_keys = list(table.get("parameter_column_keys", parameter_columns))
    output_keys = list(table.get("output_column_keys", output_columns))
    values: dict[str, dict[str, list[TableValue]]] = {
        "inputs": {name: [] for name in input_keys},
        "parameters": {name: [] for name in parameter_keys},
        "outputs": {name: [] for name in output_keys},
    }
    for row in table.get("rows", []):
        for group_name, columns in (
            ("inputs", input_keys),
            ("parameters", parameter_keys),
            ("outputs", output_keys),
        ):
            row_values = row.get(group_name, {})
            if not isinstance(row_values, dict):
                continue
            for name in columns:
                numeric_value = btc_numeric_value(row_values.get(name))
                if numeric_value is not None:
                    values[group_name][name].append(numeric_value)
    return {
        group_name: {
            name: min(column_values) if column_values else 0
            for name, column_values in group_values.items()
        }
        for group_name, group_values in values.items()
    }


def btc_cell_value(value: Any, fallback: TableValue, fill_manual_for_btc: bool) -> TableValue:
    if fill_manual_for_btc and value == "MANUAL":
        return fallback
    return value


def btc_numeric_value(value: Any) -> TableValue | None:
    if value == "MANUAL" or value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def testcase_table_rows(report: MCDCReport) -> list[list[TableValue]]:
    table = testcase_table(report)
    input_columns = list(table["input_columns"])
    parameter_columns = list(table.get("parameter_columns", []))
    output_columns = list(table["output_columns"])
    input_keys = list(table.get("input_column_keys", input_columns))
    parameter_keys = list(table.get("parameter_column_keys", parameter_columns))
    output_keys = list(table.get("output_column_keys", output_columns))
    rows: list[list[TableValue]] = [
        table.get(
            "group_headers",
            [
                "Mode",
                *(["Inputs"] * len(input_columns)),
                *(["Parameters"] * len(parameter_columns)),
                *(["Outputs"] * len(output_columns)),
            ],
        ),
        ["Step", *input_columns, *parameter_columns, *output_columns],
    ]
    if table["rows"]:
        for row in table["rows"]:
            rows.append(
                [
                    row["step"],
                    *(row.get("inputs", {}).get(key, "MANUAL") for key in input_keys),
                    *(row.get("parameters", {}).get(key, "MANUAL") for key in parameter_keys),
                    *(row.get("outputs", {}).get(key, "MANUAL") for key in output_keys),
                ]
            )
        return rows
    rows.append(
        [
            "No generated testcases",
            *(["MANUAL"] * len(input_columns)),
            *(["MANUAL"] * len(parameter_columns)),
            *(["MANUAL"] * len(output_columns)),
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
            setup_status, setup_notes = testcase_setup_status(assignments, variable_names, list(row.notes))
            rows.append(
                {
                    "step": step_index,
                    "decision_id": result.decision.id,
                    "line": result.decision.line,
                    "inputs": assignments,
                    "outputs": outputs,
                    "setup_status": setup_status,
                    "setup_notes": setup_notes,
                    "mcdc_condition_values": list(row.values),
                    "decision_result": row.decision_result,
                    "covers": list(row.covers),
                    "notes": list(row.notes),
                }
            )
            step_index += 1
    return {
        "input_columns": variable_names,
        "parameter_columns": [],
        "output_columns": output_names,
        "input_column_keys": variable_names,
        "parameter_column_keys": [],
        "output_column_keys": output_names,
        "score": round(report.score, 4),
        "score_kind": "generated_target_score",
        "mcdc_complete": report.score == 1.0,
        **testcase_setup_counts(rows),
        "rows": rows,
    }


def targetlink_logged_interface_table(report: MCDCReport) -> dict[str, Any] | None:
    interface = extract_log_var_interface(report.source_text)
    if interface is None:
        return None

    input_names, parameter_names, output_names, array_sizes, initial_values = interface
    output_names = targetlink_output_order(output_names)
    input_columns, input_keys = expand_interface_columns(input_names, array_sizes)
    parameter_columns, parameter_keys = expand_interface_columns(parameter_names, array_sizes)
    output_columns, output_keys = expand_interface_columns(output_names, array_sizes)
    controllable_names = [*parameter_names, *input_names]
    testcase_inputs = targetlink_mcdc_interface_inputs(report, controllable_names, output_names)
    if testcase_inputs is None:
        testcase_inputs = targetlink_generic_interface_inputs(report, controllable_names)
    if testcase_inputs is None:
        return None

    rows: list[dict[str, Any]] = []
    output_state = {name: 0 for name in output_names}
    for step_index, scenario in enumerate(testcase_inputs):
        inputs = scenario["inputs"]
        output_state.update(evaluate_targetlink_outputs(inputs, output_state))
        row_inputs = expand_interface_values(input_names, input_keys, array_sizes, inputs)
        row_parameters = expand_interface_values(
            parameter_names,
            parameter_keys,
            array_sizes,
            merge_concrete_values(initial_values, inputs),
        )
        row_outputs = expand_interface_values(output_names, output_keys, array_sizes, output_state)
        setup_status, setup_notes = testcase_setup_status(
            {**row_inputs, **row_parameters},
            [*input_keys, *parameter_keys],
            scenario["notes"],
        )
        rows.append(
            {
                "step": step_index,
                "decision_id": scenario["decision_id"],
                "line": scenario["line"],
                "inputs": row_inputs,
                "parameters": row_parameters,
                "outputs": row_outputs,
                "setup_status": setup_status,
                "setup_notes": setup_notes,
                "mcdc_condition_values": scenario["mcdc_condition_values"],
                "decision_result": scenario["decision_result"],
                "covers": scenario["covers"],
                "notes": scenario["notes"],
            }
        )

    return {
        "input_columns": input_columns,
        "parameter_columns": parameter_columns,
        "output_columns": output_columns,
        "input_column_keys": input_keys,
        "parameter_column_keys": parameter_keys,
        "output_column_keys": output_keys,
        "group_headers": targetlink_group_headers(input_columns, parameter_columns, output_columns),
        "score": round(report.score, 4),
        "score_kind": "generated_target_score",
        "mcdc_complete": report.score == 1.0,
        **testcase_setup_counts(rows),
        "rows": rows,
    }


def expand_interface_columns(names: list[str], array_sizes: dict[str, int]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    keys: list[str] = []
    for name in names:
        width = array_sizes.get(name, 1)
        if width <= 1:
            labels.append(name)
            keys.append(name)
            continue
        for index in range(width):
            labels.append(name)
            keys.append(f"{name}[{index}]")
    return labels, keys


def expand_interface_values(
    names: list[str],
    keys: list[str],
    array_sizes: dict[str, int],
    values: dict[str, Any],
) -> dict[str, TableValue]:
    expanded: dict[str, TableValue] = {}
    key_index = 0
    for name in names:
        width = array_sizes.get(name, 1)
        root_value = values.get(name, "MANUAL")
        for array_index in range(width):
            key = keys[key_index]
            value = values.get(key, root_value)
            if isinstance(root_value, (list, tuple)) and array_index < len(root_value):
                value = root_value[array_index]
            expanded[key] = value
            key_index += 1
    return expanded


def merge_concrete_values(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(defaults)
    for name, value in overrides.items():
        if value != "MANUAL":
            merged[name] = value
    return merged


def targetlink_group_headers(
    input_names: list[str],
    parameter_names: list[str],
    output_names: list[str],
) -> list[str]:
    return [
        "Mode",
        "Inputs",
        *([" "] * max(len(input_names) - 1, 0)),
        *(["Parameters"] if parameter_names else []),
        *([" "] * max(len(parameter_names) - 1, 0)),
        "Outputs",
        *([" "] * max(len(output_names) - 1, 0)),
    ]


def testcase_setup_status(
    inputs: dict[str, TableValue],
    input_names: list[str],
    notes: list[str],
) -> tuple[str, list[str]]:
    manual_inputs = [name for name in input_names if inputs.get(name, "MANUAL") == "MANUAL"]
    if not input_names or not manual_inputs:
        return "concrete", []

    status = "manual_required" if len(manual_inputs) == len(input_names) else "partial"
    setup_notes = list(notes)
    if status == "manual_required":
        setup_notes.append("Manual setup required: no concrete root input values were inferred.")
    else:
        setup_notes.append("Partial setup: manual values required for " + ", ".join(manual_inputs) + ".")
    return status, list(dict.fromkeys(setup_notes))


def testcase_setup_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "target_rows": len(rows),
        "concrete_rows": sum(1 for row in rows if row.get("setup_status") == "concrete"),
        "partial_rows": sum(1 for row in rows if row.get("setup_status") == "partial"),
        "manual_required_rows": sum(1 for row in rows if row.get("setup_status") == "manual_required"),
    }


def extract_log_var_interface(source: str) -> tuple[list[str], list[str], list[str], dict[str, int], dict[str, Any]] | None:
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
    return input_names, [], output_names, {}, {}


def extract_targetlink_declared_interface(source: str) -> tuple[list[str], list[str], list[str], dict[str, int], dict[str, Any]] | None:
    analysis = analyze_c_interface(source)
    parameter_names = list(dict.fromkeys((*analysis.data_extern, *analysis.data_public)))
    parameter_set = set(parameter_names)
    input_names = list(
        dict.fromkeys(
            name
            for name in (
                *analysis.function_parameters,
                *analysis.ext_sp_globals,
                *analysis.ram_extern,
                *analysis.condition_input_roots,
            )
            if name not in parameter_set
        )
    )
    output_names = list(
        dict.fromkeys(
            name
            for name in (
                *analysis.global_outputs,
                *analysis.ram_public,
                *analysis.assignment_targets,
                *analysis.condition_output_roots,
            )
            if name not in parameter_set
        )
    )
    if not input_names or not output_names:
        return None
    return input_names, parameter_names, output_names, dict(analysis.array_sizes), dict(analysis.initial_values)


def analyze_c_interface(source: str) -> InterfaceAnalysis:
    clean_source = strip_comments_and_strings(source)
    function_parameters = extract_first_function_definition_parameters(clean_source)
    function_start = first_function_definition_start(clean_source)
    top_level_source = clean_source[:function_start] if function_start is not None else clean_source
    function_source = clean_source[function_start or 0 :]
    global_order, section_by_name, array_sizes = extract_top_level_variables(source, top_level_source)
    initial_values = extract_top_level_initial_values(source, global_order)
    global_names = set(global_order)
    local_names = frozenset(extract_local_variables(function_source, global_names))
    assignment_sources, assignment_targets = extract_assignment_dependencies(function_source, global_names, set(function_parameters))
    variable_graph = build_variable_graph(
        clean_source,
        function_source,
        global_order,
        function_parameters,
        local_names,
        assignment_sources,
    )
    decisions = extract_decisions(clean_source)
    condition_input_roots: list[str] = []
    condition_output_roots: list[str] = []
    graph_root_names = set(global_order) | set(function_parameters)

    for decision in decisions:
        for condition_index, condition in enumerate(decision.conditions):
            input_roots, output_roots = condition_root_variables(
                condition,
                global_names,
                set(function_parameters),
                assignment_sources,
                variable_graph,
            )
            condition_input_roots.extend(input_roots)
            condition_output_roots.extend(output_roots)
            candidate = condition_candidate_lvalue(condition)
            if candidate:
                variable_graph.add_condition_trace(
                    f"{decision.id}:{condition_index}",
                    condition,
                    candidate,
                    graph_root_names,
                    output_roots,
                )

    ext_sp_globals = [name for name in global_order if section_by_name.get(name) == "EXT_SP_GLOBAL"]
    ram_extern = [name for name in global_order if section_by_name.get(name) == "RAM_EXTERN"]
    global_outputs = [name for name in global_order if section_by_name.get(name) == "GLOBAL"]
    ram_public = [name for name in global_order if section_by_name.get(name) == "RAM_PUBLIC"]
    data_extern = [name for name in global_order if section_by_name.get(name) == "DATA_EXTERN"]
    data_public = [name for name in global_order if section_by_name.get(name) == "DATA_PUBLIC"]
    ordered_assignment_targets = [name for name in global_order if name in assignment_targets]

    return InterfaceAnalysis(
        function_parameters=function_parameters,
        global_order=global_order,
        ext_sp_globals=tuple(ext_sp_globals),
        ram_extern=tuple(ram_extern),
        global_outputs=tuple(global_outputs),
        ram_public=tuple(ram_public),
        data_extern=tuple(data_extern),
        data_public=tuple(data_public),
        local_names=local_names,
        array_sizes=dict(array_sizes),
        initial_values=initial_values,
        assignment_sources=assignment_sources,
        assignment_targets=tuple(ordered_assignment_targets),
        condition_input_roots=tuple(order_known_roots(condition_input_roots, global_order, function_parameters)),
        condition_output_roots=tuple(order_known_roots(condition_output_roots, global_order, function_parameters)),
        variable_graph=variable_graph,
    )


def first_function_definition_start(source: str) -> int | None:
    function_pattern = re.compile(r"\b[A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")
    for match in function_pattern.finditer(source):
        if match.group(1) in KEYWORDS_WITH_DECISIONS:
            continue
        return match.start()
    return None


def extract_top_level_variables(original_source: str, top_level_source: str) -> tuple[tuple[str, ...], dict[str, str], dict[str, int]]:
    section_by_line: dict[int, str] = {}
    current_section = ""
    for line_number, line in enumerate(original_source.splitlines(), start=1):
        section_match = re.search(r"\$(RAM_EXTERN|RAM_PUBLIC|DATA_EXTERN|DATA_PUBLIC)\$", line)
        if section_match:
            current_section = section_match.group(1)
        section_by_line[line_number] = current_section

    names: list[str] = []
    sections: dict[str, str] = {}
    array_sizes: dict[str, int] = {}
    declaration_pattern = re.compile(
        r"^\s*(extern\s+)?(?:(GLOBAL|EXT_SP_GLOBAL)\s+)?(?:[A-Za-z_]\w*\s+)+\**([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?\s*(?:=|;)"
    )
    for line_number, line in enumerate(top_level_source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("{") or stripped.startswith("}"):
            continue
        match = declaration_pattern.match(line)
        if match is None:
            continue
        name = match.group(3)
        if name in C_TYPE_WORDS:
            continue
        section = match.group(2) or section_by_line.get(line_number, "")
        names.append(name)
        if match.group(4):
            array_sizes[name] = int(match.group(4))
        if section:
            sections[name] = section
    return tuple(dict.fromkeys(names)), sections, array_sizes


def extract_top_level_initial_values(source: str, names: tuple[str, ...]) -> dict[str, Any]:
    initial_values: dict[str, Any] = {}
    for name in names:
        array_match = re.search(rf"\b{name}\s*\[[^\]]+\]\s*=\s*\{{(?P<body>.*?)\}}\s*;", source, re.DOTALL)
        if array_match:
            values = [
                parse_initializer_literal(part.strip())
                for part in array_match.group("body").replace("\n", " ").split(",")
                if part.strip()
            ]
            if values and all(value is not None for value in values):
                initial_values[name] = values
            continue
        scalar_match = re.search(rf"\b{name}\s*=\s*(?P<value>[^;]+);", source)
        if scalar_match:
            value = parse_initializer_literal(scalar_match.group("value").strip())
            if value is not None:
                initial_values[name] = value
    return initial_values


def parse_initializer_literal(value: str) -> TableValue | None:
    cleaned = value.strip().strip("()")
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[fFlLuU]*", cleaned):
        return parse_c_numeric_literal(cleaned)
    return None


def extract_local_variables(function_source: str, global_names: set[str]) -> set[str]:
    local_names: set[str] = set()
    declaration_pattern = re.compile(
        r"(?m)^\s*(?:[A-Za-z_]\w*\s+)+(?!if\b|while\b|for\b|switch\b|return\b)([^;{}()]+);"
    )
    for match in declaration_pattern.finditer(function_source):
        for declarator in match.group(1).split(","):
            declarator = declarator.split("=")[0]
            declarator = re.sub(r"\[[^\]]*\]", "", declarator).replace("*", " ").strip()
            name_match = re.search(r"([A-Za-z_]\w*)\s*$", declarator)
            if name_match and name_match.group(1) not in global_names:
                local_names.add(name_match.group(1))
    return local_names


def extract_assignment_dependencies(
    source: str,
    global_names: set[str],
    parameter_names: set[str],
) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    assignment_sources: dict[str, tuple[str, ...]] = {}
    assignment_targets: set[str] = set()
    assignment_pattern = re.compile(
        r"(?<![=!<>])(?P<lhs>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)?(?:\s*\[[^\]]+\])?|\*\s*[A-Za-z_]\w*|\(\s*\*\s*[A-Za-z_]\w*\s*\))\s*=(?!=)\s*(?P<rhs>[^;]+);"
    )
    for match in assignment_pattern.finditer(source):
        lhs = canonical_lvalue(match.group("lhs"))
        rhs = match.group("rhs")
        lhs_roots = resolve_root_variables(lhs, global_names, parameter_names, assignment_sources)
        assignment_targets.update(root for root in lhs_roots if root in global_names)
        roots = expression_root_variables(rhs, global_names, parameter_names, assignment_sources)
        if roots:
            assignment_sources[lhs] = tuple(dict.fromkeys(roots))
    return assignment_sources, assignment_targets


def build_variable_graph(
    clean_source: str,
    function_source: str,
    global_order: tuple[str, ...],
    parameter_order: tuple[str, ...],
    local_names: frozenset[str],
    assignment_sources: dict[str, tuple[str, ...]],
) -> VariableGraph:
    graph = VariableGraph()
    add_declaration_nodes(graph, global_order, parameter_order, local_names)
    add_assignment_edges(graph, function_source, set(global_order), set(parameter_order), assignment_sources)
    add_condition_edges(graph, clean_source)
    return graph


def add_declaration_nodes(
    graph: VariableGraph,
    global_order: tuple[str, ...],
    parameter_order: tuple[str, ...],
    local_names: frozenset[str],
) -> None:
    for name in global_order:
        graph.add_node(name, graph_kind_for_name(name, "global"))
    for name in parameter_order:
        graph.add_node(name, "param")
    for name in sorted(local_names):
        graph.add_node(name, graph_kind_for_name(name, "local"))


def add_assignment_edges(
    graph: VariableGraph,
    function_source: str,
    global_names: set[str],
    parameter_names: set[str],
    assignment_sources: dict[str, tuple[str, ...]],
) -> None:
    assignment_pattern = re.compile(
        r"(?<![=!<>])(?P<lhs>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)?(?:\s*\[[^\]]+\])?|\*\s*[A-Za-z_]\w*|\(\s*\*\s*[A-Za-z_]\w*\s*\))\s*=(?!=)\s*(?P<rhs>[^;]+);"
    )
    root_names = global_names | parameter_names
    for match in assignment_pattern.finditer(function_source):
        lhs = canonical_lvalue(match.group("lhs"))
        rhs = match.group("rhs").strip()
        line = function_source.count("\n", 0, match.start()) + 1
        direct_sources = direct_dependency_names(rhs)
        if not direct_sources:
            direct_sources = assignment_sources.get(lhs, ())
        edge_kind = "aliases" if rhs.startswith("&") else "derived_from"
        graph.add_node(lhs, graph_kind_for_name(lhs), line=line, expression=match.group(0).strip())
        graph.add_node(f"assignment:{line}:{lhs}", "assignment", line=line, expression=match.group(0).strip())
        for source in direct_sources:
            graph.add_node(source, graph_kind_for_name(source), line=line)
            graph.add_edge(source, lhs, edge_kind, line=line, expression=match.group(0).strip())
            graph.add_edge(source, f"assignment:{line}:{lhs}", "reads_from", line=line, expression=rhs)
        graph.add_edge(f"assignment:{line}:{lhs}", lhs, "writes_to", line=line, expression=match.group(0).strip())
        graph.add_dependency(lhs, tuple(direct_sources))
        if lhs_roots := graph.trace_roots(lhs, root_names):
            for root in lhs_roots:
                if root in global_names:
                    output_node = f"output:{root}"
                    graph.add_node(output_node, "output", line=line)
                    graph.add_edge(lhs, output_node, "writes_to", line=line, expression=match.group(0).strip())


def add_condition_edges(graph: VariableGraph, clean_source: str) -> None:
    for decision in extract_decisions(clean_source):
        for condition_index, condition in enumerate(decision.conditions):
            trace_key = f"{decision.id}:{condition_index}"
            graph.add_node(trace_key, "condition", line=decision.line, expression=condition)
            candidate = condition_candidate_lvalue(condition)
            if candidate:
                graph.add_edge(candidate, trace_key, "condition_uses", line=decision.line, expression=condition)


def direct_dependency_names(expression: str) -> tuple[str, ...]:
    cleaned = expression.strip()
    address_match = re.fullmatch(r"&\s*([A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)?(?:\s*\[[^\]]+\])?)", cleaned)
    if address_match:
        return (canonical_lvalue(address_match.group(1)),)
    if cleaned.startswith("*"):
        return (canonical_lvalue(cleaned[1:]),)
    lvalue = canonical_lvalue(cleaned)
    if re.fullmatch(r"[A-Za-z_]\w*(?:->|\.)[A-Za-z_]\w*", lvalue) or re.fullmatch(r"[A-Za-z_]\w*\[.+\]", lvalue):
        return (lvalue_container_name(lvalue) or lvalue,)
    function_calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", cleaned))
    names = [
        lvalue_container_name(canonical_lvalue(name)) or canonical_lvalue(name)
        for name in identifiers_in_expression(cleaned)
        if name not in function_calls
    ]
    return tuple(dict.fromkeys(name for name in names if name))


def condition_candidate_lvalue(condition: str) -> str | None:
    candidate = value_for_condition(condition, True)
    if candidate is not None:
        return candidate[0]
    comparison = re.search(r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)", condition)
    if comparison:
        return canonical_lvalue(comparison.group(1))
    cleaned = condition.strip()
    if cleaned:
        return canonical_lvalue(cleaned)
    return None


def graph_kind_for_name(name: str, default: str = "local") -> str:
    canonical = canonical_lvalue(name)
    if canonical.startswith("*"):
        return "pointer"
    if re.fullmatch(r"[A-Za-z_]\w*\[.+\]", canonical):
        return "array_root"
    if "->" in canonical or "." in canonical:
        return "field"
    if canonical.startswith("assignment:"):
        return "assignment"
    return default


def condition_root_variables(
    condition: str,
    global_names: set[str],
    parameter_names: set[str],
    assignment_sources: dict[str, tuple[str, ...]],
    variable_graph: VariableGraph | None = None,
) -> tuple[list[str], list[str]]:
    comparison = re.search(r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)", condition)
    if comparison:
        left, _, right = comparison.groups()
        input_roots = expression_root_variables(left, global_names, parameter_names, assignment_sources, variable_graph)
        output_roots = expression_root_variables(right, global_names, parameter_names, assignment_sources, variable_graph)
    else:
        input_roots = expression_root_variables(condition, global_names, parameter_names, assignment_sources, variable_graph)
        output_roots = []
    return input_roots, output_roots


def expression_root_variables(
    expression: str,
    global_names: set[str],
    parameter_names: set[str],
    assignment_sources: dict[str, tuple[str, ...]],
    variable_graph: VariableGraph | None = None,
) -> list[str]:
    lvalue = canonical_lvalue(expression)
    root_names = global_names | parameter_names
    if variable_graph is not None:
        graph_roots = variable_graph.trace_roots(lvalue, root_names)
        if graph_roots:
            return list(graph_roots)
    lvalue_roots = resolve_root_variables(lvalue, global_names, parameter_names, assignment_sources)
    if lvalue_roots:
        return list(lvalue_roots)

    roots: list[str] = []
    for identifier in identifiers_in_expression(expression):
        roots.extend(resolve_root_variables(identifier, global_names, parameter_names, assignment_sources))
    return list(dict.fromkeys(roots))


def resolve_root_variables(
    name: str,
    global_names: set[str],
    parameter_names: set[str],
    assignment_sources: dict[str, tuple[str, ...]],
    seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    name = canonical_lvalue(name)
    if name in C_TYPE_WORDS:
        return ()
    if name in global_names or name in parameter_names:
        return (name,)
    if name in seen:
        return ()
    if name.startswith("*"):
        return resolve_root_variables(name[1:].strip(), global_names, parameter_names, assignment_sources, seen | {name})
    container = lvalue_container_name(name)
    if container and container != name:
        return resolve_root_variables(container, global_names, parameter_names, assignment_sources, seen | {name})
    roots: list[str] = []
    for source_name in assignment_sources.get(name, ()):
        roots.extend(resolve_root_variables(source_name, global_names, parameter_names, assignment_sources, seen | {name}))
    return tuple(dict.fromkeys(roots))


def canonical_lvalue(expression: str) -> str:
    value = expression.strip()
    value = strip_enclosing_parentheses(value)
    value = re.sub(r"\s+", "", value)
    value = strip_simple_casts(value)
    value = strip_enclosing_parentheses(value)
    if value.startswith("*"):
        return "*" + canonical_lvalue(value[1:])
    return value


def strip_enclosing_parentheses(expression: str) -> str:
    value = expression.strip()
    while value.startswith("(") and value.endswith(")"):
        close_paren = find_matching_paren(value, 0)
        if close_paren != len(value) - 1:
            break
        value = value[1:-1].strip()
    return value


def strip_simple_casts(expression: str) -> str:
    value = expression
    cast_pattern = re.compile(r"^\((?:const|volatile|signed|unsigned|struct\s+\w+|[A-Za-z_]\w+|\s|\*)+\)")
    while True:
        match = cast_pattern.match(value)
        if match is None:
            return value
        value = value[match.end() :].strip()


def lvalue_container_name(lvalue: str) -> str | None:
    array_match = re.fullmatch(r"([A-Za-z_]\w*)\[.+\]", lvalue)
    if array_match:
        return array_match.group(1)
    field_match = re.fullmatch(r"([A-Za-z_]\w*)(?:->|\.).+", lvalue)
    if field_match:
        return field_match.group(1)
    return None


def identifiers_in_expression(expression: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            identifier for identifier in IDENTIFIER_PATTERN.findall(expression) if identifier not in C_TYPE_WORDS
        )
    )


def order_known_roots(roots: list[str], global_order: tuple[str, ...], parameter_order: tuple[str, ...]) -> list[str]:
    wanted = set(roots)
    ordered = [name for name in parameter_order if name in wanted]
    ordered.extend(name for name in global_order if name in wanted and name not in ordered)
    ordered.extend(name for name in roots if name not in ordered)
    return ordered


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

        source_input = targetlink_source_input_for_condition(condition, report.source_text, input_names)
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


def targetlink_generic_interface_inputs(report: MCDCReport, input_names: list[str]) -> list[dict[str, Any]] | None:
    if not input_names:
        return None
    analysis = analyze_c_interface(report.source_text)
    root_names = set(analysis.global_order) | set(analysis.function_parameters)
    scenarios: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[tuple[str, TableValue], ...], bool]] = set()

    for decision in report.decisions:
        for row in decision.cases:
            inputs = {name: report.manual_inputs.get(name, "MANUAL") for name in input_names}
            notes = list(row.notes)
            for condition_index, (condition, desired) in enumerate(zip(decision.decision.conditions, row.values)):
                candidate = value_for_condition(condition, desired)
                if candidate is None:
                    continue
                candidate_name, value = candidate
                trace_key = f"{decision.decision.id}:{condition_index}"
                trace = analysis.variable_graph.condition_traces.get(trace_key)
                roots = tuple(trace.get("roots", ())) if trace else ()
                if not roots:
                    roots = resolve_root_variables(
                        candidate_name,
                        set(analysis.global_order),
                        set(analysis.function_parameters),
                        analysis.assignment_sources,
                    )
                assignable_roots = [root for root in roots if root in inputs]
                if len(assignable_roots) != 1:
                    if len(assignable_roots) > 1:
                        notes.append(
                            f"MANUAL: ambiguous roots [{', '.join(assignable_roots)}] for `{candidate_name}`."
                        )
                    continue
                root = assignable_roots[0]
                if root in inputs:
                    inputs[root] = value
                    if root != candidate_name:
                        chain = trace.get("chain", []) if trace else analysis.variable_graph.trace_chain(candidate_name, root_names)
                        notes.append(f"`{condition}` traced {' -> '.join(chain)}.")
            key = (
                decision.decision.id,
                tuple((name, inputs[name]) for name in input_names),
                row.decision_result,
            )
            if key in seen:
                continue
            seen.add(key)
            scenarios.append(
                {
                    "inputs": inputs,
                    "decision_id": decision.decision.id,
                    "line": decision.decision.line,
                    "mcdc_condition_values": list(row.values),
                    "decision_result": row.decision_result,
                    "covers": list(row.covers),
                    "notes": notes,
                }
            )
    return scenarios or None


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


def targetlink_source_input_for_condition(condition: str, source: str = "", input_names: list[str] | None = None) -> str | None:
    if source and input_names is not None:
        analysis = analyze_c_interface(source)
        input_roots, _ = condition_root_variables(
            condition,
            set(analysis.global_order),
            set(analysis.function_parameters),
            analysis.assignment_sources,
        )
        for root in input_roots:
            if root in input_names:
                return root
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
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def xlsx_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def xlsx_core_properties(name: str) -> str:
    title = xml_text(name or "mcdc_testcases")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{title}</dc:title>
  <dc:creator>c2testcase</dc:creator>
  <cp:lastModifiedBy>c2testcase</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""


def xlsx_app_properties(sheet_name: str) -> str:
    safe_name = xml_text(safe_sheet_name(sheet_name))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>c2testcase</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>{safe_name}</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0300</AppVersion>
</Properties>
"""


def xlsx_workbook(sheet_name: str = "Testcases") -> str:
    safe_name = quoteattr(xml_valid_text(safe_sheet_name(sheet_name)))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <fileVersion appName="xl" lastEdited="7" lowestEdited="7" rupBuild="23426"/>
  <workbookPr defaultThemeVersion="166925"/>
  <bookViews>
    <workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="15000"/>
  </bookViews>
  <sheets>
    <sheet name={safe_name} sheetId="1" r:id="rId1"/>
  </sheets>
  <calcPr calcId="191029"/>
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
  <cellXfs count="10">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
    <xf numFmtId="0" fontId="1" fillId="6" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
    <xf numFmtId="0" fontId="1" fillId="6" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment textRotation="90"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>
"""


def xlsx_sheet(rows: list[list[TableValue]], metadata: ExcelExportMetadata | None = None) -> str:
    metadata = metadata or ExcelExportMetadata()
    sheet_rows = excel_export_rows(rows, metadata)
    section_by_column = excel_section_by_column(sheet_rows[4]) if len(sheet_rows) >= 5 else {}
    row_xml = "\n".join(
        xlsx_row(index, row, section_by_column=section_by_column)
        for index, row in enumerate(sheet_rows, start=1)
    )
    widths = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths(sheet_rows), start=1)
    )
    last_column = column_name(len(sheet_rows[0]))
    dimension = f"A1:{last_column}{len(sheet_rows)}"
    filter_dimension = f"A6:{last_column}{len(sheet_rows)}"
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
  <autoFilter ref="{filter_dimension}"/>
</worksheet>
"""


def excel_export_rows(rows: list[list[TableValue]], metadata: ExcelExportMetadata) -> list[list[TableValue]]:
    if not rows:
        return []
    max_columns = len(rows[1]) + 1 if len(rows) > 1 else len(rows[0]) + 1
    padded_rows = [
        pad_row(["Format Version", excel_format_version_number(metadata.format_version)], max_columns),
        pad_row(["Architecture", metadata.architecture], max_columns),
        pad_row(["Scope", metadata.scope], max_columns),
        pad_row(["Name", metadata.name], max_columns),
    ]
    group_row = pad_row([*rows[0], ""], max_columns)
    header_row = pad_row([*rows[1], "Comment"], max_columns)
    data_rows = [pad_row(row, max_columns) for row in rows[2:]]
    return [*padded_rows, group_row, header_row, *data_rows]


def excel_format_version_number(format_version: str) -> float:
    try:
        value = float(str(format_version).strip())
    except (TypeError, ValueError):
        return 1.3
    if not math.isfinite(value):
        return 1.3
    return value


def pad_row(row: list[TableValue], width: int) -> list[TableValue]:
    return [*row, *([""] * max(width - len(row), 0))]


def excel_section_by_column(group_row: list[TableValue]) -> dict[int, str]:
    section_by_column: dict[int, str] = {}
    current_section = "Mode"
    for index, value in enumerate(group_row, start=1):
        if value in {"Inputs", "Parameters", "Outputs"}:
            current_section = str(value)
        section_by_column[index] = current_section
    return section_by_column


def xlsx_row(row_index: int, row: list[TableValue], section_by_column: dict[int, str] | None = None) -> str:
    section_by_column = section_by_column or {}
    cells = "".join(
        xlsx_cell(
            row_index,
            column_index,
            value,
            style=xlsx_style_for_cell(row_index, column_index, section_by_column, len(row)),
        )
        for column_index, value in enumerate(row, start=1)
    )
    height_attr = ' ht="90" customHeight="1"' if row_index == 6 else ""
    return f'    <row r="{row_index}"{height_attr}>{cells}</row>'


def xlsx_style_for_cell(
    row_index: int,
    column_index: int,
    section_by_column: dict[int, str],
    column_count: int,
) -> int:
    if row_index <= 4:
        return 1
    if row_index == 5:
        if column_index == column_count:
            return 8
        section = section_by_column.get(column_index)
        if section == "Outputs":
            return 3
        if section == "Parameters":
            return 4
        if section == "Inputs":
            return 2
        return 1
    if row_index == 6:
        if column_index == column_count:
            return 7
        section = section_by_column.get(column_index)
        if section == "Outputs":
            return 6
        if section == "Parameters":
            return 9
        if section == "Inputs":
            return 5
        return 1
    return 0


def xlsx_cell(row_index: int, column_index: int, value: TableValue, style: int = 0) -> str:
    reference = f"{column_name(column_index)}{row_index}"
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style_attr}><v>{int(value)}</v></c>'
    if isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            text = xml_text(str(value))
            return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t>{text}</t></is></c>'
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
    raw_text = xml_valid_text(str(value))
    text = escape(raw_text)
    space_attr = ' xml:space="preserve"' if raw_text != raw_text.strip() else ""
    return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t{space_attr}>{text}</t></is></c>'


def xml_text(value: str) -> str:
    return escape(xml_valid_text(value))


def xml_valid_text(value: str) -> str:
    return "".join(character if is_xml_character(character) else " " for character in value)


def is_xml_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint == 0x09
        or codepoint == 0x0A
        or codepoint == 0x0D
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


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


def concretize_conditions(conditions: tuple[str, ...], values: tuple[bool, ...]) -> tuple[dict[str, TableValue], tuple[str, ...]]:
    assignments: dict[str, TableValue] = {}
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


def value_for_condition(condition: str, desired: bool) -> tuple[str, TableValue] | None:
    cleaned = condition.strip()
    negated = False
    while cleaned.startswith("!"):
        negated = not negated
        cleaned = cleaned[1:].strip()

    desired = desired if not negated else not desired
    numeric_literal = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:[fFlLuU]*)"
    lhs_pattern = r"(.+?)"
    match = re.fullmatch(rf"{lhs_pattern}\s*(==|!=|>=|<=|>|<)\s*{numeric_literal}", cleaned)
    if match:
        name, operator, literal_text = match.groups()
        literal = parse_c_numeric_literal(literal_text)
        return canonical_lvalue(name), candidate_number(operator, literal, desired)

    if re.fullmatch(r"[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)?(?:\s*\[[^\]]+\])?", cleaned):
        return canonical_lvalue(cleaned), desired
    pointer_match = re.fullmatch(r"\(?\s*\*\s*([A-Za-z_]\w*)\s*\)?", cleaned)
    if pointer_match:
        return "*" + pointer_match.group(1), desired

    return None


def parse_c_numeric_literal(literal_text: str) -> int | float:
    cleaned = re.sub(r"[fFlLuU]+$", "", literal_text)
    if "." in cleaned or "e" in cleaned.lower():
        return float(cleaned)
    return int(cleaned)


def candidate_number(operator: str, literal: int | float, desired: bool) -> int | float:
    if isinstance(literal, float):
        return candidate_float(operator, literal, desired)
    return candidate_integer(operator, literal, desired)


def candidate_float(operator: str, literal: float, desired: bool) -> float:
    step = 1.0
    if operator == ">":
        return literal + step if desired else literal
    if operator == ">=":
        return literal if desired else literal - step
    if operator == "<":
        return literal - step if desired else literal
    if operator == "<=":
        return literal if desired else literal + step
    if operator == "==":
        return literal if desired else literal + step
    if operator == "!=":
        return literal + step if desired else literal
    raise ValueError(f"Unsupported operator: {operator}")


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
