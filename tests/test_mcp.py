import gzip
import io
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from mcp import Client
import nbtlib

from mc_builder.builds import BuildStore, assistant_planning
from mc_builder.model import BuildSpec
from server_test_support import LiveServer


class MCPTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LiveServer().start()
        cls.base = cls.server.base

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    @patch('mc_builder.planner.ai_plan', side_effect=AssertionError('MCP must never call a model API'))
    async def test_real_sdk_client_create_preview_and_exports_without_model(self, model_call):
        async with Client(self.base + '/mcp') as client:
            tools = await client.list_tools()
            self.assertEqual({tool.name for tool in tools.tools}, {'get_building_capabilities', 'create_build', 'get_build', 'search_blocks', 'edit_build'})
            capabilities = await client.call_tool('get_building_capabilities', {})
            self.assertFalse(capabilities.structured_content['model_api_required'])
            result = await client.call_tool('create_build', {
                'style': 'medieval', 'width': 33, 'depth': 27, 'floors': 3,
                'title': 'Assistant-designed observatory', 'seed': 2026,
            })
            self.assertFalse(result.is_error)
            build = result.structured_content
            self.assertEqual(build['planning']['mode'], 'assistant')
            self.assertEqual(build['spec']['title'], 'Assistant-designed observatory')
            self.assertGreater(build['block_count'], 1000)
            self.assertNotIn('blocks', build, 'Do not flood the model context with individual blocks.')
            self.assertEqual(build['preview_url'], self.base + '/?build=' + build['id'])
            fetched = await client.call_tool('get_build', {'build_id': build['id']})
            self.assertEqual(fetched.structured_content['id'], build['id'])
        with urllib.request.urlopen(self.base + '/api/builds/' + build['id']) as response:
            payload = json.load(response)
        self.assertEqual(payload['block_count'], build['block_count'])
        self.assertTrue(payload['blocks'])
        for fmt, version in (('schem', 2), ('litematic', 6)):
            with urllib.request.urlopen(build['downloads'][fmt]) as response:
                root = nbtlib.File.parse(io.BytesIO(gzip.decompress(response.read())))
            self.assertEqual(root['Version'], version)
        model_call.assert_not_called()

    async def test_invalid_tool_parameters_and_unknown_build(self):
        async with Client(self.base + '/mcp') as client:
            for values in ({'width': 1000}, {'width': True}, {'style': 'invented'}, {'terrain': 'false'}):
                with self.subTest(values=values):
                    result = await client.call_tool('create_build', values)
                    self.assertTrue(result.is_error)
            result = await client.call_tool('get_build', {'build_id': 'not-a-build'})
            self.assertTrue(result.is_error)

    async def test_old_handshake_and_blocked_cross_origin(self):
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'compatibility-check', 'version': '1.0'},
        }}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        request = urllib.request.Request(self.base + '/mcp', data=json.dumps(message).encode(), headers=headers)
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        self.assertEqual(result['result']['serverInfo']['name'], 'Blockwright')
        request = urllib.request.Request(self.base + '/mcp', data=json.dumps(message).encode(), headers={**headers, 'Origin': 'https://untrusted.example'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    async def test_missing_build_has_clear_http_error(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + '/api/builds/missing')
        self.assertEqual(caught.exception.code, 404)

    async def test_render_hostname_links_and_request_size_limit(self):
        public_origin = 'https://blockwright-hostname-test.onrender.com'
        server = LiveServer(public_origin).start()
        try:
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                       'Host': 'blockwright-hostname-test.onrender.com', 'MCP-Protocol-Version': '2025-03-26'}
            message = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
                'name': 'create_build', 'arguments': {'title': 'Forwarded-host build'},
            }}
            request = urllib.request.Request(server.base + '/mcp', data=json.dumps(message).encode(), headers=headers)
            with urllib.request.urlopen(request) as response:
                result = json.load(response)['result']
            self.assertFalse(result.get('isError'))
            self.assertTrue(result['structuredContent']['preview_url'].startswith(public_origin + '/?build='))
            request = urllib.request.Request(server.base + '/mcp', data=b'x' * 17000, headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 413)
        finally:
            server.stop()


class BuildStoreTests(unittest.TestCase):
    def test_expired_builds_are_not_replaced_with_another_users_build(self):
        store = BuildStore(capacity=1)
        first = store.create(BuildSpec(), assistant_planning())
        second = store.create(BuildSpec(seed=43), assistant_planning())
        self.assertIsNone(store.get(first['id']))
        self.assertEqual(store.get(second['id'])[2]['spec']['seed'], 43)
