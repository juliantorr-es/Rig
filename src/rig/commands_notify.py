from __future__ import annotations

import json

from rig_tools import notifications


def register(subparsers, helpers):
    parser = subparsers.add_parser("notify", help="Notification helpers", description="Optional macOS notification sink for Rig.")
    notify = parser.add_subparsers(dest="notify_cmd", required=True)

    test = notify.add_parser("test", help="Show notification backend status")
    test.set_defaults(handler=lambda args: _emit(notifications.detect_backends()))

    send = notify.add_parser("send", help="Send a notification")
    send.add_argument("--title", required=True)
    send.add_argument("--message", required=True)
    send.add_argument("--subtitle")
    send.add_argument("--backend")
    send.set_defaults(handler=lambda args: _emit(notifications.send_notification(title=args.title, message=args.message, subtitle=args.subtitle, backend=args.backend).to_dict()))

    status = notify.add_parser("status", help="Show notification backend status")
    status.set_defaults(handler=lambda args: _emit({"backends": notifications.detect_backends()}))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

