# Changelog

## Unreleased

### Added

- Added a local MC/DC generation workflow for C files with explicit `unique-cause`, `masking`, and `multicondition` modes.
- Added a FastAPI UI for uploading C files and generating MC/DC reports locally.
- Added hard C fixture coverage for MBD/autocode, hardware registers, HIL diagnostics, lifecycle gates, unit/integration gates, and system acceptance logic.
- Added LLVM/LLVM-MinGW confirmed MC/DC coverage execution through `scripts/run_llvm_mcdc_coverage.py`.
- Added executable scalar fixture evaluation through `scripts/evaluate_llvm_mcdc_fixtures.py`.
- Added bounded supplemental concrete calls for small scalar domains to improve LLVM source-level MC/DC confirmation.
- Added covered-or-justified adjusted MC/DC scoring with explicit coupled-condition justifications.
- Added simple `const Struct *` harness modeling for integer evidence structs.

### Changed

- Improved generated fixture scores on the 14-file corpus:
  - Unique-Cause: `0.9513`
  - Masking: `1.0000`
  - Multicondition: `0.8571`
- Improved raw confirmed LLVM MC/DC on the 9-file executable corpus to `0.9066`.
- Reached adjusted covered-or-justified MC/DC of `1.0000` on the executable scalar corpus.
- Improved `system_acceptance_matrix.c` raw confirmed LLVM MC/DC from `0.0000` to `0.9091`.
- Confirmed `architecture_lifecycle_gate.c` at raw LLVM MC/DC `1.0000`.
- Improved `unit_integration_gate.c` from unsupported pointer input to runnable raw LLVM MC/DC `0.3636`; richer nested-OR struct modeling remains future work.

### Notes

- Raw LLVM MC/DC remains separate from adjusted covered-or-justified MC/DC.
- `hard_coupled_conditions.c` has raw LLVM MC/DC `0.2500` because repeated and semantically coupled conditions cannot independently vary at source level; the remaining gaps are justified as `duplicate-condition` or `no-independence-pair`.
