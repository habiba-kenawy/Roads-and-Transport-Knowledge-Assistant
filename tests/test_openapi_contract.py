"""The frontend's copy of the API contract must match the API (a changed field must not slip past the page)."""
import json

from scripts.export_openapi import CONTRACT_PATH, build_contract


def test_the_committed_contract_matches_the_api() -> None:
    """If this fails, the API's request or response shapes changed: run `python -m scripts.export_openapi`, then update frontend/src/types.ts."""
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert committed == build_contract()
