# API Contracts

Document public API contracts here.

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

The response `report` includes a first-class `testcase_table`:

```json
{
  "score_kind": "generated_target_score",
  "mcdc_complete": true,
  "testcase_table": {
    "input_columns": ["a", "b", "flag"],
    "output_columns": ["Decision_Result"],
    "score": 1.0,
    "score_kind": "generated_target_score",
    "mcdc_complete": true,
    "rows": [
      {
        "step": 0,
        "inputs": {"a": 1, "b": 9, "flag": false},
        "outputs": {"Decision_Result": true},
        "covers": [0],
        "mcdc_condition_values": [true, true, false]
      }
    ]
  }
}
```
