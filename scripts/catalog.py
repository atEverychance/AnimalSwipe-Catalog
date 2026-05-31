#!/usr/bin/env python3
"""Catalog repo CLI for migration validation and local automation reports."""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter
from pathlib import Path
from typing import Any

def read_json(p: Path) -> Any: return json.loads(p.read_text())
def load_animals(root: Path) -> list[dict[str,Any]]: return [read_json(p) for p in sorted((root/'animals').glob('*.json'))]
def load_packs(root: Path) -> list[dict[str,Any]]: return sorted([read_json(p) for p in (root/'packs').glob('*.json')], key=lambda p:(p.get('sortOrder',9999), p.get('id','')))
def sha256_hex(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s: str|None) -> str: return re.sub(r'[^a-z0-9]+','-',(s or '').lower()).strip('-')

def source_shape(m: dict[str, Any]) -> dict[str, Any]:
    out={
        'id': m['id'], 'name': m['name'], 'species': m['species']['displayName'], 'caption': m['copy']['caption'], 'imageFileName': m['image']['primaryFileName'],
        'attributionName': m['provenance']['photo']['attributionName'], 'sourcePageURL': m['provenance']['fact']['sourcePageURL'], 'licenseName': m['provenance']['photo']['licenseName'], 'licenseURL': m['provenance']['photo']['licenseURL'], 'provenance': m['provenance']['origin'],
        'shortDescription': m['copy']['shortDescription'], 'factSourceName': m['provenance']['fact']['sourceName'], 'factSourceURL': m['provenance']['fact']['sourceURL'], 'photoCommonsFile': m['provenance']['photo']['commonsFile'], 'photoCommonsPageURL': m['provenance']['photo']['commonsPageURL']
    }
    fp=m['image'].get('focalPoint')
    if fp:
        out['focalPointX']=fp['x']; out['focalPointY']=fp['y']
    return out

def live_equivalence(root: Path, source_app_repo: Path) -> tuple[list[str], list[str]]:
    errors=[]; warnings=[]
    src_animals=read_json(source_app_repo/'Content/animals/animals.json')
    src_packs=sorted([read_json(p) for p in (source_app_repo/'Content/packs').glob('*.json')], key=lambda p:(p.get('sortOrder',9999), p.get('id','')))
    src_rewards=read_json(source_app_repo/'Content/rewards/rewards.json')
    animals=load_animals(root); packs=load_packs(root)
    by_src={a['id']:a for a in src_animals}; by_m={a['id']:a for a in animals}
    if len(src_animals)!=len(animals): errors.append(f'animal count mismatch source={len(src_animals)} migrated={len(animals)}')
    missing=sorted(set(by_src)-set(by_m)); extra=sorted(set(by_m)-set(by_src))
    if missing: errors.append(f'missing migrated animals: {missing}')
    if extra: errors.append(f'extra migrated animals: {extra}')
    fields=['id','name','species','caption','imageFileName','attributionName','sourcePageURL','licenseName','licenseURL','provenance','shortDescription','factSourceName','factSourceURL','photoCommonsFile','photoCommonsPageURL','focalPointX','focalPointY']
    for aid,s in by_src.items():
        if aid not in by_m: continue
        rt=source_shape(by_m[aid])
        for key in fields:
            if s.get(key) != rt.get(key): errors.append(f'{aid}: field {key} mismatch source={s.get(key)!r} migrated={rt.get(key)!r}')
    sp={p['id']:p for p in src_packs}; mp={p['id']:p for p in packs}
    if len(sp)!=len(mp): errors.append(f'pack count mismatch source={len(sp)} migrated={len(mp)}')
    for pid,p in sp.items():
        if pid not in mp: errors.append(f'missing migrated pack: {pid}'); continue
        if p != mp[pid]: errors.append(f'{pid}: pack record mismatch')
    rewards_path=root/'rewards/rewards.json'
    if not rewards_path.exists(): errors.append('missing migrated rewards/rewards.json')
    elif read_json(rewards_path) != src_rewards: errors.append('reward config mismatch')
    src_enc=source_app_repo/'Content/encyclopedia/encyclopedia.json'
    migrated_enc=root/'encyclopedia/encyclopedia.json'
    if src_enc.exists():
        if not migrated_enc.exists(): warnings.append('source encyclopedia exists but migrated encyclopedia/encyclopedia.json is missing')
        elif read_json(migrated_enc) != read_json(src_enc): errors.append('encyclopedia sidecar mismatch')
    return errors,warnings

