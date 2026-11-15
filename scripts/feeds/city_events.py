"""Backward-compat shim: the adapter now lives in ``tampere_city``.

Kept so older imports keep working; delegates entirely to ``tampere_city``.
"""
from feeds import tampere_city as _tc  # noqa: E402

fetch = _tc.fetch
URL = _tc.URL
TZ = _tc.TZ
MAX_EVENTS = _tc.MAX_EVENTS
