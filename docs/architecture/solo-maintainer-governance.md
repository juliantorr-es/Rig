# Solo Maintainer Governance

Rig can enforce protected branches, required checks, and replay validation even when the repository has a single maintainer.

That setup is still useful, but it has a hard limit:

- CODEOWNER auto-routing does not prove separation of duties when the same person owns and opens the PR.
- reviewer assignment can still document policy, but it is not an independent authority boundary in a solo-maintainer repo.
- the real operational controls in this mode are branch protection, required checks, and human review discipline.

Policy for solo-maintainer operation:

1. Keep `main` and `preproduction` protected.
2. Keep replay and preproduction validation required before merge.
3. Treat CODEOWNERS as policy documentation, not as a proof of independent review.
4. Use synthetic rehearsal PRs to verify workflow execution and merge blocking, not reviewer separation.

This is the correct governance model until a second maintainer or team-based review lane exists.
