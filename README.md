# units-static

High-quality **unit conversion** MCP server with fixed conversion tables (no
network I/O). Companion dogfood to [`meteo-static`](https://github.com/plugin-federation/meteo-static):
this repo is the **good MCP** baseline — tools are designed so schema-clarity
judges should score well (clear names, deep descriptions, strict enums, typed
output schemas).

## Tools

| Tool | Description |
|------|-------------|
| `list_units` | List supported unit ids (optionally filter by dimension) |
| `convert_length` | Convert length between SI / imperial units |
| `convert_mass` | Convert mass / weight |
| `convert_temperature` | Convert °C / °F / K (rejects below absolute zero) |
| `convert_volume` | Convert liquid volume (US + imperial + SI) |
| `compare_quantities` | Compare two quantities in the same dimension |

## Design goals (judge-friendly)

- **Names**: lowercase, descriptive, verb-led (`convert_*`, `list_*`, `compare_*`)
- **Descriptions**: when to call the tool, what it does, what not to use it for
- **Inputs**: closed enums / constrained fields with per-parameter descriptions
- **Outputs**: Pydantic models → MCP `outputSchema` objects (no bare arrays)
- **Deterministic**: static factor tables; safe for CI evals

## Running

### STDIO (default)

```bash
pip install -r requirements.txt
python src/server.py
```

### Streamable HTTP

```bash
pip install -r requirements.txt
python src/server.py --transport http --port 8000
```

## Export tools/list (local)

```bash
pip install -r requirements.txt
python scripts/export_tools_list.py --output ci/tools-list.json
```

## GitHub Actions

Shared Actions from **`plugin-federation/actions`**:

| Job | Purpose |
|-----|---------|
| `tools-list-validate` | Export `tools/list` + structural validation |
| `nexus-catalog` | OIDC → catalog, schema verify, selection-surface embeddings, LLM-as-judge (**fail-on-judge-fail**) |
| `evals` | Functional evals (`evals/evaluations.xml`, **100%** threshold) |

## Nexus pipeline setup

| Variable / secret | Purpose |
|-------------------|---------|
| `NEXUS_URL` | e.g. `https://api.nonprod.plugin-federation.com` |
| `NEXUS_OIDC_AUDIENCE` | Must match Nexus GitHub audience |
| `TENANT_ID` | Target tenant UUID |
| `MCP_SOURCE_ID` | **New** stable tool source UUID for this server |
| `XAI_API_KEY` | Judge model + functional evals |
| `OPENAI_API_KEY` | Embeddings (`text-embedding-3-small`) |

Embeddings use name + description + input schema (`tool-embedding-report/v1`).
Embed failures do not fail judges. Similarity reports are derived by Nexus from
a registered semantic-analysis profile whose `profileVersion` and `model` match
`text-embedding-3-small` (1536 dimensions unless shortened). CI cannot create
that profile.

Also register this repository in the tenant OIDC trust policy (same pattern as
meteo-static) and create a dedicated tool source for `units-static`.

## Status

- **Working** — stdio + streamable HTTP
- **Tools** — six conversion tools with structured I/O
- **CI** — Plugin Federation Actions with hard fail gates
