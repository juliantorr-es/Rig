# Rig Not-Compiler Capability

Status: FUTURE

State:
- Not implemented.
- Blocked until the active pyright lane is green or close to green.
- Depends on the Step 4 stabilization baseline.

## Problem Statement

Rig needs deterministic cleanup of type, lint, and static issues on the active product surface.

Broad lint cleanup is noisy and unsafe.

LLM-generated fixes can help as proposals, but they must not be authoritative.

Legacy or deprecated code must not poison the active product lane.

## Capability Summary

Future subsystem: compiler-ish pipeline for Python hygiene.

Pipeline:
Snapshot -> Diagnose -> Normalize -> Scope Filter -> Classify -> Plan -> Apply Allowed Transforms -> Verify -> Receipt

Working name:
- Rig Not-Compiler
- Internal script: `Scripts/rig_i_cant_believe_its_not_a_compiler.py`
- Eventual CLI shapes:
  - `rig not-compiler ...`
  - `rig compile python ...`

## Doctrine

- Models may propose.
- Diagnostics may inform.
- Only deterministic transforms may apply.
- Validators decide.
- Receipts remember.

## Non-Goals

- Do not build an AI autofixer.
- Do not revive the legacy Textual TUI.
- Do not run broad repo-wide formatting.
- Do not apply semantic rewrites.
- Do not add broad pyright or ruff ignores.
- Do not make model output authoritative.
- Do not replace validators or tests.

## Proposed Commands

Initial script-shaped entrypoints:

```bash
python Scripts/rig_i_cant_believe_its_not_a_compiler.py diagnose
python Scripts/rig_i_cant_believe_its_not_a_compiler.py plan
python Scripts/rig_i_cant_believe_its_not_a_compiler.py apply --fix-family pep585_builtin_generics
python Scripts/rig_i_cant_believe_its_not_a_compiler.py verify
```

Later CLI forms:

```bash
rig not-compiler plan
rig not-compiler apply --fix-family pep585_builtin_generics
rig compile python plan
```

## Architecture

### Snapshot

Capture:
- Git branch
- Git commit
- Dirty state
- Python version
- Tool versions
- Config hashes

### Diagnostic Frontend

Use existing static tooling as input frontends:
- Pyright JSON diagnostics via `pyright --outputjson`
- Ruff JSON output

Pyright already exposes machine-readable diagnostics through `--outputjson`, including `generalDiagnostics` and summary counts.

### Diagnostic Normalizer

Normalize Pyright and Ruff diagnostics into one internal record shape.

That record should preserve:
- tool name
- diagnostic code
- file path
- range
- severity
- normalized message
- provenance hashes

### Scope Filter

Operate on active product surface only.

Legacy Textual and full-repo debt remain deferred.

### Classifier

Classify diagnostics into:
- `deterministic_fix_available`
- `planner_only`
- `advisory_only`
- `unsafe_to_autofix`
- `outside_scope`

### Fix Planner

Emit JSON or Markdown plans without editing files by default.

Planning output should identify:
- candidate file
- diagnostic source
- proposed fix family
- safety gate result
- expected verification steps

### Transform Engine

Eventually use LibCST for source-preserving codemods.

LibCST codemods are intended for automated refactors that preserve concrete source details while applying controlled edits across codebases.

### Verifier

Verification gates:
- `compileall`
- scoped Pyright
- targeted Ruff
- active pytest
- smoke commands

### Receipt Writer

Write a receipt that records:
- before and after counts
- planned transforms
- applied transforms
- rejected diagnostics
- validation results

## Initial Fix Families

Proposed only, not implemented.

- `pep585_builtin_generics`
  - `List[T]` -> `list[T]`
  - `Dict[K, V]` -> `dict[K, V]`
  - `Tuple[...]` -> `tuple[...]`
  - `Set[T]` -> `set[T]`
- `unused_typing_import_cleanup`
- `missing_typing_import`
- `future_annotations_inserter`
- `type_checking_import_guard`
- `quoted_forward_ref_normalizer`

## Explicitly Unsafe Or Deferred Families

- `optional_none_guard`
- control-flow rewrites
- return-value changes
- inferred API contract changes
- broad type ignore insertion
- file-level pyright suppression
- semantic patch repair

## Safety Gates

- Plan mode is default and never edits files.
- Apply mode requires explicit command and at least one `--fix-family`.
- Apply mode refuses dirty git tree unless `--allow-dirty` is passed.
- Only active-scope files can be touched.
- Every transform must reference a diagnostic or allowed fix family.
- Every apply run must verify and receipt.
- Failed verification means failed run, not success.

## Acceptance Criteria

Future implementation should satisfy:
- Diagnose mode parses Pyright JSON and Ruff JSON.
- Plan mode emits structured transform plans without changing files.
- Apply mode supports at least one safe family, likely `pep585_builtin_generics`.
- Receipts are written for plan and apply.
- Tests cover classifier behavior with fixture diagnostics.
- No broad formatting wave is introduced.
- Active tests and smoke commands remain green.

## Relationship To Rig Pseudo-Compiler

This capability is a stepping stone toward Rig’s broader deterministic pseudo-compiler model:

- model output normalization
- typed candidate decoding
- patch planning
- validation before application
- receipts as evidence

## References

- [Pyright CLI JSON output documentation](https://github.com/microsoft/pyright/blob/main/docs/command-line.md)
- [Pyright overview](https://microsoft.github.io/pyright/)
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [LibCST codemod documentation](https://libcst.readthedocs.io/en/latest/codemods.html)
