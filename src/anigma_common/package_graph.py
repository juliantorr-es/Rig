from __future__ import annotations
import json, subprocess, re
from pathlib import Path

def discover_package_roots(repo_root: Path):
    roots=[]
    for p in [repo_root/"anigma", repo_root]:
        if (p/"Package.swift").exists(): roots.append(p)
    for p in repo_root.rglob("Package.swift"):
        if p.parent not in roots: roots.append(p.parent)
    return roots

def describe_package(root: Path):
    try:
        proc = subprocess.run(["swift","package","describe","--type","json"], cwd=root, capture_output=True, text=True, check=False)
        if proc.returncode==0:
            return json.loads(proc.stdout)
    except Exception:
        pass
    return None

def parse_package_swift(path: Path):
    text = path.read_text(encoding="utf-8")
    targets = re.findall(r'\.(?:executableTarget|target|testTarget)\((?:.|\n)*?name:\s*"([^"]+)"', text)
    products = re.findall(r'\.(?:library|executable)\((?:.|\n)*?name:\s*"([^"]+)"', text)
    return {"targets":[{"name":t} for t in targets],"products":[{"name":p} for p in products]}