def validate_publish(root: Path, allow_staging: bool) -> tuple[list[str], list[str]]:
    errors=[]; warnings=[]
    latest_path=root/'dist/latest.json'
    if not latest_path.exists(): return ['missing dist/latest.json'], warnings
    latest=read_json(latest_path)
    required=['schemaVersion','catalogVersion','publishedAt','minAppVersion','manifestURL','manifestSHA256','signatureAlgorithm','signature']
    for k in required:
        if k not in latest: errors.append(f'dist/latest.json missing {k}')
    version=latest.get('catalogVersion')
    catalog_path=root/'dist'/f'catalog-v{int(version):04d}.json' if isinstance(version,int) else None
    if not catalog_path or not catalog_path.exists(): errors.append(f'missing versioned catalog for version {version!r}')
    staging=latest.get('stagingOnly') is True
    if staging and allow_staging:
        warnings.append('publish validation allowed unsigned staging latest.json')
    else:
        if latest.get('signatureAlgorithm') != 'P256.ECDSA.SHA256': errors.append('latest.json signatureAlgorithm must be P256.ECDSA.SHA256')
        if not latest.get('manifestSHA256'): errors.append('latest.json missing manifestSHA256')
        if not latest.get('signature'): errors.append('latest.json missing signature')
        if catalog_path and catalog_path.exists() and latest.get('manifestSHA256') and latest['manifestSHA256'] != sha256_hex(catalog_path): errors.append('latest.json manifestSHA256 does not match catalog bytes')
    assets_manifest=root/'dist'/f'assets-manifest-v{int(version):04d}.json' if isinstance(version,int) else None
    if assets_manifest and assets_manifest.exists():
        manifest=read_json(assets_manifest)
        for asset in manifest.get('assets',[]):
            if 'animalID' not in asset or 'fileName' not in asset: errors.append('asset entry missing animalID/fileName')
            if not allow_staging:
                for k in ['sha256','byteSize','contentType']:
                    if not asset.get(k): errors.append(f'asset {asset.get("animalID")}: missing {k}')
    else:
        warnings.append('assets manifest not found for this catalog version')
    return errors,warnings

