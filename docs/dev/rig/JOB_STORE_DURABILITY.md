# Job Store Durability

Rig Phase 7 makes `.build/rig/jobs/<job_id>.json` the canonical product job store.

## Storage model

- Each job lives in its own JSON file.
- Writes use same-directory temporary files and `os.replace`.
- Mutations take an exclusive lock on `.build/rig/jobs/.lock`.
- Legacy `queue.json` is deprecated and only migrates through `rig doctor repair --migrate-legacy-queue`.

## Load model

- Normal reads ignore `.tmp`, `.lock`, and `.bad` files.
- Malformed files do not crash the CLI.
- Repair can quarantine malformed jobs to `<job_id>.json.bad`.

## Queue health

- `rig doctor queue` reports job counts, malformed files, tmp files, and legacy queue presence.
- `rig doctor repair --queue` may quarantine malformed files and clean stale temporary files.
