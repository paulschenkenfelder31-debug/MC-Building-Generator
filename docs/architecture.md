# Architecture

```text
Browser description + controls OR assistant design via MCP
            ↓
Offline keyword planner OR optional OpenAI planner OR connected assistant
            ↓
Validated BuildSpec (style, footprint, floors, tower, terrain, seed)
            ↓
Deterministic geometry primitives
foundation → shell → roof → interiors → entrance → tower → landscape
            ↓
World: sparse {(x, y, z): namespaced block-state string}
            ↓
Palette / state / door-pair validation
            ↓
Three.js preview + material quantities
            ↓
Sponge v2 .schem / Litematica v6 .litematic / JSON
```

## Responsibilities

- `mc_builder/planner.py`: natural-language parameter extraction and optional remote planning. AI produces a bounded data object, never executable code or individual block placements.
- `mc_builder/model.py`: schema, limits, block states, coordinate normalization, material counts, and versioned palette validation.
- `mc_builder/generator.py`: reusable geometry primitives and three architectural recipes. Per-request random generators keep builds deterministic across threads.
- `mc_builder/exporters.py`: binary NBT, Sponge VarInt block data, and Litematica's continuous packed long-array block states. Air is palette entry zero; indexing is X fastest, then Z, then Y.
- `mc_builder/builds.py`: one eight-build memory cache shared by the browser and MCP tools; generation slots bound concurrent geometry work.
- `mc_builder/mcp_tools.py`: official MCP SDK tools for capabilities, creating assistant-specified builds, and retrieving links. These tools never call a model provider.
- `mc_builder/web_app.py`: one ASGI application serves the browser API, static frontend, and stateless JSON Streamable HTTP MCP endpoint. Requests and design inputs are bounded.
- `mc_builder/server.py`: Uvicorn startup on the host's public port. No API credentials are sent to the browser.
- `web/preview.js`: exposed-face meshes, stair and door geometry, camera controls, cutaways, and PNG capture. This is a lightweight architectural preview.
- `tests/`: planner bounds, generation at size limits, staircase clearance, door validation, full-coordinate export round trips, independent readers, API integration, and browser interactions.

## API

`POST /api/generate` accepts:

```json
{
  "prompt": "A 29x25 medieval manor with 2 floors",
  "mode": "offline",
  "overrides": { "seed": 42, "terrain": true }
}
```

Response fields include `id`, `spec`, `planning`, `validation`, `dimensions` in X/Y/Z order, `palette`, `blocks` as `[x,y,z,paletteIndex]`, `materials`, and `block_count`. Coordinates in the response and exports are normalized consistently.

`GET /api/builds/{id}/schem`, `/litematic`, and `/json` download a cached build. `GET /api/health` reports readiness and whether a server API-key binding is present (never its value).

## Path toward the full concept

1. **Validate in Minecraft.** Exercise WorldEdit and Litematica imports in a Java test world. Add real-client captures and block-update checks before promising gameplay correctness.
2. **Expand the design schema.** Add named volumes, rooms, circulation, roof intersections, and stable component IDs. Preserve existing components during targeted edits.
3. **Add architectural knowledge.** Curate original or appropriately licensed style guides, palettes, and components. Keep third-party reference licensing and provenance with each example.
4. **Add reference-image planning.** Extract composition into the same validated schema; show unsupported requests before generation.
5. **Add render feedback.** Capture deterministic exterior and cutaway views. A vision model should return bounded component edits and evidence for each critique, rather than invented numeric scores.
6. **Iterate safely.** Apply one component edit at a time, revalidate, compare captures, and retain the best version with a small iteration and API-cost budget.
7. **Support larger and shared builds.** Add durable job storage, a queue, cancellation, account controls, usage limits, and a deployment-grade HTTP stack.

The optional direct AI planner uses one model call. The MCP path uses a design supplied by the connected assistant and makes no model-provider request. Multiple AI agents, a reference-build database, and a vision feedback loop are not part of the current implementation.
