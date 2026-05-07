# Quickstart

1. Install Rig with Python 3.14 and your preferred package manager.
2. Run `rig init`.
3. Run `rig tui`.
4. Create a workspace with `rig workspace create --task <task-id>`.
5. For governed orchestration, start with `rig run --task <task-id> --provider custom-command`.
6. Inspect the job with `rig job inspect <job_id>`.
7. Check durability with `rig doctor queue` if job state looks inconsistent.
8. Export a redacted support archive with `rig debug bundle --dry-run` before sending logs or reports.

The TUI's visual language is called the Gridline Interface. It uses CSS grid for the dashboard skeleton and typed container widgets for sidebar, main, evidence, and chat regions.
