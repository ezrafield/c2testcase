# MC/DC Fixture Corpus

These C files are intentionally small and graded by difficulty.

| File | Level | Expected Signal |
| --- | --- | --- |
| `easy_boolean_logic.c` | Easy | Full generated MC/DC target score with simple inferred values. |
| `easy_multiple_decisions.c` | Easy | Multiple decisions, including a `while`, with simple inferred values. |
| `medium_nested_logic.c` | Medium | Nested boolean expression and variable-to-variable comparison that needs manual setup notes. |
| `medium_enum_state.c` | Medium | Enum constants and negation; should generate vectors but require manual setup for symbolic constants. |
| `hard_coupled_conditions.c` | Hard | Strongly coupled repeated condition, so full independent MC/DC is not generated. |
| `hard_environment_dependencies.c` | Hard | Function calls, pointers, arrays, and struct access produce environment gaps. |
| `hard_too_many_conditions.c` | Hard | More conditions than the default cap, so the decision is classified as tool-limited. |
| `mbd_autocode_controller.c` | Hard | MBD-style generated controller with structs, calibration gates, nested logic, and diagnostic fallback. |
| `hardware_register_safety.c` | Hard | Volatile registers, bit masks, external GPIO, and ADC bounds. |
| `architecture_lifecycle_gate.c` | Hard | Architecture/basic/detail/coding/test lifecycle release gate with many conditions. |
| `unit_integration_gate.c` | Hard | Unit and integration test quality gate with waiver-like logic. |
| `system_acceptance_matrix.c` | Hard | System and hardware acceptance gate with enums, risk class, and phase-coupled conditions. |
| `hardware_in_loop_diagnostics.c` | Hard | Hardware-in-loop diagnostics with external reads, repeated callbacks, and range checks. |
