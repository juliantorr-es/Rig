"""Intent dispatching and handling.

This module provides the IntentDispatcher for governed execution paths.
- IntentDispatcher: Routes intents to appropriate handlers
- Handler registry for execution and other governed operations
"""

from rig.domain.intents.dispatcher import IntentDispatcher

__all__ = ["IntentDispatcher"]
