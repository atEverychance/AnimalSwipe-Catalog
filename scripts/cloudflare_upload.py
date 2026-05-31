#!/usr/bin/env python3
"""Upload signed AnimalSwipe catalog artifacts to a Cloudflare R2 bucket via Wrangler."""
from __future__ import annotations
import argparse, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd: list[str], dry_run: bool) -> None:
    print('+', ' '.join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket', default='animalswipe-catalog-staging')
    parser.add_argument('--version', type=int, default=1)
    parser.add_argument('--source-app-repo', default='../AnimalSwipe')
    parser.add_argument('--include-assets', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    dist = ROOT / 'dist'
    uploads = [
        (dist / 'latest.json', 'latest.json', 'application/json; charset=utf-8'),
        (dist / f'catalog-v{args.version:04d}.json', f'catalog/catalog-v{args.version:04d}.json', 'application/json; charset=utf-8'),
        (dist / f'assets-manifest-v{args.version:04d}.json', f'catalog/assets-manifest-v{args.version:04d}.json', 'application/json; charset=utf-8'),
    ]
    if args.include_assets:
        import json
        app_repo = (ROOT / args.source_app_repo).resolve()
        manifest = json.loads((dist / f'assets-manifest-v{args.version:04d}.json').read_text())
        for asset in manifest['assets']:
            source = app_repo / asset['sourceRelativePath']
            uploads.append((source, asset['remotePath'], asset.get('contentType') or 'image/jpeg'))
    for source, key, content_type in uploads:
        if not source.exists(): raise SystemExit(f'missing upload source: {source}')
        run(['wrangler', 'r2', 'object', 'put', f'{args.bucket}/{key}', '--file', str(source), '--content-type', content_type, '--remote'], args.dry_run)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
