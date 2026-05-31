#!/usr/bin/env python3
"""Prepare a signed AnimalSwipe catalog manifest using OpenSSL P-256 ECDSA.

Private key stays outside the repo by default: ~/.animalswipe/catalog-signing-key-p256.pem
"""
from __future__ import annotations
import argparse, base64, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY = Path.home() / '.animalswipe' / 'catalog-signing-key-p256.pem'
PUBLIC_KEY = ROOT / 'keys' / 'catalog-public-key-p256.pem'

def read_json(path: Path) -> Any:
    return json.loads(path.read_text())

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def ensure_key(private_key: Path) -> None:
    private_key.parent.mkdir(parents=True, exist_ok=True)
    if not private_key.exists():
        run(['openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', str(private_key)])
        private_key.chmod(0o600)
    PUBLIC_KEY.parent.mkdir(parents=True, exist_ok=True)
    run(['openssl', 'ec', '-in', str(private_key), '-pubout', '-out', str(PUBLIC_KEY)])

def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def find_source(app_repo: Path, rel: str | None, filename: str) -> Path | None:
    candidates=[]
    if rel: candidates.append(app_repo / rel)
    candidates.extend([
        app_repo / 'Content/images' / filename,
        app_repo / 'AnimalSwipe/Resources/AnimalPhotos' / filename,
        app_repo / 'AnimalSwipe/Resources/PackPhotos' / filename,
        app_repo / 'AnimalSwipe/Resources/StarterPhotos' / filename,
    ])
    for candidate in candidates:
        if candidate.exists(): return candidate
    return None

def update_assets(root: Path, app_repo: Path, version: int) -> None:
    catalog_path = root / 'dist' / f'catalog-v{version:04d}.json'
    assets_path = root / 'dist' / f'assets-manifest-v{version:04d}.json'
    catalog = read_json(catalog_path)
    assets_manifest = read_json(assets_path)
    updated=[]
    for asset in assets_manifest['assets']:
        source = find_source(app_repo, asset.get('sourceRelativePath'), asset['fileName'])
        if source is None:
            raise SystemExit(f"missing source asset for {asset['animalID']}: {asset['fileName']}")
        item = dict(asset)
        item['sha256'] = sha256_bytes(source)
        item['byteSize'] = source.stat().st_size
        item['contentType'] = 'image/jpeg'
        item['remotePath'] = f"assets/{item['fileName']}"
        updated.append(item)
    assets_manifest['assets'] = updated
    catalog['assets'] = updated
    write_json(assets_path, assets_manifest)
    write_json(catalog_path, catalog)

def sign(private_key: Path, catalog_path: Path) -> str:
    sig_path = catalog_path.with_suffix(catalog_path.suffix + '.sig')
    run(['openssl', 'dgst', '-sha256', '-sign', str(private_key), '-out', str(sig_path), str(catalog_path)])
    run(['openssl', 'dgst', '-sha256', '-verify', str(PUBLIC_KEY), '-signature', str(sig_path), str(catalog_path)])
    sig = base64.b64encode(sig_path.read_bytes()).decode('ascii')
    sig_path.unlink(missing_ok=True)
    return sig

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-app-repo', help='optional app repo used to refresh local asset hashes before signing')
    parser.add_argument('--version', type=int, default=1)
    parser.add_argument('--private-key', default=str(DEFAULT_KEY))
    parser.add_argument('--manifest-url-base', default='catalog')
    parser.add_argument('--channel', choices=['staging', 'production'], default='staging')
    parser.add_argument('--min-app-version', default='0.2.0')
    args = parser.parse_args()
    root = ROOT
    private_key = Path(args.private_key).expanduser().resolve()
    ensure_key(private_key)
    if args.source_app_repo:
        update_assets(root, Path(args.source_app_repo).resolve(), args.version)
    catalog_path = root / 'dist' / f'catalog-v{args.version:04d}.json'
    if not catalog_path.exists():
        raise SystemExit(f'missing catalog artifact: {catalog_path}; run scripts/build_catalog.py first')
    digest = sha256_bytes(catalog_path)
    signature = sign(private_key, catalog_path)
    latest = {
        'schemaVersion': 1,
        'catalogVersion': args.version,
        'publishedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'minAppVersion': args.min_app_version,
        'manifestURL': f"{args.manifest_url_base}/catalog-v{args.version:04d}.json",
        'manifestSHA256': digest,
        'signatureAlgorithm': 'P256.ECDSA.SHA256',
        'signatureFormat': 'base64-der',
        'signature': signature,
        'stagingOnly': args.channel != 'production',
        'channel': args.channel,
        'keyID': 'catalog-p256-v1'
    }
    write_json(root / 'dist/latest.json', latest)
    print(f"Prepared signed catalog v{args.version:04d}")
    print(f"manifestSHA256={digest}")
    print(f"publicKey={PUBLIC_KEY}")
    print(f"privateKey={private_key}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
