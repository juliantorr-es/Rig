import hashlib, json
def stable_finding_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
