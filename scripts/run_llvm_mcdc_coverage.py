from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.mcdc_generator import evaluate_decision, find_tool_path, generate_mcdc_report, write_report_artifacts


@dataclass(frozen=True)
class FunctionSignature:
    return_type: str
    name: str
    parameters: tuple[tuple[str, str], ...]
    source_path: Path
    constants: dict[str, int] = field(default_factory=dict)
    structs: dict[str, tuple[str, ...]] = field(default_factory=dict)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Clang/LLVM source coverage with MC/DC for simple generated C cases.",
    )
    parser.add_argument("source", type=Path, help="Target .c file.")
    parser.add_argument("--target-function", required=True, help="Function to call from the generated harness.")
    parser.add_argument("--output-dir", type=Path, default=Path("build/llvm-mcdc"), help="Artifact directory.")
    parser.add_argument("--mcdc-mode", default="masking", choices=("unique-cause", "masking", "multicondition"))
    parser.add_argument("--max-conditions", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clang = require_coverage_clang()
    llvm_profdata = require_tool("llvm-profdata")
    llvm_cov = require_tool("llvm-cov")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    report = generate_mcdc_report(
        args.source,
        target_function=args.target_function,
        mcdc_mode=args.mcdc_mode,
        max_conditions=args.max_conditions,
    )
    write_report_artifacts(report, output_dir / "generated")
    harness_report = select_harness_report(args.source, args.target_function, args.mcdc_mode, args.max_conditions, report)

    signature = infer_function_signature(args.source, args.target_function)
    harness = render_executable_harness(signature, harness_report.to_dict())
    harness_path = output_dir / "llvm_mcdc_harness.c"
    harness_path.write_text(harness, encoding="utf-8")

    exe_path = output_dir / "mcdc_runner.exe"
    profraw_path = output_dir / "mcdc.profraw"
    profdata_path = output_dir / "mcdc.profdata"
    coverage_path = output_dir / "llvm_mcdc_report.txt"
    result_path = output_dir / "coverage_result.json"

    compile_command = [
        clang,
        "-fprofile-instr-generate",
        "-fcoverage-mapping",
        "-fcoverage-mcdc",
        str(harness_path),
        "-o",
        str(exe_path),
    ]
    run_command(compile_command, output_dir / "compile.log")

    env = os.environ.copy()
    env["LLVM_PROFILE_FILE"] = str(profraw_path)
    run_command([str(exe_path)], output_dir / "run.log", env=env)
    run_command([llvm_profdata, "merge", "-sparse", str(profraw_path), "-o", str(profdata_path)], output_dir / "profdata.log")

    coverage_command = [
        llvm_cov,
        "show",
        str(exe_path),
        "--instr-profile",
        str(profdata_path),
        "--show-mcdc",
        "--show-mcdc-summary",
        "--show-branch-summary",
    ]
    coverage = run_command(coverage_command, output_dir / "llvm-cov.log")
    coverage_path.write_text(coverage.stdout, encoding="utf-8")
    confirmed_mcdc = extract_confirmed_mcdc_scores(coverage.stdout)
    adjustment = compute_adjusted_mcdc(harness_report.to_dict(), signature, coverage.stdout)

    result = {
        "source": str(args.source),
        "target_function": args.target_function,
        "generated_score": round(report.score, 4),
        "mcdc_mode": args.mcdc_mode,
        "coverage_case_mode": harness_report.mcdc_mode,
        "confirmed_mcdc_decision_scores": confirmed_mcdc,
        "confirmed_mcdc_average": round(sum(confirmed_mcdc) / len(confirmed_mcdc), 4) if confirmed_mcdc else None,
        "adjusted_mcdc_decision_scores": adjustment["adjusted_scores"],
        "adjusted_mcdc_average": adjustment["adjusted_average"],
        "mcdc_justifications": adjustment["justifications"],
        "coverage_report": str(coverage_path),
        "profdata": str(profdata_path),
        "executable": str(exe_path),
        "clang": clang,
        "llvm_profdata": llvm_profdata,
        "llvm_cov": llvm_cov,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def select_harness_report(source: Path, target_function: str, requested_mode: str, max_conditions: int, report):
    if requested_mode == "unique-cause":
        return report
    if any("->" in condition for decision in report.to_dict()["decisions"] for condition in decision["conditions"]):
        return report

    unique_report = generate_mcdc_report(
        source,
        target_function=target_function,
        mcdc_mode="unique-cause",
        max_conditions=max_conditions,
    )
    if unique_report.score >= report.score:
        return unique_report
    return report


def require_tool(name: str) -> str:
    path = find_tool_path(name)
    if path is None:
        raise SystemExit(f"Required LLVM tool not found: {name}")
    return path


def require_coverage_clang() -> str:
    configured = os.environ.get("C2TESTCASE_COVERAGE_CLANG")
    if configured and Path(configured).exists():
        return configured

    for candidate in coverage_clang_candidates():
        if candidate.exists():
            return str(candidate)

    return require_tool("clang")


def coverage_clang_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    path_candidate = find_executable_on_path("x86_64-w64-mingw32-clang")
    if path_candidate is not None:
        candidates.append(Path(path_candidate))

    winget_root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget_root.exists():
        candidates.extend(winget_root.glob("MartinStorsjo.LLVM-MinGW.UCRT_*/llvm-mingw-*-ucrt-x86_64/bin/x86_64-w64-mingw32-clang.exe"))

    candidates.extend(
        [
            Path.home() / "AppData/Local/Programs/LLVM-MinGW/bin/x86_64-w64-mingw32-clang.exe",
            Path("C:/llvm-mingw/bin/x86_64-w64-mingw32-clang.exe"),
        ]
    )
    return tuple(dict.fromkeys(candidates))


def find_executable_on_path(executable: str) -> str | None:
    from shutil import which

    return which(executable)


def run_command(command: list[str], log_path: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    log_path.write_text(
        "COMMAND: " + " ".join(command) + "\n\nSTDOUT:\n" + completed.stdout + "\nSTDERR:\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SystemExit(f"Command failed with exit code {completed.returncode}; see {log_path}")
    return completed


def infer_function_signature(source_path: Path, function_name: str) -> FunctionSignature:
    source = source_path.read_text(encoding="utf-8")
    match = re.search(
        rf"\b([A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*)\s+{re.escape(function_name)}\s*\(([^)]*)\)",
        source,
        flags=re.S,
    )
    if match is None:
        raise SystemExit(f"Could not infer a simple int/bool signature for {function_name}.")

    return_type, raw_parameters = match.groups()
    parameters: list[tuple[str, str]] = []
    if raw_parameters.strip() and raw_parameters.strip() != "void":
        for raw_parameter in raw_parameters.split(","):
            parameter = " ".join(raw_parameter.strip().split())
            parameters.append(parse_parameter(parameter))
    return FunctionSignature(
        return_type=return_type,
        name=function_name,
        parameters=tuple(parameters),
        source_path=source_path,
        constants=extract_integer_constants(source),
        structs=extract_struct_fields(source),
    )


def parse_parameter(parameter: str) -> tuple[str, str]:
    pointer_match = re.fullmatch(r"(.+?)\s*\*\s*([A-Za-z_]\w*)", parameter)
    if pointer_match:
        base_type, name = pointer_match.groups()
        return f"{base_type.strip()} *", name

    scalar_match = re.fullmatch(r"(.+?)\s+([A-Za-z_]\w*)", parameter)
    if scalar_match:
        type_name, name = scalar_match.groups()
        return type_name.strip(), name

    raise SystemExit(f"Only simple scalar parameters are supported by this coverage runner: `{parameter}`")


def render_executable_harness(signature: FunctionSignature, report: dict[str, object]) -> str:
    lines = [
        "/* Generated executable harness for LLVM MC/DC coverage. */",
        "#include <stdbool.h>",
        "",
        f'#include "{signature.source_path.resolve().as_posix()}"',
        "",
        "int main(void) {",
        "    volatile int sink = 0;",
    ]

    case_index = 0
    seen_arguments: set[tuple[str, ...]] = set()
    all_conditions: list[str] = []
    for decision in report["decisions"]:
        all_conditions.extend(decision["conditions"])
        for case in decision["cases"]:
            case_index += 1
            assignments = solve_case_assignments(
                signature,
                decision["conditions"],
                case["values"],
                case["assignments"],
            )
            setup_lines, arguments = render_case_arguments(signature, assignments, case_index)
            seen_arguments.add(tuple(arguments))
            lines.extend(setup_lines)
            lines.append(f"    sink += {signature.name}({', '.join(arguments)}); /* case {case_index} */")

    for arguments in supplemental_concrete_arguments(signature, all_conditions):
        if arguments in seen_arguments:
            continue
        seen_arguments.add(arguments)
        case_index += 1
        lines.append(f"    sink += {signature.name}({', '.join(arguments)}); /* supplemental {case_index} */")

    if case_index == 0:
        raise SystemExit("No generated cases available for executable coverage harness.")

    lines.extend(
        [
            "    return sink == -2147483647;",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def render_case_arguments(
    signature: FunctionSignature,
    assignments: dict[str, object],
    case_index: int,
) -> tuple[list[str], list[str]]:
    setup_lines: list[str] = []
    arguments: list[str] = []
    for type_name, name in signature.parameters:
        if is_pointer_type(type_name):
            base_type = pointer_base_type(type_name)
            variable_name = f"{name}_{case_index}"
            pointer_value = int(assignments.get(name, 1))
            if pointer_value == 0:
                arguments.append("0")
                continue
            setup_lines.append(f"    {base_type} {variable_name} = {{0}};")
            for field_name in signature.structs.get(base_type, ()):
                key = f"{name}->{field_name}"
                if key in assignments:
                    setup_lines.append(f"    {variable_name}.{field_name} = {c_literal(assignments[key])};")
            arguments.append(f"&{variable_name}")
        else:
            arguments.append(c_literal(assignments.get(name, default_value_for_type(type_name))))
    return setup_lines, arguments


def supplemental_concrete_arguments(signature: FunctionSignature, conditions: list[str]) -> list[tuple[str, ...]]:
    if any(is_pointer_type(type_name) for type_name, _name in signature.parameters):
        return []
    domains = build_condition_aware_domains(signature, conditions)
    total = 1
    for domain in domains:
        total *= len(domain)
    if total > 5000:
        return []
    return [
        tuple(c_literal(value) for value in row)
        for row in candidate_rows(domains)
    ]


def build_condition_aware_domains(
    signature: FunctionSignature,
    conditions: list[str],
    preferred_assignments: dict[str, object] | None = None,
) -> list[tuple[int, ...]]:
    parameter_names = [name for _, name in signature.parameters]
    values_by_name: dict[str, list[int]] = {name: [] for name in parameter_names}
    enum_values = tuple(dict.fromkeys(signature.constants.values()))
    preferred_assignments = preferred_assignments or {}

    for type_name, name in signature.parameters:
        if name in preferred_assignments:
            values_by_name[name].append(int(preferred_assignments[name]))
        if type_name not in {"int", "unsigned int", "bool", "_Bool"} and enum_values:
            values_by_name[name].extend(enum_values)

    for condition in conditions:
        cleaned = condition.strip()
        while cleaned.startswith("!"):
            cleaned = cleaned[1:].strip()
        if cleaned in values_by_name:
            values_by_name[cleaned].extend((0, 1))
            continue

        match = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)", cleaned)
        if match:
            name, _operator, literal_text = match.groups()
            if name in values_by_name:
                literal = int(literal_text)
                values_by_name[name].extend((literal, literal - 1, literal + 1))
            continue

        match = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*([A-Za-z_]\w*)", cleaned)
        if match:
            left, _operator, right = match.groups()
            right_value = signature.constants.get(right)
            if left in values_by_name and right_value is not None:
                values_by_name[left].extend((right_value, right_value - 1, right_value + 1))
            if right in values_by_name:
                values_by_name[right].extend((0, 1, 2, 3))

    domains: list[tuple[int, ...]] = []
    for _type_name, name in signature.parameters:
        values = values_by_name[name] or [0, 1]
        domains.append(tuple(dict.fromkeys(values)))
    return domains


def default_value_for_type(type_name: str) -> int:
    return 0


def is_pointer_type(type_name: str) -> bool:
    return "*" in type_name


def pointer_base_type(type_name: str) -> str:
    return type_name.replace("const ", "").replace("*", "").strip()


def c_literal(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def solve_case_assignments(
    signature: FunctionSignature,
    conditions: list[str],
    values: list[bool],
    initial_assignments: dict[str, object],
) -> dict[str, object]:
    assignments = dict(initial_assignments)
    assignments.update(infer_assignments_from_conditions(signature, conditions, values))
    if satisfies_conditions(conditions, values, assignments, signature.constants):
        return assignments

    if any(is_pointer_type(type_name) for type_name, _name in signature.parameters):
        return assignments

    parameter_domains = build_condition_aware_domains(signature, conditions, assignments)
    parameter_names = [name for _, name in signature.parameters]
    for candidate_values in candidate_rows(parameter_domains):
        candidate = dict(zip(parameter_names, candidate_values))
        if satisfies_conditions(conditions, values, candidate, signature.constants):
            return candidate
    return assignments


def infer_assignments_from_conditions(
    signature: FunctionSignature,
    conditions: list[str],
    values: list[bool],
) -> dict[str, object]:
    assignments: dict[str, object] = {}
    parameter_names = {name for _type_name, name in signature.parameters}
    for condition, desired in zip(conditions, values):
        expression = condition.strip()
        negated = False
        while expression.startswith("!"):
            negated = not negated
            expression = expression[1:].strip()
        desired = not desired if negated else desired

        if expression in parameter_names:
            assignments[expression] = desired
            continue

        pointer_match = re.fullmatch(r"([A-Za-z_]\w*)\s*(!=|==)\s*0", expression)
        if pointer_match:
            name, operator = pointer_match.groups()
            if name in parameter_names:
                non_null = desired if operator == "!=" else not desired
                assignments[name] = int(non_null)
            continue

        field_bool = re.fullmatch(r"([A-Za-z_]\w*->[A-Za-z_]\w*)", expression)
        if field_bool:
            assignments[field_bool.group(1)] = int(desired)
            continue

        field_compare = re.fullmatch(r"([A-Za-z_]\w*->[A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)", expression)
        if field_compare:
            key, operator, literal_text = field_compare.groups()
            assignments[key] = candidate_integer(operator, int(literal_text), desired)
    return assignments


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


def satisfies_conditions(
    conditions: list[str],
    values: list[bool],
    assignments: dict[str, object],
    constants: dict[str, int],
) -> bool:
    return all(
        evaluate_supported_condition(condition, desired, assignments, constants, unknown_matches=False)
        for condition, desired in zip(conditions, values)
    )


def build_parameter_domains(signature: FunctionSignature, assignments: dict[str, object]) -> list[tuple[int, ...]]:
    domains: list[tuple[int, ...]] = []
    enum_values = tuple(dict.fromkeys(signature.constants.values()))
    integer_values = (0, 1, 2, 3, -1, 4, 5, 9, 10, 11, -2, -3)
    for type_name, name in signature.parameters:
        values: list[int] = []
        if name in assignments:
            values.append(int(assignments[name]))
        if type_name not in {"int", "unsigned int", "bool", "_Bool"} and enum_values:
            values.extend(enum_values)
        elif type_name in {"bool", "_Bool"} or isinstance(assignments.get(name), bool):
            values.extend((0, 1))
        else:
            values.extend(integer_values)
        domains.append(tuple(dict.fromkeys(values)))
    return domains


def candidate_rows(domains: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    rows: list[tuple[int, ...]] = [()]
    for domain in domains:
        rows = [row + (value,) for row in rows for value in domain]
        if len(rows) > 100_000:
            raise SystemExit("Concrete input search exceeded 100000 candidate rows; add bounds or stubs.")
    return rows


def evaluate_supported_condition(
    condition: str,
    desired: bool,
    assignments: dict[str, object],
    constants: dict[str, int] | None = None,
    unknown_matches: bool = True,
) -> bool:
    expression = condition.strip()
    negated = False
    while expression.startswith("!"):
        negated = not negated
        expression = expression[1:].strip()

    actual = evaluate_positive_condition(expression, assignments, constants or {})
    if actual is None:
        return unknown_matches
    actual = not actual if negated else actual
    return actual is desired


def evaluate_positive_condition(
    condition: str,
    assignments: dict[str, object],
    constants: dict[str, int],
) -> bool | None:
    pointer_match = re.fullmatch(r"([A-Za-z_]\w*)\s*(!=|==)\s*0", condition)
    if pointer_match:
        name, operator = pointer_match.groups()
        if name not in assignments:
            return None
        non_null = bool(assignments[name])
        return non_null if operator == "!=" else not non_null

    if re.fullmatch(r"[A-Za-z_]\w*->[A-Za-z_]\w*", condition):
        return bool(assignments.get(condition, 0))

    field_match = re.fullmatch(r"([A-Za-z_]\w*->[A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)", condition)
    if field_match:
        left, operator, right = field_match.groups()
        if left not in assignments:
            return None
        return compare_ints(int(assignments[left]), operator, int(right))

    if re.fullmatch(r"[A-Za-z_]\w*", condition):
        return bool(assignments.get(condition, 0))

    match = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)", condition)
    if match:
        left, operator, right = match.groups()
        if left not in assignments:
            return None
        return compare_ints(int(assignments[left]), operator, int(right))

    match = re.fullmatch(r"([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<)\s*([A-Za-z_]\w*)", condition)
    if match:
        left, operator, right = match.groups()
        right_value = assignments.get(right, constants.get(right))
        if left not in assignments or right_value is None:
            return None
        return compare_ints(int(assignments[left]), operator, int(right_value))

    return None


def compare_ints(left: int, operator: str, right: int) -> bool:
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    raise ValueError(f"Unsupported operator: {operator}")


def extract_integer_constants(source: str) -> dict[str, int]:
    constants: dict[str, int] = {}
    for enum_body in re.findall(r"typedef\s+enum\s*\{(.*?)\}\s*[A-Za-z_]\w*\s*;", source, flags=re.S):
        next_value = 0
        for raw_item in enum_body.split(","):
            item = raw_item.strip()
            if not item:
                continue
            match = re.fullmatch(r"([A-Za-z_]\w*)(?:\s*=\s*(-?\d+))?", item)
            if match is None:
                continue
            name, explicit_value = match.groups()
            if explicit_value is not None:
                next_value = int(explicit_value)
            constants[name] = next_value
            next_value += 1
    return constants


def extract_struct_fields(source: str) -> dict[str, tuple[str, ...]]:
    structs: dict[str, tuple[str, ...]] = {}
    for body, name in re.findall(r"typedef\s+struct\s*\{(.*?)\}\s*([A-Za-z_]\w*)\s*;", source, flags=re.S):
        fields: list[str] = []
        for field_match in re.finditer(r"\bint\s+([A-Za-z_]\w*)\s*;", body):
            fields.append(field_match.group(1))
        structs[name] = tuple(fields)
    return structs


def extract_confirmed_mcdc_scores(report_text: str) -> list[float]:
    return [
        float(match.group(1)) / 100.0
        for match in re.finditer(r"MC/DC Coverage for Decision:\s+([0-9.]+)%", report_text)
    ]


def compute_adjusted_mcdc(report: dict[str, object], signature: FunctionSignature, coverage_text: str) -> dict[str, object]:
    llvm_decisions = parse_llvm_decision_pairs(coverage_text)
    adjusted_scores: list[float] = []
    justifications: list[dict[str, object]] = []

    for decision_index, decision in enumerate(report["decisions"]):
        conditions = decision["conditions"]
        llvm_decision = llvm_decisions[decision_index] if decision_index < len(llvm_decisions) else {
            "condition_count": len(conditions),
            "covered": set(),
        }
        total = int(llvm_decision["condition_count"])
        covered = set(llvm_decision["covered"])
        if len(covered) >= total:
            adjusted_scores.append(1.0)
            continue
        try:
            unconfirmable = semantic_unconfirmable_conditions(decision, signature)
        except SystemExit:
            unconfirmable = {}
        justified = sorted(index for index in unconfirmable if index not in covered)
        for index in justified:
            reason = unconfirmable[index]
            justifications.append(
                {
                    "decision": decision["id"],
                    "condition_index": index,
                    "condition": conditions[index],
                    "classification": "coupled",
                    "reason": reason,
                    "message": justification_message(reason),
                }
            )
        adjusted_scores.append(round((len(covered) + len(justified)) / total, 4) if total else 1.0)

    return {
        "adjusted_scores": adjusted_scores,
        "adjusted_average": round(sum(adjusted_scores) / len(adjusted_scores), 4) if adjusted_scores else None,
        "justifications": justifications,
    }


def parse_llvm_decision_pairs(report_text: str) -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in report_text.splitlines():
        count_match = re.search(r"Number of Conditions:\s+(\d+)", line)
        if count_match:
            current = {"condition_count": int(count_match.group(1)), "covered": set()}
            decisions.append(current)
            continue
        pair_match = re.search(r"C(\d+)-Pair:\s+covered", line)
        if pair_match and current is not None:
            current["covered"].add(int(pair_match.group(1)) - 1)
    return decisions


def justification_message(reason: str) -> str:
    if reason == "duplicate-condition":
        return "Condition is a repeated source expression and cannot independently vary from its earlier occurrence."
    return "No source-level independence pair exists in the bounded scalar model."


def semantic_unconfirmable_conditions(decision: dict[str, object], signature: FunctionSignature) -> dict[int, str]:
    conditions = list(decision["conditions"])
    expression = str(decision["expression"])
    rows = feasible_condition_rows(signature, conditions)
    outcomes = {
        values: evaluate_decision(expression, tuple(conditions), values)
        for values in rows
    }
    outcomes = {values: outcome for values, outcome in outcomes.items() if outcome is not None}
    unconfirmable: dict[int, str] = {}
    for condition_index in range(len(conditions)):
        if is_duplicate_after_first(conditions, condition_index):
            unconfirmable[condition_index] = "duplicate-condition"
            continue
        if not has_source_level_independence_pair(condition_index, list(outcomes), outcomes):
            unconfirmable[condition_index] = "no-independence-pair"
    return unconfirmable


def feasible_condition_rows(signature: FunctionSignature, conditions: list[str]) -> list[tuple[bool, ...]]:
    domains = build_condition_aware_domains(signature, conditions)
    rows: set[tuple[bool, ...]] = set()
    parameter_names = [name for _, name in signature.parameters]
    for candidate_values in candidate_rows(domains):
        assignments = dict(zip(parameter_names, candidate_values))
        row: list[bool] = []
        supported = True
        for condition in conditions:
            positive = evaluate_condition_truth(condition, assignments, signature.constants)
            if positive is None:
                supported = False
                break
            row.append(positive)
        if supported:
            rows.add(tuple(row))
    return sorted(rows)


def evaluate_condition_truth(
    condition: str,
    assignments: dict[str, object],
    constants: dict[str, int],
) -> bool | None:
    expression = condition.strip()
    negated = False
    while expression.startswith("!"):
        negated = not negated
        expression = expression[1:].strip()
    value = evaluate_positive_condition(expression, assignments, constants)
    if value is None:
        return None
    return not value if negated else value


def is_duplicate_after_first(conditions: list[str], condition_index: int) -> bool:
    return conditions[condition_index] in conditions[:condition_index]


def has_source_level_independence_pair(
    condition_index: int,
    rows: list[tuple[bool, ...]],
    outcomes: dict[tuple[bool, ...], bool],
) -> bool:
    for left in rows:
        for right in rows:
            if left[condition_index] == right[condition_index]:
                continue
            if outcomes[left] == outcomes[right]:
                continue
            if all(index == condition_index or left[index] == right[index] for index in range(len(left))):
                return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
