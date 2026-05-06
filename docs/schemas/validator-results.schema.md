# Validator Results Schema

**Schema ID:** validator-results.schema.md  
**Status:** STUB  
**Type:** Markdown (not JSON Schema)  
**Purpose:** Placeholder for validator results aggregation documentation  
**Replaced By:** `validate_verification_profiles.py` and individual validator outputs

---

## Status

This file is a **STUB / PLACEHOLDER**. The actual validator result schemas are defined in:

1. **Validator Result Schema:** `Docs/schemas/validator-result.schema.json` (JSON Schema for individual results)
2. **Verification Profiles:** `Docs/manifests/verification-profiles.yaml` (profile definitions)
3. **Validator Script:** `Scripts/validate_verification_profiles.py` (aggregation logic)

## Reason for Existence

This file exists to:
- Preserve the historical naming convention from earlier documentation efforts
- Provide a discoverable entry point for validation documentation
- Maintain compatibility with existing references in proof artifacts

## Canonical Sources

For validator results, use:

| Resource | Location | Purpose |
|----------|----------|---------|
| Validator Result Schema | `validator-result.schema.json` | JSON Schema for single result |
| Verification Profiles | `Docs/manifests/verification-profiles.yaml` | Profile-based validation |
| Profiles Validator | `Scripts/validate_verification_profiles.py` | Profile validation script |
| Validator Result Doctrine | `Docs/governance/VERIFICATION_PROFILES.md` | Doctrine and usage |

## File Relationship

This file (`validator-results.schema.md`) is **separate** from `validator-result.schema.json`:
- `validator-result.schema.json` = JSON Schema (singular) for one validation result
- `validator-results.schema.md` = Markdown stub (plural) - historical placeholder

## Migration Note

If you need a JSON Schema for aggregating multiple validator results, create `validator-results.schema.json` as a new JSON Schema file. This stub file can be:
- **Deleted** if no references exist
- **Archived** to `Docs/archive/schemas/` with a note
- **Replaced** with actual content if needed

---

## References

- [Validator Result Schema](validator-result.schema.json) (singular - JSON Schema)
- [Verification Profiles Manifest](../../manifests/verification-profiles.yaml)
- [Verification Profiles Doctrine](../../governance/VERIFICATION_PROFILES.md)
- [validate_verification_profiles.py](../../Scripts/validate_verification_profiles.py)
