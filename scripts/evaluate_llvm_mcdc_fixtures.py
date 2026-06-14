from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "c"
OUTPUT_DIR = ROOT / "build" / "llvm-mcdc-eval"

TARGETS = {
    "simple_logic.c": "logic",
    "easy_boolean_logic.c": "easy_boolean_logic",
    "easy_multiple_decisions.c": "easy_multiple_decisions",
    "medium_nested_logic.c": "medium_nested_logic",
    "medium_enum_state.c": "medium_enum_state",
    "hard_too_many_conditions.c": "hard_too_many_conditions",
    "hard_coupled_conditions.c": "hard_coupled_conditions",
    "system_acceptance_matrix.c": "system_acceptance_matrix",
    "architecture_lifecycle_gate.c": "architecture_lifecycle_gate",
}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for filename, target in TARGETS.items():
        source = FIXTURE_DIR / filename
        output_dir = OUTPUT_DIR / source.stem
        command = [
            str(PYTHON),
            str(ROOT / "scripts" / "run_llvm_mcdc_coverage.py"),
            str(source),
            "--target-function",
            target,
            "--output-dir",
            str(output_dir),
            "--mcdc-mode",
            "masking",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            reason_counts: dict[str, int] = {}
            for justification in payload["mcdc_justifications"]:
                reason = justification.get("reason", justification.get("classification", "unknown"))
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            results.append(
                {
                    "source": source.relative_to(ROOT).as_posix(),
                    "target_function": target,
                    "status": "confirmed",
                    "generated_score": payload["generated_score"],
                    "confirmed_mcdc_average": payload["confirmed_mcdc_average"],
                    "adjusted_mcdc_average": payload["adjusted_mcdc_average"],
                    "justification_count": len(payload["mcdc_justifications"]),
                    "justification_reasons": reason_counts,
                    "coverage_case_mode": payload["coverage_case_mode"],
                    "coverage_report": Path(payload["coverage_report"]).as_posix(),
                }
            )
        else:
            results.append(
                {
                    "source": source.relative_to(ROOT).as_posix(),
                    "target_function": target,
                    "status": "failed",
                    "error": (completed.stderr or completed.stdout).strip(),
                    "output_dir": output_dir.relative_to(ROOT).as_posix(),
                }
            )

    confirmed_scores = [
        result["confirmed_mcdc_average"]
        for result in results
        if result["status"] == "confirmed" and result["confirmed_mcdc_average"] is not None
    ]
    adjusted_scores = [
        result["adjusted_mcdc_average"]
        for result in results
        if result["status"] == "confirmed" and result.get("adjusted_mcdc_average") is not None
    ]
    summary = {
        "fixture_count": len(results),
        "confirmed_count": len(confirmed_scores),
        "confirmed_average": round(sum(confirmed_scores) / len(confirmed_scores), 4) if confirmed_scores else None,
        "adjusted_average": round(sum(adjusted_scores) / len(adjusted_scores), 4) if adjusted_scores else None,
        "results": results,
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def render_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# LLVM MC/DC Fixture Evaluation",
        "",
        f"- Fixture count: {summary['fixture_count']}",
        f"- Confirmed fixture count: {summary['confirmed_count']}",
        f"- Average confirmed MC/DC: {summary['confirmed_average']}",
        f"- Average adjusted MC/DC: {summary['adjusted_average']}",
        "",
        "| Source | Status | Generated | Confirmed | Adjusted | Justifications | Reasons | Case Mode | Report |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for result in summary["results"]:
        generated = result.get("generated_score", "")
        confirmed = result.get("confirmed_mcdc_average", "")
        adjusted = result.get("adjusted_mcdc_average", "")
        justifications = result.get("justification_count", "")
        reasons = format_reason_counts(result.get("justification_reasons", {}))
        report = result.get("coverage_report", "")
        report_cell = f"`{report}`" if report else ""
        lines.append(
            f"| `{result['source']}` | {result['status']} | {generated} | {confirmed} | {adjusted} | {justifications} | {reasons} | {result.get('coverage_case_mode', '')} | {report_cell} |"
        )
    lines.append("")
    return "\n".join(lines)


def format_reason_counts(reason_counts: object) -> str:
    if not isinstance(reason_counts, dict) or not reason_counts:
        return ""
    return ", ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
