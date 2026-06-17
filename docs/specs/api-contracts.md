# API Contracts

## Example Endpoint
```http
GET /health
```

Expected response:
```json
{
  "status": "ok"
}
```

## Generate MC/DC Testcases
```http
POST /api/generate
```

Accepts a multipart form with:

- `source`: required `.c` file.
- `headers`: optional one or more `.h` files.
- `target_function`: optional target function name.
- `input_variables`: optional comma-separated extra input columns or defaults, such as `gear=D`.
- `output_variables`: optional comma-separated output columns or defaults.
- `compile_flags`: optional compile flags recorded in the report.
- `excel_format_version`: text written to row 1 of the Excel export, default `1.3`.
- `excel_architecture`: text written to row 2 of the Excel export.
- `excel_scope`: text written to row 3 of the Excel export.
- `excel_name`: text written to row 4 of the Excel export. This also becomes the `.xlsx` filename and worksheet name.
- `max_conditions`: condition enumeration cap.
- `mcdc_mode`: `unique-cause`, `masking`, or `multicondition`.

The response includes generated artifacts, downloads, and a `report`. The generated score is a target-vector score, not compiler-confirmed coverage.

```json
{
  "report": {
    "source": "logic.c",
    "source_text": "int logic(int a,int b,int flag){ ... }",
    "score": 1.0,
    "score_kind": "generated_target_score",
    "mcdc_complete": true,
    "mcdc_mode": "masking",
    "target_function": "logic",
    "input_variables": ["a", "b", "flag"],
    "output_variables": [],
    "coverage_ready": true,
    "coverage_status": "LLVM coverage tools are available; use scripts/run_llvm_mcdc_coverage.py for supported simple signatures.",
    "interface_graph": {
      "nodes": [{"id": "n1", "kind": "global", "name": "VF24bgratiof_s"}],
      "edges": [{"from": "n1", "to": "n2", "kind": "derived_from"}],
      "condition_traces": {
        "D1:0": {
          "condition": "Sa2_bgratiof_s_ > 8.F",
          "roots": ["VF24bgratiof_s"],
          "chain": ["VF24bgratiof_s", "Sa2_bgratiof_s_"],
          "output_roots": []
        }
      }
    },
    "testcase_table": {
      "input_columns": ["a", "b", "flag"],
      "output_columns": ["Decision_Result"],
      "score": 1.0,
      "score_kind": "generated_target_score",
      "mcdc_complete": true,
      "target_rows": 1,
      "concrete_rows": 1,
      "partial_rows": 0,
      "manual_required_rows": 0,
      "rows": [
        {
          "step": 0,
          "decision_id": "D1",
          "line": 1,
          "inputs": {"a": 1, "b": 9, "flag": false},
          "outputs": {"Decision_Result": true},
          "setup_status": "concrete",
          "setup_notes": [],
          "decision_result": true,
          "covers": [0],
          "mcdc_condition_values": [true, true, false],
          "notes": []
        }
      ]
    },
    "decisions": []
  },
  "artifacts": {
    "mcdc_cases.json": "{...}",
    "generated_mcdc_tests.c": "/* ... */",
    "gap_report.md": "# MC/DC Gap Report\n..."
  },
  "downloads": {
    "SIL_SV_ATG_1.xlsx": "base64-encoded workbook"
  },
  "excel_filename": "SIL_SV_ATG_1.xlsx"
}
```

### Testcase Table

For ordinary C logic, `testcase_table` is derived from generated MC/DC cases:

- input columns come from the target function parameters plus any manually supplied input variables.
- output columns come from manually supplied output variables, or `Decision_Result` when none are supplied.
- each row is one generated testcase step.
- `target_rows` counts generated MC/DC target rows.
- `concrete_rows` counts rows where all input columns have concrete values.
- `partial_rows` and `manual_required_rows` identify rows that still need harness/manual input setup.
- each row has `setup_status`: `concrete`, `partial`, or `manual_required`.
- rows with all `MANUAL` inputs are retained as MC/DC target evidence, but they are not executable concrete testcases until setup is supplied.

