# units-static — Agent Guide

## Purpose

High-quality static **unit conversion** MCP server used as the “good MCP”
dogfood for Plugin Federation (judges should score high; CI fails on judge
fail and eval misses).

## Tools

| Tool | Description |
|------|-------------|
| `list_units` | Catalog of unit ids by dimension |
| `convert_length` | Length conversion |
| `convert_mass` | Mass conversion |
| `convert_temperature` | Temperature conversion |
| `convert_volume` | Volume conversion |
| `compare_quantities` | Same-dimension comparison |

## Running

```bash
pip install -r requirements.txt
python src/server.py
```

## Conventions

- Prefer deep tool/parameter descriptions over short stubs.
- Keep enums closed; never invent unit strings outside `list_units`.
- Keep output models object-shaped for MCP `outputSchema`.
- Do not add network-backed tools; this server is deterministic.
