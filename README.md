# c2testcase

c2testcase is a local, CPU-friendly starter pipeline for generating best-effort MC/DC testcase targets from a C source file.

It currently extracts `if` and `while` decisions, splits boolean conditions, enumerates independence pairs, and emits:

- `mcdc_cases.json`: decision targets, selected MC/DC rows, inferred simple inputs, and warnings.
- `generated_mcdc_tests.c`: a harness scaffold to adapt to the function under test.
- `gap_report.md`: score, local tool availability, and gap classifications.

This is intentionally deterministic and dependency-light. It does not claim 100% MC/DC for arbitrary C; it reports coupled, oversized, or manually-bound cases so they can be closed with harness work, exclusions, or a future symbolic/coverage backend.

## Getting Started
```powershell
python -m venv .c2testcases
.\.c2testcases\Scripts\python.exe -m pip install -r requirements.txt
.\.c2testcases\Scripts\python.exe -m pytest tests/unit tests/integration
```

Generate cases:

```powershell
c2testcase path\to\file.c --header path\to\file.h -I path\to\includes --target-function my_func --mcdc-mode masking -o build\mcdc
```

Without installation, use:

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli path\to\file.c -o build\mcdc
```

Compiler flags that start with `-` should use the equals form:

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli path\to\file.c --compile-flag=-DUNIT_TEST -o build\mcdc
```

Supported generated target modes:

- `unique-cause`: strict default.
- `masking`: allows masked/coupled variations for a higher achievable generated score.
- `multicondition`: enumerates feasible truth combinations up to the cap.

Current harder fixture-corpus generated scores:

- Unique-Cause: `0.9513`
- Masking: `1.0`
- Multicondition: `0.8571`

The corpus includes MBD/autocode, hardware register, HIL diagnostic, architecture lifecycle, unit/integration, and system acceptance examples under `tests/fixtures/c/`.

## Practical Scope

Works best for pure logic such as:

- Primitive integer and boolean inputs.
- Bounded expressions with `&&`, `||`, `!`, and simple comparisons.
- C files that can later be compiled with a small hand-written harness.

Hard cases need extra setup:

- Pointers, structs, globals, hardware registers, volatile state, callbacks, and external calls.
- Loops or decisions with many conditions.
- Unreachable defensive code or strongly coupled conditions.

## Local Commands

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli tests\fixtures\c\simple_logic.c --target-function logic -o build\mcdc-smoke
.\.c2testcases\Scripts\python.exe scripts\run_llvm_mcdc_coverage.py tests\fixtures\c\simple_logic.c --target-function logic --output-dir build\llvm-mcdc\simple_logic --mcdc-mode masking
.\.c2testcases\Scripts\python.exe scripts\evaluate_llvm_mcdc_fixtures.py
.\.c2testcases\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
.\.c2testcases\Scripts\python.exe -m compileall src tests
.\.c2testcases\Scripts\python.exe scripts\evaluate_mcdc_fixtures.py
```

Open the local UI at `http://127.0.0.1:8000`.

The LLVM coverage runner is currently scoped to scalar functions where generated cases can be called directly. It emits `llvm_mcdc_report.txt`, `mcdc.profdata`, the executable harness, and `coverage_result.json` with confirmed MC/DC percentages.

Current executable scalar fixture coverage:

- Confirmed fixtures: `9`
- Average raw confirmed LLVM MC/DC: `0.9066`
- Average adjusted covered-or-justified MC/DC: `1.0`
- Full confirmed MC/DC: `7/9`
- Struct-pointer fixture support: `architecture_lifecycle_gate.c` confirmed at `1.0`
- Near-full confirmed MC/DC: `system_acceptance_matrix.c` at `0.9091`
- Justified low-score case: `hard_coupled_conditions.c`, where repeated and logically dependent conditions limit source-level MC/DC.
