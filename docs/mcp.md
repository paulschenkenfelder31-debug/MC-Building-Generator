# Use ChatGPT or Codex as the architect, without a model API key

MCP connects an assistant to the building generator. The assistant interprets the user's description and supplies the design parameters. The generator then creates blocks and exports them. **The MCP server never calls a model provider or requests model sampling.** Your assistant still needs its normal model access, and its subscription/usage limits still apply.

This is a chat-driven workflow: the user describes a building in ChatGPT/Codex and the assistant calls a tool. The website cannot call your ChatGPT subscription, run a model through MCP, or autonomously generate AI plans without a model provider. Its offline generation button remains available independently.

## Connect

1. Deploy the current `deploy/public-demo` branch on Render. If the service does not deploy commits automatically, use Render's manual deployment of the latest commit.
2. Open the website and expand **Build with ChatGPT or Codex**. Copy the **MCP server address**. It is your actual site's HTTPS origin followed by `/mcp`.
3. In an MCP-capable assistant, add that address as a remote **Streamable HTTP** MCP server. The current public demo uses **no authentication** and needs no OpenAI API key.
4. Enable the connected tools in the conversation. Ask: “Use Blockwright to build a 33×27 medieval observatory with three floors, a corner tower, and seed 2026. Return the preview and both Minecraft downloads.”
5. Open the returned preview link and download the `.schem` or `.litematic` file.

For Codex clients that support remote MCP configuration, an example CLI command is:

```bash
codex mcp add blockwright --url "PASTE_THE_COPIED_MCP_ADDRESS_HERE"
```

Or add the following to the client's MCP configuration, replacing the placeholder with the copied address:

```toml
[mcp_servers.blockwright]
url = "PASTE_THE_COPIED_MCP_ADDRESS_HERE"
```

For ChatGPT, custom MCP apps/developer-mode availability depends on the account and workspace. If those settings are available, create a custom MCP app with the copied address and authentication set to **None**, then enable it in a chat. A client that requires OAuth or does not offer custom MCP connections cannot use this public endpoint just by pasting a URL into a normal message. Deploying the server does not automatically connect it to the current chat.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_building_capabilities` | Describe the three styles, supported dimensions, features, and formats. |
| `create_build` | Generate a new build from the assistant's validated architectural parameters. |
| `get_build` | Retrieve links and materials for a known, unexpired build ID. |
| `search_blocks` | Search all 1,286 vanilla block IDs and state properties (Java 26.3). |
| `edit_build` | Place/remove blocks or replace a material in a new copy of a build. |

Example `create_build` arguments:

```json
{
  "style": "medieval",
  "width": 33,
  "depth": 27,
  "floors": 3,
  "tower": true,
  "terrain": true,
  "seed": 2026,
  "title": "Wizard observatory",
  "palette": {"wall": "cherry_planks", "stair": "oxidized_cut_copper_stairs"}
}
```

The tool returns a summary, materials, validation, a preview link, and downloads. It does not send thousands of individual blocks into the model context. The preview link loads the same build via `/api/builds/{id}`; it does not regenerate a replacement.

## Limits and hosting

Supported architecture remains template-based: medieval, modern, and Japanese-inspired; footprints 15–65 per side; 1–3 main floors. Reference images, arbitrary floor plans, and vision critique are not implemented. The assistant can choose building materials and edit individual blocks through the complete registry. See [block edit examples and limits](blocks-and-textures.md#mcp). The initial building layout remains template-based.

Builds are stored in the same eight-entry memory cache used by the browser. Restarts, Render free-service sleeping/restarts, and newer builds can expire links. Download files promptly; ask the assistant to regenerate if a link expires. Old IDs return a clear error rather than a different user's build. No global build-list tool is exposed.

Render provides `RENDER_EXTERNAL_URL`, which supplies absolute preview/download URLs and the trusted public MCP host. Other hosts should set the non-secret `PUBLIC_BASE_URL` to their actual HTTPS origin. Keep DNS rebinding protection enabled. The MCP endpoint permits local development hosts and the configured public origin; it does not trust arbitrary Host/Origin headers. The service and MCP endpoint use the same public hosting port.

The current demo endpoint is public like the existing generator: it has no account isolation or OAuth. It accepts bounded design parameters and generates builds, not executable code or world-edit commands. A deployment needing private builds should add authentication and durable per-user storage before promising privacy.

## Verification

Run `npm test`, `npm run build`, the browser smoke test, and the container smoke test. Tests use the official MCP client to discover tools, create a build, fetch its preview data, and decode both Minecraft exports. A mocked model-provider function fails the test if MCP accidentally calls it. Older initialization, invalid arguments, untrusted origins, expired builds, and browser deep links are covered.

Client registration and use inside the user's actual ChatGPT/Codex account require that client to be configured separately; local protocol tests do not prove that account integration is complete.
