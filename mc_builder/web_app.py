"""Browser API and official Streamable HTTP MCP on one hosting port."""
import json
import os
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .builds import BuildStore
from .exporters import litematic, schematic
from .mcp_tools import create_mcp, origin_url, transport_security
from .planner import plan
from .catalog import DATA_VERSION, VERSION, catalog_page


ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 16384


def create_app(public_base_url=None, assets_directory=None):
    assets = Path(assets_directory) if assets_directory is not None else ROOT / 'minecraft-assets'
    asset_manifest = None
    try:
        manifest = json.loads((assets / 'manifest.json').read_text())
        if (isinstance(manifest, dict) and manifest.get('version') == VERSION and manifest.get('data_version') == DATA_VERSION
                and (assets / 'atlas.png').is_file() and (assets / 'models.json').is_file()):
            asset_manifest = manifest
    except (OSError, ValueError):
        pass
    base_url = origin_url(public_base_url if public_base_url is not None else
                          os.environ.get('PUBLIC_BASE_URL', os.environ.get('RENDER_EXTERNAL_URL', '')))
    store = BuildStore()
    mcp = create_mcp(store, base_url)
    app = mcp.streamable_http_app(
        stateless_http=True, json_response=True, max_request_body_size=MAX_BODY,
        transport_security=transport_security(base_url),
    )
    app.state.builds = store
    app.state.mcp = mcp

    def json_response(value, status=200):
        return JSONResponse(value, status_code=status, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    async def health(request):
        return json_response({'application': 'blockwright', 'status': 'ok',
                              'ai_configured': bool(os.environ.get('OPENAI_API_KEY')),
                              'minecraft_version': f'Java {VERSION}', 'mcp_endpoint': '/mcp', 'mcp_version': '0.3.0'})

    async def block_catalog(request):
        try:
            return json_response(catalog_page(request.query_params.get('q', ''),
                int(request.query_params.get('offset', 0)), int(request.query_params.get('limit', 60))))
        except (ValueError, TypeError) as error:
            return json_response({'error': str(error)}, 400)

    async def asset_status(request):
        if asset_manifest is not None:
            return json_response(asset_manifest | {'available': True})
        return json_response({'available': False, 'version': VERSION,
            'message': f'Original Java {VERSION} textures are not installed on this server. Preview uses color placeholders.'})

    async def edit_build(request):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            return json_response({'error': 'Use Content-Type: application/json.'}, 415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return json_response({'error': 'Request exceeds 16,384 bytes.'}, 413)
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError('Edits must be a JSON object.')
            payload = await run_in_threadpool(store.edit, request.path_params['build_id'], data.get('changes'), data.get('replace'))
            return json_response(payload)
        except (ValueError, TypeError) as error:
            return json_response({'error': str(error)}, 400)

    async def generate_build(request):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            return json_response({'error': 'Use Content-Type: application/json.'}, 415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return json_response({'error': 'Request must be 1–16,384 bytes.'}, 413)
        if not body:
            return json_response({'error': 'Request must be 1–16,384 bytes.'}, 413)
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError('Request must be a JSON object.')
            spec, planning = await run_in_threadpool(plan, data.get('prompt', ''), data.get('overrides'), data.get('mode', 'offline'))
            payload = await run_in_threadpool(store.create, spec, planning)
            return json_response(payload)
        except (ValueError, TypeError) as error:
            return json_response({'error': str(error)}, 400)
        except RuntimeError as error:
            return json_response({'error': str(error)}, 502)

    async def get_build(request):
        build = store.get(request.path_params['build_id'])
        if build is None:
            return json_response({'error': 'Build expired or unknown. Generate it again.'}, 404)
        return json_response(build[2])

    async def download(request):
        fmt = request.path_params['format']
        if fmt not in ('schem', 'litematic', 'json'):
            return json_response({'error': 'Unknown export.'}, 404)
        build = store.get(request.path_params['build_id'])
        if build is None:
            return json_response({'error': 'Build expired. Generate it again.'}, 404)
        spec, world, payload = build
        if fmt == 'json':
            data = json.dumps(payload).encode()
        else:
            data = await run_in_threadpool(schematic if fmt == 'schem' else litematic, world, spec.title)
        return Response(data, media_type='application/json' if fmt == 'json' else 'application/octet-stream', headers={
            'Content-Disposition': f'attachment; filename="building-{spec.seed}.{fmt}"',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        })

    async def missing_api(request):
        return json_response({'error': 'Unknown endpoint.'}, 404)

    async def frontend_missing(request):
        return json_response({'error': 'Frontend not built. Run npm ci && npm run build, or use npm run dev.'}, 503)

    app.routes.extend([
        Route('/api/health', health),
        Route('/api/blocks', block_catalog),
        Route('/api/assets', asset_status),
        Route('/api/generate', generate_build, methods=['POST']),
        Route('/api/builds/{build_id}/edit', edit_build, methods=['POST']),
        Route('/api/builds/{build_id}/{format}', download),
        Route('/api/builds/{build_id}', get_build),
        Route('/api/{path:path}', missing_api, methods=['GET', 'POST']),
    ])
    if asset_manifest is not None:
        app.routes.append(Mount('/minecraft-assets', app=StaticFiles(directory=assets)))
    if (ROOT / 'dist/index.html').is_file():
        app.routes.append(Mount('/', app=StaticFiles(directory=ROOT / 'dist', html=True)))
    else:
        app.routes.append(Route('/{path:path}', frontend_missing))
    return app
