"""Official MCP SDK tools: the calling assistant supplies the architecture."""
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from anyio import to_thread
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field, StrictBool

from .builds import assistant_planning, summary
from .model import BuildSpec


def origin_url(value):
    value = value.rstrip('/')
    if not value:
        return ''
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('PUBLIC_BASE_URL must be an HTTP(S) origin without credentials, path, query, or fragment.')
    return value


def create_mcp(store, public_base_url=''):
    base_url = origin_url(public_base_url)
    server = MCPServer(
        'Blockwright', version='0.2.0',
        instructions=(
            'You are the architect. Interpret the user building request into supported parameters and call '
            'create_build. First use get_building_capabilities if unsure. Geometry uses curated templates, '
            'not arbitrary architecture. Do not promise unsupported features, a vision review, or quality scores. '
            'Return the preview and download links to the user. No model API call or sampling request is made '
            'by this server; reasoning comes from the assistant using these tools.'
        ),
    )
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @server.tool(annotations=read_only, structured_output=True)
    def get_building_capabilities() -> dict[str, Any]:
        """Read supported architecture, parameter limits, and export formats before planning a building."""
        return {
            'styles': ['medieval', 'modern', 'japanese'], 'footprint': {'minimum': 15, 'maximum': 65},
            'main_floors': {'minimum': 1, 'maximum': 3},
            'tower': 'Medieval only, width >=25; adds two tower storeys.',
            'seed': '0..2147483647; varies foundation materials, not the layout.',
            'features': ['foundations', 'windows', 'stairs', 'doors', 'basic furnishings', 'optional landscape'],
            'exports': ['Sponge v2 .schem', 'Litematica v6 .litematic', 'JSON'],
            'minecraft_version': 'Java 1.20.1', 'model_api_required': False,
            'unsupported': ['arbitrary floor plans', 'reference images', 'vision critique', 'automatic refinement'],
        }

    @server.tool(structured_output=True, annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
    async def create_build(
        style: Literal['medieval', 'modern', 'japanese'] = 'medieval',
        width: Annotated[int, Field(ge=15, le=65, strict=True)] = 29,
        depth: Annotated[int, Field(ge=15, le=65, strict=True)] = 25,
        floors: Annotated[int, Field(ge=1, le=3, strict=True)] = 2,
        tower: StrictBool = True,
        terrain: StrictBool = True,
        seed: Annotated[int, Field(ge=0, le=2147483647, strict=True)] = 42,
        title: Annotated[str, Field(min_length=1, max_length=100, strict=True)] = 'Assistant-designed building',
    ) -> dict[str, Any]:
        """Generate Minecraft blocks from your architectural design; return a 3D preview and real schematic downloads. No model API is called. This creates an in-memory build and does not edit a Minecraft world."""
        spec = BuildSpec.from_dict(dict(style=style, width=width, depth=depth, floors=floors,
                                        tower=tower, terrain=terrain, seed=seed, title=title))
        payload = await to_thread.run_sync(store.create, spec, assistant_planning())
        return summary(payload, base_url)

    @server.tool(annotations=read_only, structured_output=True)
    def get_build(build_id: str) -> dict[str, Any]:
        """Get preview/download links and materials for a previously created build ID; expired builds must be regenerated."""
        build = store.get(build_id)
        if build is None:
            raise ToolError('Build expired or unknown. Call create_build again.')
        return summary(build[2], base_url)

    return server


def transport_security(public_base_url):
    hosts = ['127.0.0.1:*', 'localhost:*', '[::1]:*']
    origins = ['http://127.0.0.1:*', 'http://localhost:*', 'https://chatgpt.com']
    if public_base_url:
        parsed = urlsplit(public_base_url)
        hosts.append(parsed.netloc)
        origins.append(public_base_url)
    return TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins)
