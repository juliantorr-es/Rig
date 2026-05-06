# Security

Rig is a local developer tool. Treat repository paths, command output, and any generated receipts as potentially sensitive.

- Do not commit secrets, `.env` files, caches, build output, or local machine logs.
- Report security issues privately to the maintainer of this repository.
- If a command starts writing outside the repo root, stop and repair the path handling first.
