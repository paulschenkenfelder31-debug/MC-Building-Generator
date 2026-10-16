# Public demo hosting without a custom domain

Render can run this Python API and compiled frontend together, using its own HTTPS address under `onrender.com`. The repository includes `Dockerfile` and `render.yaml` for a free-plan web service. A Render account and repository access are required; no custom domain, database, or AI API key is required.

For the complete block catalog and original artwork update, see [the Python-runtime build command and texture setup](blocks-and-textures.md#render).

## Deployment

1. Select the `deploy/public-demo` branch, where the application files, `Dockerfile`, and `render.yaml` are committed. `main` may still contain only the original README.
2. Sign in at https://dashboard.render.com/ with GitHub and grant access to this repository.
3. Create a Blueprint using that repository and branch. Review the service preview; `render.yaml` requests the **free** plan. Do not select a paid plan unless you intend to pay for it.
4. Deploy the service. Render builds the frontend in a Node stage, downloads verified original Minecraft artwork in a second build stage, installs Python dependencies in the final stage, and starts the app as a non-root user. The server honors Render's `PORT` variable.
5. Copy the HTTPS address Render actually assigns. The app is published only after a real request to that address succeeds; the URL cannot be predicted from the service name.
6. Check `/api/health`, generate a building in the browser, and download both Minecraft formats.

Free services may sleep when idle and take time to wake. Availability and limits depend on Render's current free-plan terms. Builds remain in memory, with the last eight available for download; restarts clear them. This is a public prototype with offline procedural generation. Do not add a paid AI API key to a public instance without implementing access and usage controls.

No hosting account has been connected and no Render deployment has been created by these configuration files alone. Do not put hosting passwords or tokens in the repository or chat.

## Local container verification

```bash
docker build -t blockwright-demo .
python3 tests/container_smoke.py blockwright-demo
docker run --rm --name blockwright-demo -p 3000:10000 blockwright-demo
```

The final image includes the API and compiled frontend, not the Git checkout, `.env` files, development tools, or local artifacts.

The same public port also serves `/mcp`. The official MCP SDK runs alongside the browser API under Uvicorn. Render's `RENDER_EXTERNAL_URL` supplies absolute build links and the trusted MCP hostname; no additional exposed port or model API key is needed. See [connecting an assistant](mcp.md).

The smoke test checks a custom `PORT`, the non-root runtime user, frontend assets, all three building styles, and both Minecraft download formats. In this Codex runtime the Docker build also needs the provided proxy passed with Docker's standard `HTTP_PROXY`/`HTTPS_PROXY` build arguments, its hostname mapped into the build network, and the existing trusted CA bundle passed as the optional BuildKit secret `build_ca`. That CA is used only during dependency installation and is not retained in the final image. Do not disable TLS checks to build behind a proxy.

## Codex tunnel limitation

The attempted Cloudflare Quick Tunnel failed even after its domain allowlist was saved. Direct DNS resolution was unavailable both inside and outside the command sandbox, while requests through the provided HTTPS proxy returned CONNECT 403. A public tunnel address was not created. This is not evidence that the user entered the domains incorrectly. Do not ask for the same allowlist again without new evidence; use a hosting service or a platform-supported preview URL.
