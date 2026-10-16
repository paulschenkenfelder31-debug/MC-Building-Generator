"""Start the browser API and MCP tools on a single HTTP port."""
import argparse
import os

import uvicorn

from .web_app import ROOT, create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8000')))
    args = parser.parse_args()
    base_url = os.environ.get('PUBLIC_BASE_URL') or os.environ.get('RENDER_EXTERNAL_URL') or f'http://127.0.0.1:{args.port}'
    uvicorn.run(create_app(base_url), host=args.host, port=args.port, limit_concurrency=16)


if __name__ == '__main__':
    main()
