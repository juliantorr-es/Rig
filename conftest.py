"""Test helpers for async compatibility.

This repository uses a small number of `@pytest.mark.asyncio` tests without a
dedicated asyncio plugin active in this environment. Provide a minimal shim so
those tests execute with `asyncio.run(...)` instead of failing collection.
"""

from __future__ import annotations

import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None

    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None

    funcargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(testfunction(**funcargs))
    return True
