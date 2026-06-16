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
    "testcase_table": {
      "input_columns": ["a", "b", "flag"],
      "output_columns": ["Decision_Result"],
      "score": 1.0,
      "score_kind": "generated_target_score",
      "mcdc_complete": true,
      "rows": [
        {
          "step": 0,
          "decision_id": "D1",
          "line": 1,
          "inputs": {"a": 1, "b": 9, "flag": false},
          "outputs": {"Decision_Result": true},
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

For TargetLink-style generated C, the table uses the declared interface:

- the target function parameter plus `EXT_SP_GLOBAL` declarations become input columns.
- `GLOBAL` declarations become output columns.
- `LOG_VAR` calls are used only as a fallback when declarations are not enough.
- `tests/fixtures/c/result_template.md` is a sample of the desired table shape, not a limit on testcase count.
- generated rows must still cover the extracted decisions well enough to reach the highest generated MC/DC score the tool can justify.
- for the current TargetLink conversion fixture, this means adding rows beyond the sample when saturation decisions need separate true/false cases.

### Web UI Views

The root page exposes these report views:

- `Gap report`: generated gap report markdown.
- `JSON`: raw `mcdc_cases.json`.
- `Harness`: generated C harness scaffold.
- `Testcase_table`: tabular testcase input/output rows.
- `Export Excel`: downloads `<Name>.xlsx`.
- Excel export fields are available in the input panel: `Format Version`, `Architecture`, `Scope`, and `Name`. The downloaded file and worksheet use `Name`.
- `Ccode_interface`: split source/detail view. The left pane highlights decision lines; the right pane shows testcase step, covered condition reason, input values, outputs, condition truth values, and notes. The source and detail panes scroll independently.

## Export Excel
```http
POST /api/export-excel
```

Exports the current `report.testcase_table` using the current Excel metadata field values. The web `Export Excel` button calls this endpoint at click time, so users may edit the fields after generation and before export.

Request:
```json
{
  "report": {"testcase_table": {"input_columns": [], "output_columns": [], "rows": []}},
  "format_version": "1.3",
  "architecture": "IO_CANII03AD5D24CNV_OSM_CSKN_10_egkn_EP [C-Code]",
  "scope": "io-canii03ad5d24cnv-osm-cskn-1.c:1:J_canrv_03ad5d24_cnvt",
  "name": "SIL_SV_ATG_1"
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