def validate_common(root: Path, mode: str, source_app_repo: str|None=None, allow_staging: bool=False) -> tuple[list[str], list[str]]:
    errors=[]; warnings=[]; animals=load_animals(root); packs=load_packs(root)
    ids=[a.get('id') for a in animals]
    if len(ids) != len(set(ids)): errors.append('duplicate animal IDs in animals/*.json')
    byid={a['id']:a for a in animals if 'id' in a}
    for a in animals:
        aid=a.get('id','<missing>')
        for path in [('name',),('species','displayName'),('copy','caption'),('image','primaryFileName'),('provenance','origin'),('provenance','photo','attributionName'),('provenance','photo','licenseName'),('provenance','fact','sourcePageURL'),('review','status')]:
            cur=a
            for part in path:
                cur = cur.get(part) if isinstance(cur,dict) else None
            if cur in (None,''): errors.append(f'{aid}: missing required field {".".join(path)}')
        if not a.get('tags',{}).get('taxonomy'): warnings.append(f'{aid}: missing taxonomy tag')
        if a.get('review',{}).get('tagsStatus') != 'needsTagReview': warnings.append(f'{aid}: tagsStatus should remain needsTagReview until human tag review')
        fp=a.get('image',{}).get('focalPoint')
        if fp is None and not a.get('image',{}).get('focalPointGrandfathered'):
            warnings.append(f'{aid}: missing focalPoint and not grandfathered')
    pack_ids=[p.get('id') for p in packs]
    if len(pack_ids) != len(set(pack_ids)): errors.append('duplicate pack IDs')
    for p in packs:
        pid=p.get('id','<missing>'); animal_ids=p.get('animalIDs',[])
        if len(animal_ids)!=len(set(animal_ids)): errors.append(f'{pid}: duplicate animalIDs')
        for aid in animal_ids:
            if aid not in byid: errors.append(f'{pid}: missing animal {aid}')
        if p.get('coverAnimalID') not in animal_ids: errors.append(f'{pid}: coverAnimalID not in animalIDs')
    if mode == 'baseline':
        if len(animals) != 200: errors.append(f'baseline requires 200 animals, found {len(animals)}')
        if len(packs) != 20: errors.append(f'baseline requires 20 packs, found {len(packs)}')
        for p in packs:
            if len(p.get('animalIDs',[])) != 10: errors.append(f"baseline pack {p.get('id')} must have 10 animals")
        report_path=root/'indexes/migration-report.json'
        if not report_path.exists(): errors.append('missing indexes/migration-report.json')
        else:
            report=read_json(report_path); eq=report.get('equivalence',{})
            if not eq.get('passed'): errors.append(f'migration equivalence failed: {eq.get("failureCount")} failures')
            if report.get('newAnimalsAdded') != 0: errors.append('baseline must not add new animals')
        if source_app_repo:
            live_errors, live_warnings = live_equivalence(root, Path(source_app_repo).resolve())
            errors.extend(live_errors); warnings.extend(live_warnings)
    elif mode == 'publish':
        pub_errors, pub_warnings = validate_publish(root, allow_staging)
        errors.extend(pub_errors); warnings.extend(pub_warnings)
    elif mode == 'expansion':
        if len(animals) < 200: errors.append('expansion catalog cannot have fewer than 200 animals')
    return errors,warnings

def cmd_validate(args: argparse.Namespace) -> int:
    root=Path(args.root).resolve(); errors,warnings=validate_common(root,args.mode,args.source_app_repo,args.allow_staging)
    for w in warnings: print('WARN:',w)
    if errors:
        for e in errors: print('ERROR:',e)
        print(f'❌ Catalog validation failed ({args.mode}): {len(errors)} errors, {len(warnings)} warnings')
        return 1
    print(f'✅ Catalog validation passed ({args.mode}): {len(warnings)} warnings')
    return 0

def cmd_summarize(args: argparse.Namespace) -> int:
    root=Path(args.root).resolve(); animals=load_animals(root); packs=load_packs(root)
    tax=Counter(a.get('tags',{}).get('taxonomy','unknown') for a in animals)
    print(f'Animals: {len(animals)}'); print(f'Packs: {len(packs)}'); print('Taxonomy:', dict(sorted(tax.items())))
    return 0

def cmd_gaps(args: argparse.Namespace) -> int:
    root=Path(args.root).resolve(); animals=load_animals(root)
    policy_path=root/'policy/balance-policy.json'
    if not policy_path.exists(): print('missing policy/balance-policy.json'); return 1
    policy=read_json(policy_path); total=max(1,len(animals))
    tax=Counter(a.get('tags',{}).get('taxonomy','unknown') for a in animals)
    print('Taxonomy gaps vs target:')
    for key,target in policy.get('globalTargets',{}).get('taxonomy',{}).items():
        actual=tax.get(key,0)/total
        print(f'- {key}: actual={actual:.3f} target={target:.3f} gap={target-actual:+.3f}')
    return 0

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--root', default='.')
    sub=p.add_subparsers(dest='cmd', required=True)
    v=sub.add_parser('validate'); v.add_argument('--mode', choices=['baseline','expansion','publish'], default='baseline'); v.add_argument('--source-app-repo'); v.add_argument('--allow-staging', action='store_true', help='permit unsigned staging latest.json during Phase 0/2 dry runs'); v.set_defaults(func=cmd_validate)
    s=sub.add_parser('summarize'); s.set_defaults(func=cmd_summarize)
    g=sub.add_parser('gaps'); g.set_defaults(func=cmd_gaps)
    args=p.parse_args(); return args.func(args)
if __name__=='__main__': raise SystemExit(main())
