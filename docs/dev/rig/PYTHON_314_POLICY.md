# Python 3.14 Policy

Rig requires Python 3.14 or newer.

Why:

- The public product surface is now packaged and installable.
- The runtime assumptions are aligned with current local-first tooling support.
- The product should fail cleanly on unsupported interpreters instead of half-starting.

What users should see on unsupported versions:

- the current Python version
- `sys.executable`
- a short upgrade hint

Rig does not rely on `pyenv` or ambient `PYTHONPATH`.
