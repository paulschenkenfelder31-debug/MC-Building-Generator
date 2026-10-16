"""Exercise the artwork pipeline with synthetic pixels; does not validate Mojang downloads."""
import io
import os
from pathlib import Path
import tempfile
import zipfile
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from playwright.sync_api import sync_playwright

from server_test_support import LiveServer
from scripts.prepare_minecraft_assets import package


with tempfile.TemporaryDirectory(prefix='blockwright-texture-fixture-') as temporary:
    folder = Path(temporary)
    png = io.BytesIO()
    image = Image.new('RGBA', (16, 16), '#c96d24')
    for x in range(8):
        for y in range(8):
            image.putpixel((x, y), (240, 200, 70, 255))
    image.save(png, format='PNG')
    model = {'textures': {'all': 'minecraft:block/fixture', 'particle': '#all'}, 'elements': [
        {'from': [0,0,0], 'to': [16,16,16], 'faces': {
            side: {'texture': '#all', 'cullface': side} for side in ['east','west','up','down','north','south']}}]}
    with zipfile.ZipFile(folder / 'fixture.jar', 'w') as jar:
        jar.writestr('assets/minecraft/textures/block/fixture.png', png.getvalue())
        jar.writestr('assets/minecraft/models/block/fixture.json', json.dumps(model))
        for name in ['stone', 'stone_bricks', 'spruce_planks', 'white_terracotta']:
            jar.writestr(f'assets/minecraft/blockstates/{name}.json', '{"variants":{"":{"model":"minecraft:block/fixture"}}}')
    package(folder / 'fixture.jar', folder / 'assets', {'client_sha1': 'synthetic-fixture-only'})
    server = LiveServer(assets_directory=folder / 'assets').start()
    try:
        with sync_playwright() as p:
            options = {'headless': True, 'args': ['--enable-unsafe-swiftshader']}
            if os.environ.get('CHROMIUM_PATH'):
                options['executable_path'] = os.environ['CHROMIUM_PATH']
            browser = p.chromium.launch(**options)
            page = browser.new_page(viewport={'width':1440, 'height':1000})
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(server.base)
            page.locator('#schem:not(.disabled)').wait_for(timeout=30000)
            page.wait_for_function("document.querySelector('#texture-status').textContent.includes('1 original')")
            page.locator('#block-search').fill('stone_bricks')
            page.locator('[data-block-id="minecraft:stone_bricks"]').wait_for()
            icon = page.locator('[data-block-id="minecraft:stone_bricks"] .block-icon')
            assert 'fixture.png' in icon.evaluate('e => getComputedStyle(e).backgroundImage')
            assert page.request.get(server.base + '/minecraft-assets/atlas.png').status == 200
            page.locator('canvas').scroll_into_view_if_needed()
            box = page.locator('canvas').bounding_box()
            # A visible wall/roof should be pickable with merged textured geometry.
            hit = False
            for fx, fy in [(.5,.5),(.5,.6),(.4,.55),(.6,.55)]:
                page.mouse.click(box['x']+box['width']*fx, box['y']+box['height']*fy)
                if 'Selected block at' in page.locator('#edit-status').inner_text():
                    hit = True; break
            assert hit, 'Could not pick a block from the rendered geometry'
            page.locator('#block-search').fill('copper_block')
            page.locator('[data-block-id="minecraft:copper_block"]').wait_for()
            page.locator('[data-block-id="minecraft:copper_block"]').click()
            page.locator('#edit-mode').select_option('place')
            page.locator('canvas').scroll_into_view_if_needed()
            with page.expect_response('**/api/builds/*/edit') as response:
                page.mouse.click(box['x']+box['width']*fx, box['y']+box['height']*fy)
            assert response.value.status == 200, response.value.text()
            assert any('copper_block' in state for state in response.value.json()['palette'])
            assert not errors, errors
            Path('artifacts').mkdir(exist_ok=True)
            page.locator('#viewport').screenshot(path='artifacts/synthetic-texture-preview.png')
            browser.close()
    finally:
        server.stop()
print('Synthetic texture fixture passed: extraction, atlas, asset serving, model loading, textured WebGL, icons and click placement. Real Mojang download remains a separate check.')
