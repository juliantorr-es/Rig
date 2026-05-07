import json
from pathlib import Path
from typing import Any, Dict, List

from rig.domain.projections import UIProjection, WidgetProjection, IntentProjection, ProjectionLayout

def test_empty_projection_has_receipt_list():
    from rig.domain.projection_builder import _build_empty_projection
    proj = _build_empty_projection(1, None, 0, 0, 0)
    assert "evidence.receipts" in proj.widgets
    receipt_widget = proj.widgets["evidence.receipts"]
    assert receipt_widget.type == "ReceiptList"
    assert "receipts" in receipt_widget.data
    assert receipt_widget.data["receipts"] == []

def test_widget_ids_are_stable():
    from rig.domain.projection_builder import _build_empty_projection
    proj = _build_empty_projection(1, None, 0, 0, 0)
    # The IDs in the map should match the widget objects
    for w_id, widget in proj.widgets.items():
        assert widget.id == w_id
