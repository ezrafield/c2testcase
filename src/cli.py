from __future__ import annotations

import argparse
from pathlib import Path

from src.services.mcdc_generator import (
    MCDC_MODES,
    ExcelExportMetadata,
    generate_mcdc_report,
    parse_support_template,
    write_report_artifacts,
)

ManualValue = int | float | bool | str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c2testcase",
        description="Generate best-effort MC/DC testcase targets from a C source file.",
    )
    parser.add_argument("source", type=Path, help="Path to the .c file to analyze.")
    parser.add_argument(
        "-I",
        "--include",
        action="append",
        default=[],
        help="Optional include directory recorded for future harness/build integration.",
    )
    parser.add_argument(
        "--header",
        type=Path,
        action="append",
        default=[],
        help="Optional .h file recorded for future harness/build integration.",
    )
    parser.add_argument(
        "--support-template",
        type=Path,
        help="Optional support Excel (.xlsx) template defining the Input/Parameter/Output columns to generate.",
    )
    parser.add_argument(
        "--target-function",
        help="Optional function name to record in generated reports.",
    )
    parser.add_argument(
        "--input-variable",
        action="append",
        default=[],
        help="Input variable column, optionally with a manual default such as gear=D. Repeat or use commas.",
    )
    parser.add_argument(
        "--output-variable",
        action="append",
        default=[],
        help="Output variable column, optionally with a baseline value such as state=DRIVE. Repeat or use commas.",
    )
    parser.add_argument(
        "--compile-flag",
        action="append",
        default=[],
        help="Optional compile flag to record for future harness/build integration.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("build/mcdc"),
        help="Directory for generated testcase artifacts.",
    )
    parser.add_argument(
        "--max-conditions",
        type=int,
        default=12,
        help="Maximum conditions per decision to enumerate locally.",
    )
    parser.add_argument(
        "--mcdc-mode",
        choices=MCDC_MODES,
        default="unique-cause",
        help="Generated target mode: strict Unique-Cause, Masking MC/DC, or multicondition enumeration.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"Source file not found: {args.source}")
    if args.source.suffix.lower() != ".c":
        raise SystemExit("Input source must be a .c file.")
    for header in args.header:
        if not header.exists():
            raise SystemExit(f"Header file not found: {header}")
        if header.suffix.lower() != ".h":
            raise SystemExit(f"Header input must be a .h file: {header}")
    include_dirs = tuple(Path(path) for path in args.include)
    for include_dir in include_dirs:
        if not include_dir.exists() or not include_dir.is_dir():
            raise SystemExit(f"Include directory not found: {include_dir}")

    interface_override = None
    excel_metadata: ExcelExportMetadata | None = None
    if args.support_template is not None:
        if not args.support_template.exists():
            raise SystemExit(f"Support template not found: {args.support_template}")
        if args.support_template.suffix.lower() != ".xlsx":
            raise SystemExit("Support template must be a .xlsx file.")
        try:
            interface_override, excel_metadata = parse_support_template(args.support_template)
        except (ValueError, KeyError) as error:
            raise SystemExit(f"Could not parse support template: {error}")

    input_variables, manual_inputs = parse_variable_setup(args.input_variable)
    output_variables, manual_outputs = parse_variable_setup(args.output_variable)
    report = generate_mcdc_report(
        args.source,
        max_conditions=args.max_conditions,
        headers=tuple(args.header),
        include_dirs=include_dirs,
        compile_flags=tuple(args.compile_flag),
        target_function=args.target_function,
        input_variables=input_variables,
        manual_inputs=manual_inputs,
        output_variables=output_variables,
        manual_outputs=manual_outputs,
        mcdc_mode=args.mcdc_mode,
        interface_override=interface_override,
    )
    json_path, harness_path, gap_report_path, excel_path = write_report_artifacts(
        report, args.output_dir, excel_metadata=excel_metadata
    )

    print(f"Generated MC/DC target score ({report.mcdc_mode}): {report.score:.1%}")
    print(f"Cases: {json_path}")
    print(f"Excel cases: {excel_path}")
    print(f"Harness scaffold: {harness_path}")
    print(f"Gap report: {gap_report_path}")
    for warning in report.warnings:
        print(f"Warning: {warning}")
    for result in report.decisions:
        for warning in result.warnings:
            print(f"Warning {result.decision.id}: {warning}")
    return 0


def parse_variable_setup(raw_variables: list[str]) -> tuple[tuple[str, ...], dict[str, ManualValue]]:
    variables: list[str] = []
    defaults: dict[str, ManualValue] = {}
    for raw in raw_variables:
        for variable in raw.replace("\n", ",").split(","):
            item = variable.strip()
            if not item:
                continue
            if "=" in item:
                name, value = item.split("=", 1)
                name = name.strip()
                if name:
                    variables.append(name)
                    defaults[name] = parse_manual_input_value(value.strip())
                continue
            name = item
            if name:
                variables.append(name)
    return tuple(dict.fromkeys(variables)), defaults


parse_input_variables = parse_variable_setup


def parse_manual_input_value(value: str) -> ManualValue:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        pass
    return value


if __name__ == "__main__":
    raise SystemExit(main())
