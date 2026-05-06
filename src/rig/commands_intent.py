from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("intent", help="Intent decoder", description="Convert model-generated operation proposals into safe Rig plans.")
    intent = parser.add_subparsers(dest="intent_cmd", required=True)

    # 1. Status
    status = intent.add_parser("status", help="Show intent decoder status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Decode
    decode = intent.add_parser("decode", help="Decode an intent")
    decode.add_argument("--input", type=Path, help="Path to input file containing intent")
    decode.add_argument("--text", help="Direct text input")
    decode.add_argument("--task", help="Optional current task context")
    decode.set_defaults(handler=lambda args: _run_decode(helpers, args))

    # 3. Plan (Decode + generate CommandPlan)
    plan = intent.add_parser("plan", help="Decode and generate command plan")
    plan.add_argument("--input", type=Path, required=True)
    plan.add_argument("--dry-run", action="store_true", default=True)
    plan.set_defaults(handler=lambda args: _run_plan(helpers, args))

def _run_status(helpers, args) -> int:
    from rig_tools import intent_decoder
    status = {
        "schema_version": "1.0.0",
        "supported_intents": list(intent_decoder.SAFE_ALIASES.keys()),
        "forbidden_keywords": list(intent_decoder.FORBIDDEN_KEYWORDS),
        "status": "ready"
    }
    print(json.dumps(status, indent=2))
    return 0

def _run_decode(helpers, args) -> int:
    from rig_tools import intent_decoder
    input_text = ""
    if args.input:
        input_text = args.input.read_text(encoding="utf-8")
    elif args.text:
        input_text = args.text
    else:
        print("Error: --input or --text required")
        return 1
        
    result = intent_decoder.decode_intent(helpers.repo_root, input_text, current_task=args.task)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] != "rejected" else 1

def _run_plan(helpers, args) -> int:
    from rig_tools import intent_decoder
    input_text = args.input.read_text(encoding="utf-8")
    result = intent_decoder.decode_intent(helpers.repo_root, input_text)
    
    if result["status"] == "rejected":
        print(f"Error: Intent rejected: {result['rejection_reason']}")
        return 1
        
    # In MVP we just show the decode result, but intent_decoder could call
    # action_manifest to build a real CommandPlan in future turns.
    print(json.dumps(result, indent=2))
    return 0
