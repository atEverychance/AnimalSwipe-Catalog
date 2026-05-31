#!/usr/bin/env python3
"""Build AnimalSwipe remote catalog artifacts from source-of-truth repo files.

Unlike migrate_existing.py, this is the ongoing CI/local build step. It reads
animals/*.json, packs/*.json, rewards, encyclopedia, and existing dist asset
metadata, then writes versioned dist/catalog and dist/assets-manifest files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
Json = dict[str, Any]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_animals(root: Path) -> list[Json]:
    return [read_json(path) for path in sorted((root / "animals").glob("*.json"))]


def load_packs(root: Path) -> list[Json]:
    return sorted(
        [read_json(path) for path in (root / "packs").glob("*.json")],
        key=lambda pack: (pack.get("sortOrder", 9999), pack.get("id", "")),
    )


def previous_asset_index(root: Path) -> dict[tuple[str, str], Json]:
    out: dict[tuple[str, str], Json] = {}
    for path in sorted((root / "dist").glob("assets-manifest-v*.json")):
        try:
            manifest = read_json(path)
        except json.JSONDecodeError:
            continue
        for asset in manifest.get("assets", []):
            key = (asset.get("animalID"), asset.get("fileName"))
            if key[0] and key[1]:
                out[key] = asset
    return out


def resolve_asset_source(root: Path, app_repo: Path | None, rel: str | None, filename: str | None) -> Path | None:
    candidates: list[Path] = []
    if rel:
        rel_path = Path(rel)
        candidates.append(rel_path if rel_path.is_absolute() else root / rel_path)
        if app_repo:
            candidates.append(app_repo / rel_path)
    if app_repo and filename:
        candidates.extend([
            app_repo / "Content/images" / filename,
            app_repo / "AnimalSwipe/Resources/AnimalPhotos" / filename,
            app_repo / "AnimalSwipe/Resources/PackPhotos" / filename,
            app_repo / "AnimalSwipe/Resources/StarterPhotos" / filename,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_assets(root: Path, animals: list[Json], app_repo: Path | None, strict_assets: bool) -> list[Json]:
    previous = previous_asset_index(root)
    assets: list[Json] = []
    missing: list[str] = []
    for animal in animals:
        image = animal.get("image", {})
        file_name = image.get("primaryFileName")
        rel = image.get("sourceRelativePath")
        source = resolve_asset_source(root, app_repo, rel, file_name)
        prior = previous.get((animal.get("id"), file_name), {})
        content_type = prior.get("contentType") or mimetypes.guess_type(file_name or "")[0] or "image/jpeg"
        item = {
            "animalID": animal.get("id"),
            "fileName": file_name,
            "sourceRelativePath": rel,
            "sha256": prior.get("sha256"),
            "byteSize": prior.get("byteSize"),
            "contentType": content_type,
            "remotePath": prior.get("remotePath") or f"assets/{file_name}",
        }
        if source:
            item.update({
                "sourceRelativePath": str(source.relative_to(root)) if source.is_relative_to(root) else rel,
                "sha256": sha256(source),
                "byteSize": source.stat().st_size,
                "contentType": mimetypes.guess_type(source.name)[0] or content_type,
                "remotePath": f"assets/{file_name}",
            })
        elif not item["sha256"] or not item["byteSize"]:
            missing.append(f"{animal.get('id')}: {file_name}")
        assets.append(item)
    if missing and strict_assets:
        raise SystemExit("missing asset bytes/metadata:\n" + "\n".join(missing[:50]))
    return assets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--source-app-repo", help="optional app repo for migrated bundled assets")
    parser.add_argument("--strict-assets", action="store_true", help="fail if an asset is missing local bytes and previous dist metadata")
    args = parser.parse_args()

    root = ROOT
    app_repo = Path(args.source_app_repo).resolve() if args.source_app_repo else None
    animals = load_animals(root)
    packs = load_packs(root)
    rewards = read_json(root / "rewards" / "rewards.json")
    encyclopedia_path = root / "encyclopedia" / "encyclopedia.json"
    encyclopedia = read_json(encyclopedia_path) if encyclopedia_path.exists() else None
    assets = build_assets(root, animals, app_repo, args.strict_assets)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    catalog = {
        "schemaVersion": 1,
        "catalogVersion": args.version,
        "generatedAt": generated_at,
        "animals": animals,
        "packs": packs,
        "rewards": rewards,
        "encyclopedia": encyclopedia,
        "assets": assets,
        "remoteKillSwitch": {"hiddenPackIDs": []},
    }
    write_json(root / "dist" / f"assets-manifest-v{args.version:04d}.json", {"schemaVersion": 1, "catalogVersion": args.version, "assets": assets})
    write_json(root / "dist" / f"catalog-v{args.version:04d}.json", catalog)
    print(f"Built catalog v{args.version:04d}: {len(animals)} animals, {len(packs)} packs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