For TargetLink-style generated C, the table uses the declared interface:

- target function parameters and `EXT_SP_GLOBAL` declarations are input candidates.
- `$RAM_EXTERN$` declarations are not automatically inputs; they become input columns when decision conditions read them directly or through traced local assignments.
- `$RAM_PUBLIC$`, `GLOBAL`, and globals written by the target function are output candidates.
- local variables are traced to root globals where possible and are not emitted as table columns. The local data-flow pass handles simple assignments, function-call-derived locals, array reads, field reads, pointer aliases such as `p = &global`, and dereferences such as `local = *p`.
- the same root variable may appear as both an input and an output when different conditions/assignments require it.
- `LOG_VAR` calls are used only as a fallback when declarations are not enough.
- `tests/fixtures/c/result_template.md` is a sample of the desired table shape, not a limit on testcase count.
- generated rows must still cover the extracted decisions well enough to reach the highest generated MC/DC score the tool can justify.
- for the current TargetLink conversion fixture, this means adding rows beyond the sample when saturation decisions need separate true/false cases.

This interface analysis is designed for local CPU-only operation. It does not require internet access and does not use raw assembly as the primary representation because assembly loses source-level variable names. Future compiler-backed improvements should prefer Clang AST or LLVM IR with source/debug mapping when those tools are available locally.

Reports include `interface_graph` as compact temporary trace evidence for the current report. It is used for testcase notes and `Ccode_interface` details; consumers should treat it as additive metadata and keep using `testcase_table` as the canonical table export source.

### Web UI Views

The root page exposes these report views:

- `Gap report`: generated gap report markdown.
- `JSON`: raw `mcdc_cases.json`.
- `Harness`: generated C harness scaffold.
- `Testcase_table`: tabular testcase input/output rows.
- `Export Excel`: opens an export panel with blank `Format Version`, `Architecture`, `Scope`, and `Name` fields plus an `Export` action. The export uses data from `Testcase_table`; the downloaded file and worksheet use `Name`.
- `BTC fill MANUAL`: toggles display/export replacement of `MANUAL` cells with per-column minimal numeric values, or `0` when no numeric value exists. This does not change row `setup_status` or report evidence.
- `Ccode_interface`: split source/detail view. The left pane highlights decision lines; the right pane shows testcase step, covered condition reason, input values, outputs, condition truth values, and notes. The source and detail panes scroll independently.

## Export Excel
```http
POST /api/export-excel
```

Exports the current `report.testcase_table` using the current Excel metadata field values. The web `Export Excel` button calls this endpoint at click time, so users may edit the fields after generation and before export.

When `fill_manual_for_btc` is true, every `MANUAL` testcase cell in the exported workbook is replaced by the smallest numeric value already present in that same input/output column. Columns with no numeric value use `0`. The source `report` is not modified.

Request:
```json
{
  "report": {"testcase_table": {"input_columns": [], "output_columns": [], "rows": []}},
  "format_version": "1.3",
  "architecture": "IO_CANII03AD5D24CNV_OSM_CSKN_10_egkn_EP [C-Code]",
  "scope": "io-canii03ad5d24cnv-osm-cskn-1.c:1:J_canrv_03ad5d24_cnvt",
  "name": "SIL_SV_ATG_1",
  "fill_manual_for_btc": false
}
```

Response:
```json
{
  "filename": "SIL_SV_ATG_1.xlsx",
  "download": "base64-encoded workbook"
}
```

Workbook layout:

- worksheet name is `name`.
- filename is `<name>.xlsx`.
- rows 1-4 contain `Format Version`, `Architecture`, `Scope`, and `Name`.
- row 5 groups `Inputs`, `Outputs`, and `Comment`.
- row 6 contains vertical testcase column headers.
- testcase data starts at row 7.
- when LibreOffice is available locally, the generated `.xlsx` is normalized through headless LibreOffice before download to improve SharePoint / Excel Online compatibility.
