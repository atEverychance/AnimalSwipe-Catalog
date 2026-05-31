#!/usr/bin/env python3
"""Migrate AnimalSwipe's bundled content into the catalog repo shape.

Phase 0 only: no new animals are discovered or added.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TAXONOMY_BY_ID = {
    # amphibians
    'frog':'amphibian','tree-frog':'amphibian','toad':'amphibian','salamander':'amphibian','axolotl':'amphibian',
    # reptiles
    'iguana':'reptile','chameleon':'reptile','komodo-dragon':'reptile','gecko':'reptile','sea-turtle':'reptile','tortoise':'reptile','crocodile':'reptile','alligator':'reptile','king-cobra':'reptile','python-genus':'reptile','rattlesnake':'reptile',
    # fish / marine non-mammals
    'great-white-shark':'fish','hammerhead-shark':'fish','manta-ray':'fish','clownfish':'fish','seahorse':'fish','eel':'fish',
    # invertebrates
    'octopus':'invertebrate','squid':'invertebrate','jellyfish':'invertebrate','starfish':'invertebrate','crab':'invertebrate','lobster':'invertebrate','shrimp':'invertebrate','butterfly':'invertebrate','monarch-butterfly':'invertebrate','moth':'invertebrate','dragonfly':'invertebrate','ladybug':'invertebrate','bee':'invertebrate','bumblebee':'invertebrate','ant':'invertebrate','grasshopper':'invertebrate','cricket':'invertebrate','beetle':'invertebrate','firefly':'invertebrate','praying-mantis':'invertebrate','stick-insect':'invertebrate','caterpillar':'invertebrate','snail':'invertebrate','spider':'invertebrate','tarantula':'invertebrate','scorpion':'invertebrate',
}
BIRDS = {'penguin','emperor-penguin','king-penguin','puffin','eagle','bald-eagle','golden-eagle','hawk','falcon','kestrel','vulture','condor','swan','goose','duck','mallard','pelican','heron','stork','kingfisher','woodpecker','hummingbird','blue-jay','northern-cardinal','crow','raven','magpie','turkey-bird','chicken','rooster','pheasant','quail','finch','parakeet','cassowary','kiwi-bird','ostrich','emu','parrot','toucan','macaw','flamingo','peacock','owl'}
MARINE_MAMMALS = {'dolphin','orca','blue-whale','humpback-whale','beluga-whale','manatee','walrus','sea-lion','dugong','narwhal'}

HABITAT_BY_PACK = {
    'starter':['forest','grassland'],
    'frost-and-fluff':['polar','forest'],
    'hoofed-horizons':['grassland','desert'],
    'meadow-mischief':['grassland'],
    'tiny-trailblazers':['forest','grassland'],
    'splash-superstars':['ocean'],
    'feathered-fashionistas':['polar','wetland','ocean'],
    'sky-sentinels':['mountain','forest'],
    'wetland-wings':['wetland'],
    'backyard-band':['backyard','farm'],
    'scale-squad':['wetland','forest'],
    'fin-frenzy':['wetland','forest','desert'],
    'reef-rainbow':['ocean'],
    'bug-beat':['backyard','grassland'],
    'micro-monsters':['forest','backyard'],
    'farm-friends':['farm'],
    'wild-walkers':['forest','grassland'],
    'twilight-trackers':['forest','nocturnal'],
    'mountain-mob':['mountain','grassland'],
    'mystery-mammals':['forest','ocean'],
}

REGION_HINTS = {
    'arctic':['Arctic'], 'polar':['Arctic/Antarctic'], 'kangaroo':['Oceania'], 'koala':['Oceania'], 'wallaby':['Oceania'], 'wombat':['Oceania'], 'tasmanian-devil':['Oceania'], 'kiwi-bird':['Oceania'], 'cassowary':['Oceania'], 'emu':['Oceania'],
    'red-panda':['Asia'], 'giant-panda':['Asia'], 'tiger':['Asia'], 'orangutan':['Asia'], 'gibbon':['Asia'], 'proboscis-monkey':['Asia'], 'sun-bear':['Asia'], 'raccoon-dog':['Asia'], 'yak':['Asia'], 'saiga-antelope':['Asia'], 'snow-leopard':['Asia'],
    'lion':['Africa'], 'elephant':['Africa'], 'giraffe':['Africa'], 'zebra':['Africa'], 'gorilla':['Africa'], 'chimpanzee':['Africa'], 'bonobo':['Africa'], 'lemur':['Africa'], 'mandrill':['Africa'], 'baboon':['Africa'], 'meerkat':['Africa'], 'okapi':['Africa'], 'hippopotamus':['Africa'], 'rhinoceros':['Africa'], 'wildebeest':['Africa'], 'gazelle':['Africa'], 'hyena':['Africa'], 'serval':['Africa'], 'caracal':['Africa'], 'fennec-fox':['Africa'],
    'bald-eagle':['Americas'], 'cougar':['Americas'], 'bobcat':['Americas'], 'ocelot':['Americas'], 'prairie-dog':['Americas'], 'marmot':['Americas'], 'raccoon':['Americas'], 'chipmunk':['Americas'], 'northern-cardinal':['Americas'], 'blue-jay':['Americas'], 'spectacled-bear':['Americas'],
}

TRAIT_WORDS = {
    'stripe':['stripes'], 'zebra':['stripes'], 'tiger':['stripes'], 'leopard':['spots'], 'cheetah':['spots'], 'jaguar':['spots'], 'giraffe':['spots'], 'panda':['cute'], 'fox':['fluffy'], 'bear':['large'], 'whale':['giant'], 'elephant':['giant'], 'hippopotamus':['giant'], 'rhinoceros':['horns'], 'ibex':['horns'], 'goat':['horns'], 'antelope':['horns'], 'eagle':['wings'], 'hawk':['wings'], 'falcon':['wings'], 'owl':['nocturnal'], 'bat':['nocturnal'], 'scorpion':['armored'], 'turtle':['shell'], 'tortoise':['shell'], 'crab':['claws'], 'lobster':['claws'], 'chameleon':['camouflage'], 'stick-insect':['camouflage'], 'octopus':['weird'], 'axolotl':['weird'], 'narwhal':['horns']
}

HOOK_BY_TRAIT = {
    'cute':'cute','fluffy':'cute','giant':'giant','large':'giant','tiny':'tiny','camouflage':'camouflage','nocturnal':'nocturnal','armored':'armored','shell':'armored','spots':'colorful','stripes':'colorful','weird':'weird'
}

def read_json(path: Path) -> Any:
    return json.loads(path.read_text())

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + '\n')

def norm(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-')

def taxonomy(animal_id: str) -> str:
    if animal_id in BIRDS: return 'bird'
    if animal_id in TAXONOMY_BY_ID: return TAXONOMY_BY_ID[animal_id]
    return 'mammal'

def animal_pack_map(packs: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for pack in packs:
        for aid in pack.get('animalIDs', []):
            out[aid].append(pack['id'])
    return dict(out)

def infer_habitats(animal_id: str, pack_ids: list[str], tax: str) -> list[str]:
    habitats: list[str] = []
    for pid in pack_ids:
        habitats.extend(HABITAT_BY_PACK.get(pid, []))
    if animal_id in MARINE_MAMMALS or tax == 'fish': habitats.append('ocean')
    if tax == 'amphibian': habitats.extend(['wetland','forest'])
    if tax == 'invertebrate' and not habitats: habitats.extend(['backyard','forest'])
    if not habitats: habitats.append('forest')
    # stable unique order
    seen=set(); return [h for h in habitats if not (h in seen or seen.add(h))]

def infer_regions(animal_id: str) -> list[str]:
    if animal_id in REGION_HINTS: return REGION_HINTS[animal_id]
    for part, regions in REGION_HINTS.items():
        if part in animal_id: return regions
    return ['global']

def infer_traits(animal_id: str, tax: str, habitats: list[str]) -> list[str]:
    traits=[]
    for key, vals in TRAIT_WORDS.items():
        if key in animal_id:
            traits.extend(vals)
    if tax == 'bird': traits.append('wings')
    if tax in {'reptile','fish'}: traits.append('scales')
    if tax == 'invertebrate': traits.append('tiny')
    if 'nocturnal' in habitats: traits.append('nocturnal')
    if not traits: traits.append(tax)
    seen=set(); return [t for t in traits if not (t in seen or seen.add(t))]

def infer_hooks(traits: list[str], animal_id: str) -> list[str]:
    hooks=[HOOK_BY_TRAIT[t] for t in traits if t in HOOK_BY_TRAIT]
    if 'cheetah' in animal_id or 'falcon' in animal_id: hooks.append('speedy')
    if not hooks: hooks.append('cute' if any(w in animal_id for w in ['panda','fox','rabbit','koala']) else 'weird')
    seen=set(); return [h for h in hooks if not (h in seen or seen.add(h))]

def find_image(app_repo: Path, filename: str) -> str | None:
    for rel in [f'Content/images/{filename}', f'AnimalSwipe/Resources/AnimalPhotos/{filename}', f'AnimalSwipe/Resources/PackPhotos/{filename}', f'AnimalSwipe/Resources/StarterPhotos/{filename}']:
        if (app_repo/rel).exists(): return rel
    return None

def migrate_animal(src: dict[str, Any], pack_ids: list[str], app_repo: Path, grandfathered: set[str]) -> dict[str, Any]:
    aid=src['id']; tax=taxonomy(aid); habitats=infer_habitats(aid, pack_ids, tax); traits=infer_traits(aid,tax,habitats)
    image: dict[str, Any] = {'primaryFileName': src.get('imageFileName'), 'sourceRelativePath': find_image(app_repo, src.get('imageFileName',''))}
    if 'focalPointX' in src and 'focalPointY' in src:
        image['focalPoint'] = {'x': src['focalPointX'], 'y': src['focalPointY']}
    else:
        image['focalPoint'] = None
        image['focalPointGrandfathered'] = aid in grandfathered
    return {
        'schemaVersion': 1,
        'id': aid,
        'name': src.get('name'),
        'species': {'displayName': src.get('species'), 'scientificName': None},
        'copy': {'caption': src.get('caption'), 'shortDescription': src.get('shortDescription')},
        'image': image,
        'provenance': {
            'origin': src.get('provenance'),
            'fact': {'sourceName': src.get('factSourceName'), 'sourceURL': src.get('factSourceURL'), 'sourcePageURL': src.get('sourcePageURL')},
            'photo': {'attributionName': src.get('attributionName'), 'licenseName': src.get('licenseName'), 'licenseURL': src.get('licenseURL'), 'commonsFile': src.get('photoCommonsFile'), 'commonsPageURL': src.get('photoCommonsPageURL')}
        },
        'tags': {'taxonomy': tax, 'habitats': habitats, 'regions': infer_regions(aid), 'traits': traits, 'hookArchetypes': infer_hooks(traits, aid)},
        'externalIDs': {},
        'review': {'status': 'approvedMigrated', 'tagsStatus': 'needsTagReview', 'reviewedBy': 'migration-equivalence', 'reviewedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')},
        'migration': {'sourceAnimalRecordID': aid, 'sourcePackIDs': pack_ids}
    }

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

def build_indexes(animals: list[dict[str, Any]], packs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    dup={'schemaVersion':1,'byID':{},'byName':defaultdict(list),'bySpecies':defaultdict(list),'bySourceURL':defaultdict(list),'byCommonsFile':defaultdict(list)}
    for a in animals:
        dup['byID'][a['id']] = a['id']
        dup['byName'][norm(a.get('name'))].append(a['id'])
        dup['bySpecies'][norm(a.get('species',{}).get('displayName'))].append(a['id'])
        dup['bySourceURL'][a.get('provenance',{}).get('fact',{}).get('sourcePageURL')].append(a['id'])
        cf=a.get('provenance',{}).get('photo',{}).get('commonsFile')
        if cf: dup['byCommonsFile'][cf].append(a['id'])
    dup={k:(dict(v) if hasattr(v,'items') and k!='byID' else v) for k,v in dup.items()}
    tax=Counter(a['tags']['taxonomy'] for a in animals)
    hab=Counter(h for a in animals for h in a['tags']['habitats'])
    hooks=Counter(h for a in animals for h in a['tags'].get('hookArchetypes',[]))
    pack_summaries=[]
    byid={a['id']:a for a in animals}
    for p in packs:
        members=[byid[i] for i in p.get('animalIDs',[]) if i in byid]
        pack_summaries.append({'id':p['id'],'name':p.get('name'),'animalCount':len(members),'taxonomy':dict(Counter(a['tags']['taxonomy'] for a in members)),'habitats':dict(Counter(h for a in members for h in a['tags']['habitats']))})
    balance={'schemaVersion':1,'animalCount':len(animals),'packCount':len(packs),'taxonomyCounts':dict(tax),'habitatCounts':dict(hab),'hookCounts':dict(hooks),'packSummaries':pack_summaries}
    return dup, balance

def compare_source(src: list[dict[str, Any]], migrated: list[dict[str, Any]], src_packs: list[dict[str, Any]], migrated_packs: list[dict[str, Any]]) -> dict[str, Any]:
    failures=[]; warnings=[]
    by_src={a['id']:a for a in src}; by_m={a['id']:a for a in migrated}
    if len(src)!=len(migrated): failures.append(f'animal count mismatch source={len(src)} migrated={len(migrated)}')
    missing=sorted(set(by_src)-set(by_m)); extra=sorted(set(by_m)-set(by_src))
    if missing: failures.append(f'missing migrated animals: {missing}')
    if extra: failures.append(f'extra migrated animals: {extra}')
    for aid, s in by_src.items():
        if aid not in by_m: continue
        rt=source_shape(by_m[aid])
        for key in ['id','name','species','caption','imageFileName','attributionName','sourcePageURL','licenseName','licenseURL','provenance','shortDescription','factSourceName','factSourceURL','photoCommonsFile','photoCommonsPageURL','focalPointX','focalPointY']:
            if s.get(key) != rt.get(key): failures.append(f'{aid}: field {key} mismatch source={s.get(key)!r} migrated={rt.get(key)!r}')
        if by_m[aid]['image'].get('sourceRelativePath') is None:
            warnings.append(f'{aid}: image file not found locally: {s.get("imageFileName")}')
    sp={p['id']:p for p in src_packs}; mp={p['id']:p for p in migrated_packs}
    if len(sp)!=len(mp): failures.append(f'pack count mismatch source={len(sp)} migrated={len(mp)}')
    for pid,p in sp.items():
        if pid not in mp: failures.append(f'missing migrated pack: {pid}'); continue
        if p.get('animalIDs') != mp[pid].get('animalIDs'): failures.append(f'{pid}: animalIDs order mismatch')
    return {'passed': not failures, 'failureCount': len(failures), 'warningCount': len(warnings), 'failures': failures, 'warnings': warnings}

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-app-repo', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--version', type=int, default=1)
    args=ap.parse_args()
    app=Path(args.source_app_repo).resolve(); out=Path(args.output).resolve()
    for d in ['animals','packs','rewards','encyclopedia','indexes','dist']:
        (out/d).mkdir(parents=True, exist_ok=True)
    src_animals=read_json(app/'Content/animals/animals.json')
    pack_paths=sorted((app/'Content/packs').glob('*.json'))
    src_packs=sorted([read_json(p) for p in pack_paths], key=lambda p:(p.get('sortOrder',9999), p.get('id','')))
    rewards=read_json(app/'Content/rewards/rewards.json')
    encyclopedia_path=app/'Content/encyclopedia/encyclopedia.json'
    encyclopedia=read_json(encyclopedia_path) if encyclopedia_path.exists() else None
    grandfathered=set(read_json(app/'Content/animals/focal-point-grandfathered-animals.json').get('animalIds',[]))
    packmap=animal_pack_map(src_packs)
    migrated=[]
    for s in sorted(src_animals, key=lambda a:a['id']):
        m=migrate_animal(s, packmap.get(s['id'], []), app, grandfathered)
        write_json(out/'animals'/f"{m['id']}.json", m)
        migrated.append(m)
    migrated_packs=[]
    for p in src_packs:
        write_json(out/'packs'/f"{p['id']}.json", p)
        migrated_packs.append(p)
    write_json(out/'rewards/rewards.json', rewards)
    if encyclopedia is not None:
        write_json(out/'encyclopedia/encyclopedia.json', encyclopedia)
    dup,balance=build_indexes(migrated, migrated_packs)
    write_json(out/'indexes/duplicate-index.json', dup)
    write_json(out/'indexes/balance-baseline.json', balance)
    assets=[]
    for a in migrated:
        assets.append({'animalID':a['id'],'fileName':a['image']['primaryFileName'],'sourceRelativePath':a['image'].get('sourceRelativePath'),'sha256':None,'byteSize':None,'contentType':'image/jpeg'})
    write_json(out/'dist/assets-manifest-v0001.json', {'schemaVersion':1,'catalogVersion':args.version,'assets':assets})
    catalog={'schemaVersion':1,'catalogVersion':args.version,'generatedAt':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'animals':migrated,'packs':migrated_packs,'rewards':rewards,'encyclopedia':encyclopedia,'assets':assets,'remoteKillSwitch':{'hiddenPackIDs':[]}}
    write_json(out/f'dist/catalog-v{args.version:04d}.json', catalog)
    write_json(out/'dist/latest.json', {'schemaVersion':1,'catalogVersion':args.version,'publishedAt':catalog['generatedAt'],'minAppVersion':'0.2.0','manifestURL':f'catalog/catalog-v{args.version:04d}.json','manifestSHA256':None,'signatureAlgorithm':'P256.ECDSA.SHA256','signature':None,'stagingOnly':True})
    eq=compare_source(src_animals, migrated, src_packs, migrated_packs)
    report={'schemaVersion':1,'sourceAppRepo':str(app),'catalogRepo':str(out),'catalogVersion':args.version,'animalCount':len(migrated),'packCount':len(migrated_packs),'newAnimalsAdded':0,'equivalence':eq,'generatedFiles':['animals/*.json','packs/*.json','rewards/rewards.json','encyclopedia/encyclopedia.json','indexes/duplicate-index.json','indexes/balance-baseline.json','dist/catalog-v0001.json','dist/latest.json']}
    write_json(out/'indexes/migration-report.json', report)
    print(f"Migrated {len(migrated)} animals and {len(migrated_packs)} packs into {out}")
    print('Equivalence:', 'PASS' if eq['passed'] else 'FAIL', f"failures={eq['failureCount']} warnings={eq['warningCount']}")
    return 0 if eq['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
