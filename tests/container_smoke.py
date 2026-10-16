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
assert os.getuid()==10001
assert not any(Path(p).exists() for p in ('/app/.env','/app/.git','/run/secrets/build_ca'))
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
        with urllib.request.urlopen(build['downloads']['schem']) as response:
            assert response.read(2)==b'\\x1f\\x8b'
asyncio.run(verify_mcp())
print('Container smoke passed: custom PORT, non-root user, UI assets, 3 styles, both Minecraft exports, real MCP tool call, no build CA or credentials in runtime.')
'''

subprocess.run(['docker', 'run', '-d', '--name', name, '-e', 'PORT=10001', image], check=True, stdout=subprocess.DEVNULL)
try:
    result = subprocess.run(['docker', 'exec', '-i', name, 'python', '-'], input=script, text=True)
    if result.returncode:
        subprocess.run(['docker', 'logs', name])
        raise SystemExit(result.returncode)
finally:
    subprocess.run(['docker', 'rm', '-f', name], check=True, stdout=subprocess.DEVNULL)
