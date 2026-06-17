# c2testcase

`c2testcase` is a local, CPU-friendly MC/DC testcase generation tool for C source files.

It extracts C decisions, generates best-effort MC/DC target rows, builds a first-class `Testcase_table`, exports BTC/SIL-style Excel workbooks, and provides a web UI that links highlighted C source lines to testcase evidence.

The project is deterministic and dependency-light. It does **not** claim compiler-confirmed 100% MC/DC for arbitrary C. It separates generated MC/DC target coverage from executable/concrete testcase readiness so gaps stay visible instead of being hidden behind guessed inputs.

## What It Produces

Given a `.c` file and optional headers, the tool emits:

- `mcdc_cases.json`: full report JSON, including decisions, cases, `testcase_table`, `interface_graph`, toolchain readiness, warnings, and gap information.
- `mcdc_testcases.xlsx`: Excel workbook generated from `Testcase_table`.
- `generated_mcdc_tests.c`: harness scaffold with generated setup comments.
- `gap_report.md`: generated target score, toolchain readiness, warnings, and coverage gaps.

The web UI additionally provides:

- `Testcase_table`: input/output columns and testcase rows.
- `Export Excel`: a metadata form for `Format Version`, `Architecture`, `Scope`, and `Name`; export uses the current `Testcase_table`.
- `BTC fill MANUAL`: a toggle that replaces displayed/exported `MANUAL` cells with BTC-friendly fallback values.
- `Ccode_interface`: split C source/detail view showing highlighted decision lines, testcase steps, reasons, input/output values, graph traces, and setup notes.

## Install

```powershell
python -m venv .c2testcases
.\.c2testcases\Scripts\python.exe -m pip install -r requirements.txt
.\.c2testcases\Scripts\python.exe -m pip install -e ".[dev]"
```

Run tests:

```powershell
.\.c2testcases\Scripts\python.exe -m pytest tests/unit tests/integration
```

## CLI Usage

Generate MC/DC target artifacts:

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli path\to\file.c --header path\to\file.h --target-function my_func --mcdc-mode masking -o build\mcdc
```

With manual setup columns/defaults:

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli path\to\file.c --target-function my_func --input-variable IN_gear=D,IN_ignition=1 --output-variable VF24blatgfd_s=-24.5,VS15lat_grev=-2.5 --mcdc-mode masking -o build\mcdc
```

Compiler flags that start with `-` should use the equals form:

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli path\to\file.c --compile-flag=-DUNIT_TEST -o build\mcdc
```

After editable install, `c2testcase` is also available as a console script:

```powershell
c2testcase path\to\file.c --target-function my_func -o build\mcdc
```

Supported generated target modes:

- `unique-cause`: strict MC/DC target generation.
- `masking`: allows masked/coupled variations where valid.
- `multicondition`: enumerates feasible truth combinations up to the configured cap.

## Web UI

Start the local FastAPI app:

```powershell
.\.c2testcases\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Workflow:

1. Upload a `.c` file and optional `.h` files.
2. Choose target function and MC/DC mode.
3. Generate cases.
4. Inspect `Testcase_table`.
5. Use `Ccode_interface` to inspect which testcase rows cover each highlighted decision line.
6. Optional: turn on `BTC fill MANUAL` when the workbook must avoid literal `MANUAL` cells for BTC Embedded import.
7. Click `Export Excel`, fill the four metadata fields, then export the workbook.

The Excel filename and worksheet name come from the export `Name` field.

Excel export is written as strict OOXML. If LibreOffice is installed (`soffice` on PATH, or the usual Windows LibreOffice install path), the app automatically round-trips the generated workbook through LibreOffice headless before returning it. That produces a workbook package closer to what LibreOffice, SharePoint, and Excel Online expect. If LibreOffice is not installed, export still works with the built-in writer.

## Testcase Table Semantics

`Testcase_table` is the canonical tabular output used by the UI and Excel export.

For ordinary C logic:

- input columns come from target function parameters plus manual input variables.
- output columns come from manual output variables, or `Decision_Result` when none are supplied.

For TargetLink/autocode-style C:

- `EXT_SP_GLOBAL` and `$RAM_EXTERN$` roots are input candidates, even when a `$RAM_EXTERN$` value only feeds a fallback output assignment.
- target function parameters are input candidates.
- `$DATA_EXTERN$` and `$DATA_PUBLIC$` calibration/static data are parameter candidates.
- `$RAM_PUBLIC$`, `GLOBAL`, and globals written by the function are output candidates.
- local variables are traced to root globals where possible and are not emitted as columns.
- a variable can be both input and output if it is both read for decisions and written by the function.
- arrays expand into consecutive columns. Visible labels repeat, while JSON uses unique keys like `AF24ln_bgratiofi_s[0]`.

