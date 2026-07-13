# OpenAPI v1 Contract

The committed `openapi-v1.json` snapshot is generated from `create_app().openapi()` and canonicalized with version `1` of the snapshot canonicalizer.

Snapshot metadata:

- API contract version: `v1`
- Application version: `1.0.0`
- FastAPI: `0.139.0`
- Pydantic: `2.13.4`
- Canonicalization version: `1`

Tests compare generated canonical JSON with the committed snapshot and never update it. To update intentionally after reviewing a contract change, run:

```text
uv run --offline python scripts/update_openapi_snapshot.py
```
