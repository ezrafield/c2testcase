from pathlib import Path

from src.cli import main


def test_cli_generates_end_to_end_artifacts(tmp_path: Path, capsys) -> None:
    source = tmp_path / "logic.c"
    header = tmp_path / "logic.h"
    output_dir = tmp_path / "mcdc"
    source.write_text("int logic(int a,int b,int flag){ if ((a > 0 && b < 10) || flag) return 1; return 0; }")
    header.write_text("int logic(int a, int b, int flag);\n")

    exit_code = main(
        [
            str(source),
            "--header",
            str(header),
            "-I",
            str(tmp_path),
            "--target-function",
            "logic",
            "--input-variable",
            "a,b,flag,expected",
            "--compile-flag=-DUNIT_TEST",
            "--mcdc-mode",
            "masking",
            "-o",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Generated MC/DC target score (masking): 100.0%" in captured.out
    assert "Excel cases:" in captured.out
    assert (output_dir / "mcdc_cases.json").exists()
    assert (output_dir / "mcdc_testcases.xlsx").exists()
    assert (output_dir / "generated_mcdc_tests.c").exists()
    assert (output_dir / "gap_report.md").exists()
    assert '"input_variables": [' in (output_dir / "mcdc_cases.json").read_text()