The detailed classification rules live in `docs/specs/testcase-table-interface-classification.md`.

Rows include setup readiness:

- `target_rows`: generated MC/DC target rows.
- `concrete_rows`: rows where every input column has a concrete value.
- `partial_rows`: rows where some input values still require manual setup.
- `manual_required_rows`: rows where no concrete root input values were inferred.
- row-level `setup_status`: `concrete`, `partial`, or `manual_required`.
- row-level `setup_notes`: why setup is incomplete.

A full-`MANUAL` row is **not** an executable testcase yet. It is MC/DC target evidence: the tool knows which decision truth vector is needed, but cannot safely choose concrete root inputs.

Example:

```c
mixed = a + b;
if (mixed > 5U) { ... }
```

Many input pairs can satisfy `mixed > 5U`, so the tool keeps `a` and `b` as `MANUAL` and marks the row `manual_required` rather than guessing.

The `BTC fill MANUAL` toggle is only an export/display compatibility layer. When it is on, each `MANUAL` cell is replaced by the smallest numeric value already present in the same input/output column. If the column has no numeric value, the fallback is `0`. The underlying report still keeps `setup_status`, `setup_notes`, and original unresolved reasoning so manual setup risk remains visible.

## Interface Graph

Reports include an in-memory/source-level `interface_graph` serialized into `mcdc_cases.json`.

The graph is compact temporary trace evidence for the current report:

- nodes: globals, params, locals, fields, arrays, pointers, conditions, assignments, outputs.
- edges: `derived_from`, `aliases`, `reads_from`, `writes_to`, `condition_uses`.
- condition traces: root inputs and chain from root variable to condition variable.

Examples:

```text
VF24bgratiof_s -> Sa2_bgratiof_s_
sensor_raw -> p -> from_ptr -> from_call
source_arr -> from_arr
state -> state.ready
```

`Ccode_interface` uses these traces to explain why a testcase row uses a root input for a condition.

Ambiguous multi-root traces remain manual:

```text
a, b -> mixed
MANUAL: ambiguous roots [a, b] for `mixed`.
```

## Practical Scope

Works best for:

- C decisions in `if` and `while`.
- integer, float, and boolean comparisons.
- local assignment chains.
- arrays and fields at root-variable level.
- simple pointer aliases such as `p = &global` and `local = *p`.
- function-call-derived locals where inputs can be traced to arguments.
- TargetLink/autocode-style global interfaces.

Hard cases still need harness work or future solver/compiler support:

- ambiguous pointer aliasing.
- deep structs/pointers.
- external callbacks and hardware state.
- complex macro-generated control flow.
- loops requiring bounds.
- unreachable/defensive code.

The next deeper layer should be local Clang AST or LLVM IR with source/debug mapping. Raw assembly is not the preferred primary representation because it loses source variable names.

## Local Commands

```powershell
.\.c2testcases\Scripts\python.exe -m src.cli tests\fixtures\c\simple_logic.c --target-function logic -o build\mcdc-smoke
.\.c2testcases\Scripts\python.exe scripts\evaluate_mcdc_fixtures.py
.\.c2testcases\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
.\.c2testcases\Scripts\python.exe -m compileall src tests
```

LLVM coverage helpers are available for supported simple signatures:

```powershell
.\.c2testcases\Scripts\python.exe scripts\run_llvm_mcdc_coverage.py tests\fixtures\c\simple_logic.c --target-function logic --output-dir build\llvm-mcdc\simple_logic --mcdc-mode masking
.\.c2testcases\Scripts\python.exe scripts\evaluate_llvm_mcdc_fixtures.py
```

The LLVM path is a separate confirmation workflow. The main report score is still a generated target score unless external coverage evidence is run and reviewed.

## Make Targets

If GNU Make is available:

```powershell
make install
make dev
make test-unit
make test-integration
make mcdc SOURCE=tests/fixtures/c/simple_logic.c TARGET=logic MODE=masking OUT=build/mcdc-smoke
make mcdc-coverage SOURCE=tests/fixtures/c/simple_logic.c TARGET=logic MODE=masking OUT=build/llvm-mcdc/simple_logic
```

## Current Caveats

- Generated MC/DC target score is not the same as confirmed tool coverage.
- `manual_required` rows are not executable until setup values or a harness model are supplied.
- The parser is deterministic and local; it is not a full C interpreter.
- Ambiguous roots are intentionally not guessed.
