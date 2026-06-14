from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 200


def check_file(path: Path) -> bool:
    line_count = len(path.read_text(encoding="utf-8").splitlines())
    if line_count > MAX_LINES:
        print(f"{path.relative_to(ROOT)} has {line_count} lines; keep it under {MAX_LINES}.")
        return False
    return True


def main() -> None:
    ok = all(check_file(ROOT / name) for name in ["AGENTS.md", "CLAUDE.md"])
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
