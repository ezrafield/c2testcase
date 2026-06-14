from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("Understand Anything is provided by the installed agent/plugin runtime.")
    print("Run the runtime command `/understand` from this repository, or use the dashboard/chat skills when available.")
    print(f"Expected graph path: {(ROOT / '.understand-anything' / 'knowledge-graph.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
