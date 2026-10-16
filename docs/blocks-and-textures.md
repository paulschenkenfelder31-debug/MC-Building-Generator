# Complete Java block catalog and original textures

The app is pinned to **Minecraft Java 26.3**, the latest stable Java release identified on 2026-10-16, with **DataVersion 5023**. Snapshots are excluded. The committed registry contains all **1,286 registered block IDs**, including technical blocks, fluids, and the three air variants. Air removes a placed block. Bedrock and modded blocks are outside this catalog.

Registry facts come from the version-tagged [Misode mcmeta generated block report](https://github.com/misode/mcmeta/blob/26.3-summary/blocks/data.json). The source URL and SHA-256 are recorded in `mc_builder/data/catalog.json`. Every block exposes its allowed properties and defaults. Use WorldEdit/FAWE and Litematica versions that support 26.3.

## Use the library

Below the preview, **Build with every block** searches the full catalog. Select a block and adjust its state properties, such as stair facing or slab type.

- **Assign** chooses the material for walls, beams, floors, roofs, or roof stairs in the next generated building. Press **Generate building** to apply these assignments. Directional properties are adjusted by the geometry generator where needed.
- **Replace all** replaces a material in the current build, preserving compatible properties such as stair facing and log axis. A replacement that breaks door pairing is rejected.
- **Place selected block** and **Remove block** edit the displayed X/Y/Z coordinates. The preview click mode can inspect coordinates, place against a clicked face, or remove the clicked block. Doors, beds, and tall plants are placed/removed as pairs.
- Each edit creates a new build and updates the preview, materials, and all three downloads. **Undo edit** returns to an earlier build while it remains in the eight-build cache. The previous build is not mutated.

Edits accept integer coordinates 0–127 and at most 256 placements per request; structures are bounded to 128 blocks per axis and 150,000 placed blocks. Coordinates are normalized to the minimum occupied corner, as in the preview and JSON export. Removing an outermost block can shift this origin. Block-entity inventories, sign text, and custom entity data are not exported. Gravity, neighbor updates, fluid flow, redstone, lighting and survival placement rules are not simulated.

## Install the original artwork

Original textures and models are fetched from **Mojang's official Java client download** during setup or Docker builds. They are not committed to this repository. Minecraft artwork remains © Mojang / Microsoft; this project is not affiliated with Mojang.

```bash
.venv/bin/python -m pip install -r requirements-assets.txt
.venv/bin/python scripts/prepare_minecraft_assets.py
# Restart the Python server after installing assets.
npm start
```

The installer selects the exact stable release matching the registry. It verifies Mojang's version-metadata SHA-1, then the client JAR's SHA-1 and byte length. It extracts only vanilla PNG textures, blockstate JSON, and model JSON, builds a nearest-filtered atlas, and deletes the temporary JAR. The cache is ignored at `minecraft-assets/`. It retains every extracted PNG unchanged, including non-block textures, while the atlas contains block textures and sprites referenced by block models outside that folder. The texture index also exposes available item images for catalog icons. A manifest records source URLs, checksums, version and counts.

The preview resolves model inheritance, string and sprite-object texture references (including `force_translucent`), variants, multipart conditions, element rotations, face UVs, transparent cutouts, and simple vegetation tints. It is an approximate web renderer: animated textures show their first frame, weighted variants use their first model, UV-lock/biome colors and Minecraft's lighting are not reproduced exactly, and engine-rendered blocks such as chests/beds/signs can use approximate cubes with a particle texture or color placeholder. Full block IDs and state properties still reach the exports. `/api/assets` reports whether original assets are installed; missing assets produce an explicit placeholder notice.

## Render

The **Docker** build downloads the artwork automatically in a separate build stage. Deploy the updated `deploy/public-demo` branch using Render's **Manual Deploy → Deploy latest commit**.

For an existing Render service using the **Python 3** runtime, set:

| Setting | Value |
| --- | --- |
| Branch | `deploy/public-demo` |
| Root directory | empty |
| Build command | `bash scripts/build.sh` |
| Start command | `python -m mc_builder.server --host 0.0.0.0` |

Then deploy the latest commit. This installs Pillow at build time, builds the frontend and downloads the artwork before serving the app. A failed verified asset download fails the build instead of silently publishing a textureless update. No domain or model API key is needed.

## Cloud network prerequisite

The current Codex runtime's proxy rejects `piston-meta.mojang.com` and `piston-data.mojang.com` with CONNECT 403. Both hostnames were added to the environment configuration draft while preserving its other domains. Saving a draft does not activate the policy. Review/save it in environment settings and publish the environment before retrying the installer. Registry, editing, export and fixture-based renderer tests can run independently; a real Mojang download and full textured production-image test remain blocked until this network access works. Render uses its own network policy.

## MCP

`search_blocks(query, offset, limit)` exposes the same catalog and properties. `create_build` accepts `palette`, for example `{"wall":"cherry_planks","stair":"oxidized_cut_copper_stairs"}`. `edit_build(build_id, changes, replace)` creates an edited copy. Examples:

```json
{"build_id":"ID_FROM_CREATE_BUILD","changes":[{"x":15,"y":40,"z":15,"block":"cherry_stairs[facing=east]"}]}
```

```json
{"build_id":"ID_FROM_CREATE_BUILD","replace":{"from":"white_terracotta","to":"cherry_planks"}}
```
