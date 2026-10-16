"""Verify a built hosting image: python tests/container_smoke.py [image]."""
import os
import subprocess
import sys
import uuid


name = 'blockwright-check-' + uuid.uuid4().hex[:10]
image = sys.argv[1] if len(sys.argv) > 1 else 'blockwright-demo'
script = '''import asyncio,gzip,io,json,os,re,time,urllib.request
from pathlib import Path
import nbtlib
from mcp import Client
base='http://127.0.0.1:10001'
for attempt in range(50):
    try:
        with urllib.request.urlopen(base+'/api/health',timeout=1) as response:
            health=json.load(response)
        break
    except OSError:
        time.sleep(.1)
else:
    raise RuntimeError('Container never became ready')
assert health['application']=='blockwright' and not health['ai_configured']
assert health['mcp_endpoint']=='/mcp'
assert health['minecraft_version']=='Java 26.3'
assert os.getuid()==10001
assert not any(Path(p).exists() for p in ('/app/.env','/app/.git','/run/secrets/build_ca'))
with urllib.request.urlopen(base+'/api/blocks?limit=1') as response:
    catalog=json.load(response)
assert catalog['block_count']==1286 and catalog['data_version']==5023
with urllib.request.urlopen(base+'/api/assets') as response:
    artwork=json.load(response)
assert artwork['available'] and artwork['version']=='26.3'
assert artwork['texture_count']>1000 and re.fullmatch('[0-9a-f]{40}',artwork['client_sha1'])
with urllib.request.urlopen(base+'/minecraft-assets/atlas.png') as response:
    assert response.read(8)==b'\\x89PNG\\r\\n\\x1a\\n'
with urllib.request.urlopen(base+'/minecraft-assets/models.json') as response:
    models=json.load(response)
assert len(models['blockstates'])>1000 and len(models['textures'])>1000
with urllib.request.urlopen(base+'/') as response:
    html=response.read().decode()
assert 'Blockwright' in html
assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',html)
assert len(assets)>=2
for asset in assets:
    with urllib.request.urlopen(base+asset) as response:
        assert response.status==200
for style in ('medieval','modern','japanese'):
    request=urllib.request.Request(base+'/api/generate',data=json.dumps({'prompt':f'A {style} 29x25 building with 2 floors'}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response:
        build=json.load(response)
    assert build['validation']['passed'] and build['block_count']>1000
    for fmt,version in (('schem',2),('litematic',6)):
        with urllib.request.urlopen(base+'/api/builds/'+build['id']+'/'+fmt) as response:
            root=nbtlib.File.parse(io.BytesIO(gzip.decompress(response.read())))
        assert root['Version']==version
async def verify_mcp():
    async with Client(base+'/mcp') as client:
        result=await client.call_tool('create_build',{'title':'Container MCP build','style':'modern'})
        assert not result.is_error
        build=result.structured_content
        assert build['preview_url']==base+'/?build='+build['id']
        catalog=await client.call_tool('search_blocks',{'query':'cherry_stairs'})
        assert catalog.structured_content['total']==1
        edited=await client.call_tool('edit_build',{'build_id':build['id'],'changes':[{'x':15,'y':40,'z':15,'block':'copper_block'}]})
        assert not edited.is_error and edited.structured_content['id']!=build['id']
        with urllib.request.urlopen(build['downloads']['schem']) as response:
            assert response.read(2)==b'\\x1f\\x8b'
asyncio.run(verify_mcp())
print('Container smoke passed: custom PORT, non-root user, UI assets, complete catalog, installed Mojang artwork, 3 styles, exports, MCP catalog/editing, no build CA or credentials in runtime.')
'''

subprocess.run(['docker', 'run', '-d', '--name', name, '-e', 'PORT=10001', image], check=True, stdout=subprocess.DEVNULL)
try:
    result = subprocess.run(['docker', 'exec', '-i', name, 'python', '-'], input=script, text=True)
    if result.returncode:
        subprocess.run(['docker', 'logs', name])
        raise SystemExit(result.returncode)
finally:
    subprocess.run(['docker', 'rm', '-f', name], check=True, stdout=subprocess.DEVNULL)
