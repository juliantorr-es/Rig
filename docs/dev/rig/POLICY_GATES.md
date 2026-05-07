# Policy Gates

Rig policy defaults are conservative. `allow_auto_apply` stays unsupported even if configured. Jobs stop at proposal acceptance by default, and the durable job store underneath those gates is lock-protected and schema-safe.
