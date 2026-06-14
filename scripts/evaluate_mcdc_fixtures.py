from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.mcdc_generator import MCDC_MODES, generate_mcdc_report, write_report_artifacts

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "c"
OUTPUT_DIR = ROOT / "build" / "mcdc-eval"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for source in sorted(FIXTURE_DIR.glob("*.c")):
        mode_results = {}
        for mcdc_mode in MCDC_MODES:
            report = generate_mcdc_report(source, target_function=source.stem, mcdc_mode=mcdc_mode)
            case_dir = OUTPUT_DIR / mcdc_mode / source.stem
            write_report_artifacts(report, case_dir)
            decisions = report.to_dict()["decisions"]
            gap_counts: dict[str, int] = {}
            for decision in decisions:
                for gap in decision["gaps"]:
                    gap_counts[gap["classification"]] = gap_counts.get(gap["classification"], 0) + 1

            mode_results[mcdc_mode] = {
                "score": round(report.score, 4),
                "coverage_ready": report.coverage_ready,
                "coverage_status": report.coverage_status,
                "decisions": len(report.decisions),
                "cases": sum(len(decision.cases) for decision in report.decisions),
                "gap_counts": gap_counts,
                "output_dir": case_dir.relative_to(ROOT).as_posix(),
            }
        results.append({"source": source.relative_to(ROOT).as_posix(), "modes": mode_results})

    summary = {
        "fixture_count": len(results),
        "average_scores": {
            mode: round(sum(item["modes"][mode]["score"] for item in results) / len(results), 4) if results else 0.0
            for mode in MCDC_MODES
        },
        "coverage_ready_count": sum(1 for item in results if item["modes"]["unique-cause"]["coverage_ready"]),
        "results": results,
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def render_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# MC/DC Fixture Evaluation",
        "",
        f"- Fixture count: {summary['fixture_count']}",
        f"- Average generated scores: {format_scores(summary['average_scores'])}",
        f"- Fixtures with LLVM coverage-ready toolchain: {summary['coverage_ready_count']}",
        "",
        "| Source | Unique-Cause | Masking | Multicondition | Cases | Gaps (Masking) |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in summary["results"]:
        masking = result["modes"]["masking"]
        gap_counts = masking["gap_counts"]
        gaps = ", ".join(f"{name}={count}" for name, count in sorted(gap_counts.items())) or "none"
        lines.append(
            f"| `{result['source']}` | {result['modes']['unique-cause']['score']:.2f} | {masking['score']:.2f} | {result['modes']['multicondition']['score']:.2f} | {masking['cases']} | {gaps} |"
        )
    lines.append("")
    return "\n".join(lines)


def format_scores(scores: dict[str, float]) -> str:
    return ", ".join(f"{mode}={score:.4f}" for mode, score in scores.items())


if __name__ == "__main__":
    main()
