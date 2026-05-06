IGNORE_DIRS = {".build","DerivedData",".git","__MACOSX","ExternalResearch"}
def should_ignore_path(path):
    from pathlib import Path
    p = Path(path)
    return any(part in IGNORE_DIRS for part in p.parts) or p.name == ".DS_Store"
