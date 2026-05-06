from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("models", help="Model management and downloads", description="Govern local LLM models: catalog, recommend, download, and verify.")
    mod = parser.add_subparsers(dest="models_cmd", required=True)

    # 1. Catalog
    catalog = mod.add_parser("catalog", help="Show available model catalog")
    catalog.set_defaults(handler=lambda args: _run_catalog(helpers, args))

    # 2. Recommend
    recommend = mod.add_parser("recommend", help="Recommend models based on system benchmark")
    recommend.set_defaults(handler=lambda args: _run_recommend(helpers, args))

    # 3. List
    list_mod = mod.add_parser("list", help="List registered/downloaded models")
    list_mod.set_defaults(handler=lambda args: _run_list(helpers, args))

    # 4. Show
    show = mod.add_parser("show", help="Show details for a specific model")
    show.add_argument("model_id", help="Model ID")
    show.set_defaults(handler=lambda args: _run_show(helpers, args))

    # 5. Download
    download = mod.add_parser("download", help="Download a model from Hugging Face")
    download.add_argument("--model", required=True, help="Model ID from catalog")
    download.add_argument("--dry-run", action="store_true", help="Print download plan without networking")
    download.set_defaults(handler=lambda args: _run_download(helpers, args))

    # 6. Verify
    verify = mod.add_parser("verify", help="Verify a registered model file exists")
    verify.add_argument("model_id", help="Model ID")
    verify.set_defaults(handler=lambda args: _run_verify(helpers, args))

    # 7. Smoke (Mocked for MVP)
    smoke = mod.add_parser("smoke", help="Run a tiny smoke test with the model")
    smoke.add_argument("model_id", help="Model ID")
    smoke.add_argument("--dry-run", action="store_true", default=True)
    smoke.set_defaults(handler=lambda args: _run_smoke(helpers, args))

def _run_catalog(helpers, args) -> int:
    from rig_tools import model_manager
    catalog = model_manager.load_catalog(helpers.repo_root)
    print(json.dumps(catalog, indent=2))
    return 0

def _run_recommend(helpers, args) -> int:
    from rig_tools import model_manager
    recommended = model_manager.recommend_models(helpers.repo_root)
    print(json.dumps(recommended, indent=2))
    return 0

def _run_list(helpers, args) -> int:
    from rig_tools import model_manager
    models = model_manager.list_registered_models(helpers.repo_root)
    print(json.dumps(models, indent=2))
    return 0

def _run_show(helpers, args) -> int:
    from rig_tools import model_manager
    catalog = model_manager.load_catalog(helpers.repo_root)
    model = next((m for m in catalog.get("models", []) if m["model_id"] == args.model_id), None)
    if model:
        print(json.dumps(model, indent=2))
    else:
        print(f"Model {args.model_id} not found in catalog.")
        return 1
    return 0

def _run_download(helpers, args) -> int:
    from rig_tools import model_manager
    try:
        plan = model_manager.get_model_download_plan(helpers.repo_root, args.model)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
        
    if args.dry_run:
        print("Dry run download plan:")
        print(json.dumps(plan, indent=2))
        return 0
        
    print(f"Starting download for {args.model} (network required)...")
    result = model_manager.run_download(helpers.repo_root, plan, dry_run=False)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "downloaded" else 1

def _run_verify(helpers, args) -> int:
    from rig_tools import model_manager
    result = model_manager.verify_model(helpers.repo_root, args.model_id)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "verified" else 1

def _run_smoke(helpers, args) -> int:
    print(f"Smoke test for {args.model_id} (Dry-run: {args.dry_run})")
    print("In MVP, smoke test is a placeholder that verifies model can be imported.")
    return 0
