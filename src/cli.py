from __future__ import annotations

import argparse
from pathlib import Path

from src.services.mcdc_generator import MCDC_MODES, generate_mcdc_report, write_report_artifacts


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
        "--target-function",
        help="Optional function name to record in generated reports.",
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

    report = generate_mcdc_report(
        args.source,
        max_conditions=args.max_conditions,
        headers=tuple(args.header),
        include_dirs=include_dirs,
        compile_flags=tuple(args.compile_flag),
        target_function=args.target_function,
        mcdc_mode=args.mcdc_mode,
    )
    json_path, harness_path, gap_report_path, excel_path = write_report_artifacts(report, args.output_dir)

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


if __name__ == "__main__":
    raise SystemExit(main())
