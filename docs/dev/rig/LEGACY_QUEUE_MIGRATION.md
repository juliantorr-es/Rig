# Legacy Queue Migration

Older Rig builds stored orchestration queue state in `.build/rig/queue/queue.json`.

Phase 7 keeps that file as a legacy input only.

## Canonical target

` .build/rig/jobs/<job_id>.json`

## Migration command

```bash
rig doctor repair --migrate-legacy-queue
```

## Rules

- The original `queue.json` is preserved.
- Canonical job files are written atomically.
- Existing newer canonical jobs are not overwritten unless `--force` is introduced for that migration path.
- A migration receipt is written under `.build/rig/receipts/`.
