# Testcase Table Interface Classification

`Testcase_table` separates C interface data into three groups:

- `Inputs`: runtime values the testcase should drive from outside the function/module.
- `Parameters`: calibration, constant, or function-call parameter values used by the logic but not treated as runtime input signals.
- `Outputs`: global/module values written or published by the function.

## TargetLink / Autocode Rules

For TargetLink-style C, the classifier reads top-level declarations, section comments, function signatures, assignments, and condition traces.

### Inputs

A variable is an input when it is a runtime root value supplied from outside the function/module:

- Function-external signal declarations such as `EXT_SP_GLOBAL`.
- `$RAM_EXTERN$` variables, even when they are not used directly in a decision condition.
- `$RAM_PUBLIC$` variables when they are read by a decision before or while also being written.

Local variables are not input columns. The graph traces locals back to their root variables.

Example:

```c
extern VF24 VF24bgratiof_s;
Sa2_bgratiof_s_ = VF24bgratiof_s;
if (Sa2_bgratiof_s_ > 8.F) { ... }
```

The table input is `VF24bgratiof_s`, not `Sa2_bgratiof_s_`.

Runtime externs are still inputs when they affect fallback outputs outside MC/DC conditions:

```c
extern VU16 VU16rsh;
VU16 VU16ln_rsh;

if (enabled) {
   VU16ln_rsh = calculated_value;
}
else {
   VU16ln_rsh = VU16rsh;
}
```

`VU16rsh` is an input because the output `VU16ln_rsh` can take its value when the logic does nothing else. If no condition constrains `VU16rsh`, testcase rows keep it as `MANUAL`.

### Parameters

A variable is a parameter when it is calibration/static data rather than a runtime input signal:

- Target function parameters are placed in `Parameters` for TargetLink tables.
- `$DATA_PUBLIC$` declarations are parameters.
- Numeric scalar and array initializers are copied into testcase rows when the C file provides them.

Example:

```c
CS15 XS15ln_bgratiofd12[2] = { 1, 2 };
```

The table has two consecutive parameter columns, both displayed as `XS15ln_bgratiofd12`, with internal keys:

```text
XS15ln_bgratiofd12[0]
XS15ln_bgratiofd12[1]
```

### Outputs

A variable is an output when it is written or publicly stored by the function:

- `GLOBAL` declarations.
- `$RAM_PUBLIC$` declarations.
- Global variables assigned by the target function.
- Root variables on the output side of traced assignments.

If a root variable is both read by a condition and written by the function, it can appear in both `Inputs` and `Outputs`.

## Array Columns

Array roots expand into consecutive columns in every group where they appear.

For:

```c
VF24 AF24ln_bgratiofi_s[3];
```

the visible headers are:

```text
AF24ln_bgratiofi_s | AF24ln_bgratiofi_s | AF24ln_bgratiofi_s
```

Because JSON objects cannot safely store duplicate keys, the report also includes internal keys:

```json
{
  "input_columns": ["AF24ln_bgratiofi_s", "AF24ln_bgratiofi_s", "AF24ln_bgratiofi_s"],
  "input_column_keys": ["AF24ln_bgratiofi_s[0]", "AF24ln_bgratiofi_s[1]", "AF24ln_bgratiofi_s[2]"]
}
```

The web table and Excel export show the visible duplicate labels but read values using the unique keys.

## Manual Values

`MANUAL` means the tool could not safely infer a concrete value for that column. If `BTC fill MANUAL` is enabled, display/export can replace `MANUAL` with per-column fallback values, but the report keeps `setup_status` and notes so unresolved setup is still visible.
