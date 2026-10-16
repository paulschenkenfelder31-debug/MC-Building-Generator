"""Run against a started server: python tests/browser_smoke.py [base URL]."""
import os
import asyncio
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright
from mcp import Client


base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3000'
artifacts = Path(__file__).resolve().parent.parent / 'artifacts'
artifacts.mkdir(exist_ok=True)


async def assistant_build():
    async with Client(base + '/mcp') as client:
        result = await client.call_tool('create_build', {'style': 'modern', 'width': 23, 'depth': 19,
                                                       'floors': 1, 'seed': 123, 'title': 'MCP browser test villa'})
        assert not result.is_error
        return result.structured_content


assistant_design = asyncio.run(assistant_build())

with sync_playwright() as p:
    options = {'headless': True, 'args': ['--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    browser = p.chromium.launch(**options)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base)
    page.locator('#schem:not(.disabled)').wait_for(timeout=30000)
    assert page.locator('canvas').is_visible(), 'WebGL preview missing'
    assert page.locator('#error').is_hidden(), 'Initial generation failed'
    page.screenshot(path=str(artifacts / 'workbench-desktop.png'), full_page=True)
    page.locator('#layer').fill('8')
    page.locator('#layer').dispatch_event('input')
    assert page.locator('#layer-value').inner_text() == 'Layer 8'
    page.locator('[data-view=top]').click()
    assert page.locator('[data-view=top]').get_attribute('aria-pressed') == 'true'
    page.screenshot(path=str(artifacts / 'workbench-cutaway.png'), full_page=True)
    for fmt in ('schem', 'litematic', 'json'):
        with page.expect_download() as download:
            page.locator('#' + fmt).click()
        path = artifacts / download.value.suggested_filename
        download.value.save_as(path)
        assert path.stat().st_size > 500
    with page.expect_download() as download:
        page.locator('#snapshot').click()
    download.value.save_as(artifacts / 'preview-capture.png')
    for example, style in (('villa', 'modern'), ('temple', 'japanese')):
        page.locator(f'[data-example={example}]').click()
        with page.expect_response('**/api/generate') as response:
            page.locator('#generate').click()
        result = response.value.json()
        assert result['spec']['style'] == style
        page.locator('#loading').wait_for(state='hidden')
        assert page.locator('#error').is_hidden()
    page.locator('#terrain').uncheck()
    with page.expect_response('**/api/generate') as response:
        page.locator('#generate').click()
    result = response.value.json()
    assert not result['spec']['terrain']
    assert 'minecraft:grass_block' not in result['palette']
    page.locator('#loading').wait_for(state='hidden')
    page.locator('#prompt').fill('A 100x100 medieval house')
    with page.expect_response('**/api/generate') as response:
        page.locator('#generate').click()
    assert response.value.status == 400
    page.locator('#error').wait_for(state='visible')
    assert 'width' in page.locator('#error').inner_text()
    # The full library drives real edits, not just a decorative list.
    page.locator('#block-search').fill('cherry_stairs')
    page.locator('[data-block-id="minecraft:cherry_stairs"]').wait_for()
    page.locator('[data-block-id="minecraft:cherry_stairs"]').click()
    page.get_by_label('Block property facing', exact=True).select_option('east')
    assert 'facing=east' in page.locator('#selected-state').inner_text()
    page.locator('#assign-material').click()
    assert 'cherry_stairs' in page.locator('#custom-palette').inner_text()
    for axis, value in [('x', '15'), ('y', '40'), ('z', '15')]:
        page.locator('#block-' + axis).fill(value)
    with page.expect_response('**/api/builds/*/edit') as response:
        page.locator('#place-block').click()
    placed = response.value.json()
    assert response.value.status == 200
    assert any('cherry_stairs' in state and 'facing=east' in state for state in placed['palette'])
    page.wait_for_function("document.querySelector('#schem').href.includes(" + repr(placed['id']) + ")")
    page.locator('#block-search').fill('cherry_planks')
    page.locator('[data-block-id="minecraft:cherry_planks"]').wait_for()
    page.locator('[data-block-id="minecraft:cherry_planks"]').click()
    page.locator('#replace-from').select_option('minecraft:white_terracotta')
    with page.expect_response('**/api/builds/*/edit') as response:
        page.locator('#replace-material').click()
    replaced = response.value.json()
    assert response.value.status == 200
    assert 'minecraft:cherry_planks' in replaced['palette']
    assert 'minecraft:white_terracotta' not in replaced['palette']
    page.wait_for_function("document.querySelector('#schem').href.includes(" + repr(replaced['id']) + ")")
    with page.expect_response('**/api/builds/*/edit') as response:
        page.locator('#remove-block').click()
    removed = response.value.json()
    assert response.value.status == 200
    assert not any(b[:3] == [15, 40, 15] for b in removed['blocks'])
    page.wait_for_function("document.querySelector('#schem').href.includes(" + repr(removed['id']) + ")")
    page.locator('#undo-edit').click()
    page.wait_for_function("document.querySelector('#schem').href.includes(" + repr(replaced['id']) + ")")
    page.screenshot(path=str(artifacts / 'workbench-block-library.png'), full_page=True)
    assert errors == [], errors
    page.goto(assistant_design['preview_url'])
    page.locator('#schem:not(.disabled)').wait_for(timeout=30000)
    assert page.locator('#project-title').inner_text() == 'MCP browser test villa'
    assert page.locator('#mode-badge').inner_text() == 'ASSISTANT DESIGN'
    assert page.locator('#seed').input_value() == '123'
    assert page.locator('#style').input_value() == 'modern'
    assert page.locator('#schem').get_attribute('href').endswith(assistant_design['id'] + '/schem')
    page.locator('#assistant-connect summary').click()
    assert page.locator('#mcp-url').input_value() == base + '/mcp'
    page.screenshot(path=str(artifacts / 'workbench-mcp.png'), full_page=True)
    page.goto(base + '/?build=expired-build')
    page.locator('#error').wait_for(state='visible')
    assert 'expired' in page.locator('#error').inner_text().lower()
    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1)
    mobile.on('pageerror', lambda error: errors.append(str(error)))
    mobile.goto(base)
    mobile.locator('#schem:not(.disabled)').wait_for(timeout=30000)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile layout overflows horizontally'
    mobile.screenshot(path=str(artifacts / 'workbench-mobile.png'), full_page=True)
    assert errors == [], errors
    browser.close()
    print('Browser smoke passed: WebGL, cutaway, camera, downloads, 3 styles, terrain, catalog search, properties, palette assignment, placement, replacement, removal, undo, MCP links, mobile layout.')
