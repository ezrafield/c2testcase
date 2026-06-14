from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "docs/agent/INDEX.md",
    "docs/agent/CODEMAP.md",
    "docs/agent/AGENTS_AND_SKILLS.md",
    "docs/agent/COMMAND_OUTPUT_POLICY.md",
    "docs/agent/TOOLS.md",
    "docs/agent/MCPS.md",
    "docs/agent/SOURCE_UNDERSTANDING.md",
    "docs/agent/TASK_LOG_TEMPLATE.md",
    ".mcp/README.md",
    ".mcp/rtk.md",
    ".understand-anything/README.md",
]


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        for path in missing:
            print(f"Missing required doc: {path}")
        raise SystemExit(1)

    print("Agent docs look complete.")


if __name__ == "__main__":
    main()
