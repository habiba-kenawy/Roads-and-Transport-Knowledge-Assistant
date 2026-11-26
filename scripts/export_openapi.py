"""Write the API's data contract (field names, required fields, enum values) for the frontend's drift test.

Usage: python -m scripts.export_openapi
The frontend keeps its own copy of the API shapes in frontend/src/types.ts; its test compares that file with this contract, and
tests/test_openapi_contract.py fails if the committed contract no longer matches the API. Together they catch a changed API.
"""
import json
from pathlib import Path

from app.api.main import app

CONTRACT_PATH = Path("frontend/src/api/contract.json")


def build_contract() -> dict:
    """Reduce the OpenAPI schemas to what a client depends on: field names, which are required, and fixed value lists."""
    schemas = app.openapi()["components"]["schemas"]
    contract = {}
    for name, schema in sorted(schemas.items()):
        properties = schema.get("properties", {})
        contract[name] = {
            "properties": sorted(properties),
            "required": sorted(schema.get("required", [])),
            "enums": {field: spec["enum"] for field, spec in sorted(properties.items()) if "enum" in spec},
        }
    return contract


if __name__ == "__main__":
    CONTRACT_PATH.write_text(json.dumps(build_contract(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CONTRACT_PATH}")
