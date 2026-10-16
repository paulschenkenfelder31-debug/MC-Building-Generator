from dataclasses import asdict
import json
import os
import re
import urllib.error
import urllib.request

from .model import BuildSpec, STYLES


def plan(prompt, overrides=None, mode='offline'):
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
        raise ValueError('Describe your building in 1–2,000 characters.')
    if mode not in ('offline', 'ai'):
        raise ValueError('Unknown planning mode.')
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError('Design overrides must be an object.')
    if mode == 'ai':
        data = ai_plan(prompt)
    else:
        text = prompt.lower()
        style = 'medieval'
        if any(w in text for w in ('modern', 'concrete', 'minimalist', 'villa')):
            style = 'modern'
        if any(w in text for w in ('japan', 'pagoda', 'temple', 'shrine', 'tempel')):
            style = 'japanese'
        data = asdict(BuildSpec(style=style, tower=style == 'medieval'))
        sizes = re.search(r'\b(\d{1,3})\s*[x×]\s*(\d{1,3})\b', text)
        if sizes:
            data.update(width=int(sizes[1]), depth=int(sizes[2]))
        floors = re.search(r'\b([1-3])\s*(?:floors?|stor(?:y|ies)|storeys?|geschosse?|etagen?)', text)
        if floors:
            data['floors'] = int(floors[1])
        if any(w in text for w in ('one floor', 'single story', 'single storey', 'cottage', 'cabin', 'hütte')):
            data['floors'] = 1
        if any(w in text for w in ('no tower', 'without a tower', 'ohne turm')):
            data['tower'] = False
        if any(w in text for w in ('no terrain', 'without terrain', 'ohne terrain')):
            data['terrain'] = False
        data['title'] = {'medieval': 'Timber & stone manor', 'modern': 'Concrete & glass villa', 'japanese': 'Dark timber pavilion'}[style]
    data.update({k: v for k, v in (overrides or {}).items() if k in asdict(BuildSpec()) and v is not None})
    spec = BuildSpec.from_dict(data)
    return spec, {
        'mode': mode,
        'description': 'AI architectural planning with bounded procedural geometry.' if mode == 'ai' else 'Offline keyword planner with curated procedural templates; no AI model used.',
        'supported_styles': list(STYLES),
        'limitations': ['Prompts select a template and its parameters; arbitrary architecture and reference images are not supported yet.', 'No vision critique loop or quality scores are implemented.'],
    }


def ai_plan(prompt):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('AI planning requires OPENAI_API_KEY on the server. Offline mode works without it.')
    instruction = (
        'You plan Minecraft buildings. Return only a JSON object with these fields: '
        'style (medieval, modern, japanese), width (integer 15..65), depth (integer 15..65), '
        'floors (integer 1..3), tower (boolean, medieval only, width >=25), terrain (boolean), '
        'seed (integer 0..2147483647), title (1..100 characters). '
        'These are the only implemented features. Interpret the prompt within these bounds; '
        'do not claim additional features. Roofs, windows, interiors, and stairs are procedural.'
    )
    body = json.dumps({
        'model': os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
        'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'},
        'max_completion_tokens': 500,
    }).encode()
    request = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=body, headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        return json.loads(result['choices'][0]['message']['content'])
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError('AI planning failed. Check server credentials, network access, and model availability, or use offline mode.') from exc
