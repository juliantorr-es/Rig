# Tier Boundary Violations Schema

**Schema ID:** tier-boundary-violations.schema.md  
**Status:** STUB  
**Type:** Markdown (not JSON Schema)  
**Purpose:** Placeholder for tier boundary violation documentation  
**Replaced By:** `validate_tiers.py` output and `Docs/governance/TIER_GOVERNANCE.md`  

---

## Status

This file is a **STUB / PLACEHOLDER**. The actual tier boundary violation detection and reporting is performed by:

1. **Script:** `Scripts/validate_tiers.py`
2. **Doctrine:** `Docs/governance/TIER_GOVERNANCE.md`
3. **Schema:** `Docs/schemas/td-epic.schema.json` and `Docs/schemas/td-task.schema.json`

## Reason for Existence

This file exists to:
- Preserve the historical naming convention from earlier documentation efforts
- Provide a discoverable entry point for tier boundary documentation
- Maintain compatibility with existing references

## Canonical Sources

For tier boundary validation, use:

| Resource | Location | Purpose |
|----------|----------|---------|
| Tier Governance Doctrine | `Docs/governance/TIER_GOVERNANCE.md` | Rules for tier boundaries |
| Tier Validator | `Scripts/validate_tiers.py` | Automated validation |
| TD Descriptor Schema | `Docs/schemas/td-epic.schema.json` | Schema with tier fields |

## Migration Note

If you need a JSON Schema for tier boundary violations, create a new schema file and update all references. This stub file can be:
- **Deleted** if no references exist
- **Archived** to `Docs/archive/schemas/` with a note
- **Replaced** with actual content if needed

---

## References

- [Tier Governance Doctrine](../governance/TIER_GOVERNANCE.md)
- [validate_tiers.py](../../Scripts/validate_tiers.py)
- [TD Epic Schema](td-epic.schema.json)
- [Module Role Index](../architecture/maps/module-role-index.yaml)
