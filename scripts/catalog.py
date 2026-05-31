#!/usr/bin/env python3
"""AnimalSwipe catalog CLI.

Repo-first, local-first tools for migrated catalog validation and Phase 1
candidate automation. Discovery is intentionally deterministic and does not add
animals to the source tree; it produces review queues and drafts only.
"""
from __future__ import annotations

import argparse
import html
import hashlib
import json
import mimetypes
import re
import ssl
import textwrap
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

Json = dict[str, Any]
USER_AGENT = "AnimalSwipe-Catalog/1.0 (https://github.com/animalswipe/catalog; local curation CLI)"
HTTP_TIMEOUT = 16
MEDIA_REJECT_TITLE_TERMS = [
    "skull",
    "skeleton",
    "taxiderm",
    "museum",
    "specimen",
    "bone",
    "bones",
    "fur skin",
    "fur skins",
    "pelt",
    "dead",
    "roadkill",
    "dissection",
]

THEME_HINTS: dict[str, list[str]] = {
    "forest": ["forest", "rainforest", "woodland", "canopy", "jungle"],
    "ocean": ["ocean", "reef", "coastal", "marine"],
    "wetland": ["wetland", "river", "pond", "marsh"],
    "grassland": ["grassland", "savanna", "prairie", "meadow"],
    "desert": ["desert", "scrub"],
    "mountain": ["mountain", "alpine", "highland"],
    "polar": ["polar", "arctic", "antarctic"],
    "backyard": ["backyard", "garden", "urban"],
    "farm": ["farm"],
    "night": ["nocturnal", "forest", "cave"],
}

# Local structured seed queue. These are candidates for review, not approved
# catalog entries. Keep this lightweight until a true external species-source
# importer is added.
CANDIDATE_SEEDS: list[Json] = [
    {"id":"pine-marten","name":"Pine Marten","scientificName":"Martes martes","taxonomy":"mammal","habitats":["forest"],"regions":["Europe","Asia"],"traits":["climber","fluffy","tail"],"hooks":["cute","speedy"],"kid":"medium","visual":0.82,"source":0.86,"image":0.86,"risk":0.02,"license":0.08,"facts":["climbs trees with sharp claws","has a long bushy tail","hunts mostly at dusk and night"]},
    {"id":"european-badger","name":"European Badger","scientificName":"Meles meles","taxonomy":"mammal","habitats":["forest","grassland"],"regions":["Europe"],"traits":["stripes","burrower"],"hooks":["nocturnal","colorful"],"kid":"common","visual":0.88,"source":0.86,"image":0.84,"risk":0.04,"license":0.08,"facts":["lives in burrow systems called setts","has a bold black-and-white face","often comes out at night"]},
    {"id":"clouded-leopard","name":"Clouded Leopard","scientificName":"Neofelis nebulosa","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["spots","climber","tail"],"hooks":["camouflage","colorful"],"kid":"medium","visual":0.94,"source":0.86,"image":0.78,"risk":0.08,"license":0.14,"facts":["has cloud-shaped markings","is an excellent tree climber","uses a long tail for balance"]},
    {"id":"binturong","name":"Binturong","scientificName":"Arctictis binturong","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["tail","climber","black"],"hooks":["weird","cute"],"kid":"surprise","visual":0.9,"source":0.84,"image":0.76,"risk":0.03,"license":0.14,"facts":["uses a prehensile tail while climbing","is also called a bearcat","spends much time in trees"]},
    {"id":"slow-loris","name":"Slow Loris","scientificName":"Nycticebus coucang","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["big-eyes","nocturnal","tiny"],"hooks":["cute","nocturnal"],"kid":"medium","visual":0.91,"source":0.82,"image":0.74,"risk":0.06,"license":0.16,"facts":["has large night-seeing eyes","moves carefully through branches","is active mostly after dark"]},
    {"id":"philippine-tarsier","name":"Philippine Tarsier","scientificName":"Carlito syrichta","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["big-eyes","tiny","climber"],"hooks":["tiny","nocturnal"],"kid":"surprise","visual":0.95,"source":0.82,"image":0.75,"risk":0.03,"license":0.15,"facts":["has enormous eyes for night hunting","clings to slender branches","can leap between trees"]},
    {"id":"sunda-flying-lemur","name":"Sunda Flying Lemur","scientificName":"Galeopterus variegatus","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["glider","membrane","climber"],"hooks":["weird","speedy"],"kid":"surprise","visual":0.86,"source":0.78,"image":0.68,"risk":0.02,"license":0.18,"facts":["glides between trees using a skin membrane","is not actually a true lemur","rests high in trees"]},
    {"id":"sugar-glider","name":"Sugar Glider","scientificName":"Petaurus breviceps","taxonomy":"mammal","habitats":["forest"],"regions":["Oceania"],"traits":["glider","tiny","big-eyes"],"hooks":["cute","speedy"],"kid":"medium","visual":0.9,"source":0.78,"image":0.72,"risk":0.02,"license":0.16,"facts":["glides on a membrane between its legs","has large eyes for night activity","eats nectar and tree sap"]},
    {"id":"tree-kangaroo","name":"Tree Kangaroo","scientificName":"Dendrolagus matschiei","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Oceania"],"traits":["climber","tail","marsupial"],"hooks":["cute","weird"],"kid":"medium","visual":0.9,"source":0.8,"image":0.72,"risk":0.03,"license":0.16,"facts":["climbs in rainforest trees","uses a long tail for balance","is a tree-living marsupial"]},
    {"id":"silky-anteater","name":"Silky Anteater","scientificName":"Cyclopes didactylus","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["tiny","climber","golden"],"hooks":["tiny","cute"],"kid":"surprise","visual":0.88,"source":0.78,"image":0.64,"risk":0.01,"license":0.2,"facts":["is one of the smallest anteaters","climbs through forest branches","eats ants and termites"]},
    {"id":"margay","name":"Margay","scientificName":"Leopardus wiedii","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["spots","climber","cat"],"hooks":["camouflage","colorful"],"kid":"medium","visual":0.92,"source":0.82,"image":0.7,"risk":0.06,"license":0.18,"facts":["is a spotted forest cat","can climb down trees headfirst","hunts among branches"]},
    {"id":"tayra","name":"Tayra","scientificName":"Eira barbara","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["tail","climber","speedy"],"hooks":["speedy","weird"],"kid":"surprise","visual":0.76,"source":0.8,"image":0.7,"risk":0.04,"license":0.16,"facts":["moves quickly through trees and on the ground","belongs to the weasel family","has a long body and tail"]},
    {"id":"agouti","name":"Agouti","scientificName":"Dasyprocta leporina","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["small","runner","seed-eater"],"hooks":["cute","speedy"],"kid":"medium","visual":0.74,"source":0.82,"image":0.78,"risk":0.01,"license":0.1,"facts":["carries and buries seeds","runs quickly on the forest floor","helps some trees spread seeds"]},
    {"id":"fossa","name":"Fossa","scientificName":"Cryptoprocta ferox","taxonomy":"mammal","habitats":["forest"],"regions":["Africa"],"traits":["tail","climber","predator"],"hooks":["weird","speedy"],"kid":"medium","visual":0.86,"source":0.82,"image":0.72,"risk":0.08,"license":0.16,"facts":["is Madagascar's largest native predator","climbs trees with a long balancing tail","looks a little like a cat and a mongoose"]},
    {"id":"aye-aye","name":"Aye-aye","scientificName":"Daubentonia madagascariensis","taxonomy":"mammal","habitats":["forest"],"regions":["Africa"],"traits":["big-eyes","long-finger","nocturnal"],"hooks":["weird","nocturnal"],"kid":"surprise","visual":0.94,"source":0.82,"image":0.7,"risk":0.04,"license":0.16,"facts":["taps wood with a long finger","is active at night","lives in Madagascar forests"]},
    {"id":"colugo","name":"Colugo","scientificName":"Cynocephalidae","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["glider","membrane"],"hooks":["weird","speedy"],"kid":"surprise","visual":0.82,"source":0.76,"image":0.64,"risk":0.02,"license":0.2,"facts":["glides from tree to tree","has a wide skin membrane","rests on tree trunks"]},
    {"id":"hoatzin","name":"Hoatzin","scientificName":"Opisthocomus hoazin","taxonomy":"bird","habitats":["forest","wetland"],"regions":["Americas"],"traits":["crest","wings","colorful"],"hooks":["weird","colorful"],"kid":"surprise","visual":0.95,"source":0.86,"image":0.84,"risk":0.01,"license":0.08,"facts":["has a spiky crest","young chicks have tiny wing claws","lives near forested wetlands"]},
    {"id":"great-hornbill","name":"Great Hornbill","scientificName":"Buceros bicornis","taxonomy":"bird","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["beak","wings","colorful"],"hooks":["colorful","excellent-parent"],"kid":"medium","visual":0.96,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["has a huge yellow bill and casque","nests in tree hollows","helps spread forest fruit seeds"]},
    {"id":"quetzal","name":"Resplendent Quetzal","scientificName":"Pharomachrus mocinno","taxonomy":"bird","habitats":["forest","mountain"],"regions":["Americas"],"traits":["wings","bright-color","long-tail"],"hooks":["colorful"],"kid":"medium","visual":0.98,"source":0.84,"image":0.78,"risk":0.01,"license":0.14,"facts":["has shimmering green feathers","males grow long tail plumes","lives in cloud forests"]},
    {"id":"kakapo","name":"Kākāpō","scientificName":"Strigops habroptilus","taxonomy":"bird","habitats":["forest"],"regions":["Oceania"],"traits":["green","nocturnal","flightless"],"hooks":["weird","nocturnal"],"kid":"medium","visual":0.88,"source":0.88,"image":0.82,"risk":0.01,"license":0.08,"facts":["is a flightless parrot","is active mostly at night","has mossy green feathers"]},
    {"id":"potoo","name":"Potoo","scientificName":"Nyctibiidae","taxonomy":"bird","habitats":["forest"],"regions":["Americas"],"traits":["camouflage","big-eyes","wings"],"hooks":["camouflage","nocturnal"],"kid":"surprise","visual":0.92,"source":0.82,"image":0.74,"risk":0.01,"license":0.16,"facts":["blends in like a broken branch","has huge eyes for night hunting","sits very still during the day"]},
    {"id":"harpy-eagle","name":"Harpy Eagle","scientificName":"Harpia harpyja","taxonomy":"bird","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["wings","crest","giant"],"hooks":["giant","speedy"],"kid":"medium","visual":0.96,"source":0.84,"image":0.8,"risk":0.08,"license":0.14,"facts":["is one of the largest forest eagles","has a dramatic feather crest","hunts from rainforest trees"]},
    {"id":"paradise-tanager","name":"Paradise Tanager","scientificName":"Tangara chilensis","taxonomy":"bird","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["wings","bright-color","tiny"],"hooks":["colorful","tiny"],"kid":"surprise","visual":0.98,"source":0.82,"image":0.82,"risk":0.01,"license":0.1,"facts":["has bright blue, green, and red feathers","moves through rainforest canopies","often joins mixed bird flocks"]},
    {"id":"wood-thrush","name":"Wood Thrush","scientificName":"Hylocichla mustelina","taxonomy":"bird","habitats":["forest","backyard"],"regions":["Americas"],"traits":["spots","wings","song"],"hooks":["colorful"],"kid":"medium","visual":0.7,"source":0.86,"image":0.84,"risk":0.01,"license":0.08,"facts":["has a flute-like song","has spotted chest feathers","nests in eastern forests"]},
    {"id":"glass-frog","name":"Glass Frog","scientificName":"Centrolenidae","taxonomy":"amphibian","habitats":["forest","wetland","rainforest"],"regions":["Americas"],"traits":["transparent","tiny","green"],"hooks":["weird","tiny"],"kid":"surprise","visual":0.96,"source":0.84,"image":0.76,"risk":0.01,"license":0.16,"facts":["some have see-through belly skin","lays eggs on leaves above streams","is often bright green"]},
    {"id":"poison-dart-frog","name":"Poison Dart Frog","scientificName":"Dendrobatidae","taxonomy":"amphibian","habitats":["forest","rainforest","wetland"],"regions":["Americas"],"traits":["bright-color","tiny"],"hooks":["colorful","tiny"],"kid":"common","visual":0.98,"source":0.86,"image":0.86,"risk":0.12,"license":0.08,"facts":["has bright warning colors","is very small","lives on rainforest floors"]},
    {"id":"red-eyed-tree-frog","name":"Red-eyed Tree Frog","scientificName":"Agalychnis callidryas","taxonomy":"amphibian","habitats":["forest","rainforest","wetland"],"regions":["Americas"],"traits":["big-eyes","bright-color","climber"],"hooks":["cute","colorful"],"kid":"common","visual":0.98,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["has bright red eyes","climbs on rainforest leaves","hides its colorful sides while resting"]},
    {"id":"olm","name":"Olm","scientificName":"Proteus anguinus","taxonomy":"amphibian","habitats":["cave","wetland"],"regions":["Europe"],"traits":["pale","weird","aquatic"],"hooks":["weird"],"kid":"surprise","visual":0.88,"source":0.84,"image":0.7,"risk":0.01,"license":0.16,"facts":["lives in dark cave waters","has pale skin","can sense its way without much light"]},
    {"id":"great-crested-newt","name":"Great Crested Newt","scientificName":"Triturus cristatus","taxonomy":"amphibian","habitats":["wetland","forest"],"regions":["Europe"],"traits":["crest","spots","tiny"],"hooks":["colorful","weird"],"kid":"medium","visual":0.82,"source":0.86,"image":0.8,"risk":0.01,"license":0.08,"facts":["males grow a jagged crest in breeding season","lives near ponds","has a spotty belly"]},
    {"id":"emerald-tree-boa","name":"Emerald Tree Boa","scientificName":"Corallus caninus","taxonomy":"reptile","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["green","scales","camouflage"],"hooks":["camouflage","colorful"],"kid":"medium","visual":0.96,"source":0.84,"image":0.8,"risk":0.1,"license":0.14,"facts":["rests curled on branches","has bright green scales","uses heat-sensing pits to find prey"]},
    {"id":"leaf-tailed-gecko","name":"Leaf-tailed Gecko","scientificName":"Uroplatus","taxonomy":"reptile","habitats":["forest","rainforest"],"regions":["Africa"],"traits":["camouflage","scales","leaf-tail"],"hooks":["camouflage","weird"],"kid":"surprise","visual":0.95,"source":0.82,"image":0.74,"risk":0.01,"license":0.16,"facts":["can look like a dry leaf","clings to tree bark","uses camouflage to hide"]},
    {"id":"green-anole","name":"Green Anole","scientificName":"Anolis carolinensis","taxonomy":"reptile","habitats":["forest","backyard"],"regions":["Americas"],"traits":["green","scales","climber"],"hooks":["colorful","camouflage"],"kid":"common","visual":0.82,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["can change from green to brown","climbs fences and branches","males flash a colorful throat fan"]},
    {"id":"panther-chameleon","name":"Panther Chameleon","scientificName":"Furcifer pardalis","taxonomy":"reptile","habitats":["forest"],"regions":["Africa"],"traits":["bright-color","scales","camouflage"],"hooks":["colorful","camouflage"],"kid":"common","visual":0.98,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["can show brilliant colors","moves each eye separately","uses a long tongue to catch insects"]},
    {"id":"forest-dragon-lizard","name":"Forest Dragon Lizard","scientificName":"Hypsilurus","taxonomy":"reptile","habitats":["forest","rainforest"],"regions":["Oceania"],"traits":["crest","scales","climber"],"hooks":["weird","colorful"],"kid":"surprise","visual":0.86,"source":0.74,"image":0.62,"risk":0.01,"license":0.22,"facts":["perches on rainforest branches","has a spiky-looking crest","blends into leaves and bark"]},
    {"id":"atlas-moth","name":"Atlas Moth","scientificName":"Attacus atlas","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["wings","giant","pattern"],"hooks":["giant","colorful"],"kid":"medium","visual":0.97,"source":0.86,"image":0.88,"risk":0.01,"license":0.08,"facts":["is one of the largest moths","has wing tips that can look like snake heads","does not eat as an adult"]},
    {"id":"orchid-mantis","name":"Orchid Mantis","scientificName":"Hymenopus coronatus","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Asia"],"traits":["camouflage","bright-color","tiny"],"hooks":["camouflage","colorful"],"kid":"surprise","visual":0.98,"source":0.82,"image":0.78,"risk":0.04,"license":0.14,"facts":["looks like a flower petal","uses camouflage while waiting on plants","has pink and white coloring"]},
    {"id":"walking-leaf","name":"Walking Leaf","scientificName":"Phylliidae","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Asia","Oceania"],"traits":["camouflage","leaf","tiny"],"hooks":["camouflage","weird"],"kid":"surprise","visual":0.96,"source":0.82,"image":0.76,"risk":0.01,"license":0.14,"facts":["looks like a leaf","may sway like a leaf in the breeze","hides among plants"]},
    {"id":"goliath-bird-eater","name":"Goliath Birdeater","scientificName":"Theraphosa blondi","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["giant","hairy","legs"],"hooks":["giant","weird"],"kid":"surprise","visual":0.9,"source":0.82,"image":0.78,"risk":0.14,"license":0.12,"facts":["is one of the largest spiders by mass","lives in burrows in rainforest areas","has a very hairy body"]},
    {"id":"blue-morpho","name":"Blue Morpho","scientificName":"Morpho menelaus","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["wings","bright-color","blue"],"hooks":["colorful"],"kid":"common","visual":0.98,"source":0.86,"image":0.88,"risk":0.01,"license":0.08,"facts":["has shining blue wings","flashes color as it flies","lives in tropical forests"]},
    {"id":"stag-beetle","name":"Stag Beetle","scientificName":"Lucanidae","taxonomy":"invertebrate","habitats":["forest","backyard"],"regions":["global"],"traits":["horns","armored","tiny"],"hooks":["armored","weird"],"kid":"medium","visual":0.86,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["males have large antler-like jaws","larvae live in decaying wood","adults are strong-looking beetles"]},
    {"id":"velvet-worm","name":"Velvet Worm","scientificName":"Onychophora","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["global"],"traits":["soft","many-legs","weird"],"hooks":["weird","tiny"],"kid":"surprise","visual":0.86,"source":0.8,"image":0.66,"risk":0.02,"license":0.18,"facts":["has a soft velvety body","walks on many stubby legs","lives in damp hidden places"]},
    {"id":"millipede","name":"Millipede","scientificName":"Diplopoda","taxonomy":"invertebrate","habitats":["forest","backyard"],"regions":["global"],"traits":["many-legs","armored","tiny"],"hooks":["weird","armored"],"kid":"medium","visual":0.78,"source":0.86,"image":0.86,"risk":0.01,"license":0.08,"facts":["has many pairs of legs","curls into a coil when bothered","helps break down fallen leaves"]},
    {"id":"leafcutter-ant","name":"Leafcutter Ant","scientificName":"Atta","taxonomy":"invertebrate","habitats":["forest","rainforest"],"regions":["Americas"],"traits":["tiny","teamwork","leaf"],"hooks":["tiny","excellent-parent"],"kid":"common","visual":0.86,"source":0.86,"image":0.84,"risk":0.01,"license":0.08,"facts":["carries leaf pieces overhead","works in huge colonies","uses leaves to grow fungus food"]},
    {"id":"tapaculo","name":"Tapaculo","scientificName":"Rhinocryptidae","taxonomy":"bird","habitats":["forest","mountain"],"regions":["Americas"],"traits":["tiny","wings","hidden"],"hooks":["tiny","weird"],"kid":"surprise","visual":0.62,"source":0.76,"image":0.58,"risk":0.01,"license":0.22,"facts":["often stays hidden near the ground","has a loud voice for a small bird","lives in dense forest cover"]},
    {"id":"sunbittern","name":"Sunbittern","scientificName":"Eurypyga helias","taxonomy":"bird","habitats":["forest","wetland"],"regions":["Americas"],"traits":["wings","pattern","river"],"hooks":["colorful","weird"],"kid":"surprise","visual":0.92,"source":0.84,"image":0.78,"risk":0.01,"license":0.12,"facts":["opens patterned wings like big eyes","walks near forest streams","has delicate gray and orange markings"]},
    {"id":"okapi-duiker","name":"Yellow-backed Duiker","scientificName":"Cephalophus silvicultor","taxonomy":"mammal","habitats":["forest","rainforest"],"regions":["Africa"],"traits":["small","hoofed","stripe"],"hooks":["camouflage","cute"],"kid":"surprise","visual":0.74,"source":0.78,"image":0.62,"risk":0.02,"license":0.22,"facts":["is a forest antelope","has a yellowish patch on its back","moves through dense vegetation"]},
    {"id":"malayan-tapir","name":"Malayan Tapir","scientificName":"Tapirus indicus","taxonomy":"mammal","habitats":["forest","wetland"],"regions":["Asia"],"traits":["black-white","snout","large"],"hooks":["weird","giant"],"kid":"medium","visual":0.9,"source":0.84,"image":0.82,"risk":0.01,"license":0.1,"facts":["has a black-and-white body pattern","uses a short trunk-like snout","lives near forests and water"]},
    {"id":"shoebill","name":"Shoebill","scientificName":"Balaeniceps rex","taxonomy":"bird","habitats":["wetland"],"regions":["Africa"],"traits":["huge-beak","wings","giant"],"hooks":["weird","giant"],"kid":"medium","visual":0.98,"source":0.86,"image":0.86,"risk":0.06,"license":0.08,"facts":["has a huge shoe-shaped bill","stands very still in wetlands","can make bill-clattering sounds"]},
    {"id":"platypus","name":"Platypus","scientificName":"Ornithorhynchus anatinus","taxonomy":"mammal","habitats":["wetland","river"],"regions":["Oceania"],"traits":["bill","webbed-feet","weird"],"hooks":["weird","cute"],"kid":"common","visual":0.94,"source":0.88,"image":0.84,"risk":0.03,"license":0.08,"facts":["has a duck-like bill","lays eggs even though it is a mammal","swims in rivers and streams"]},
    {"id":"leafy-seadragon","name":"Leafy Seadragon","scientificName":"Phycodurus eques","taxonomy":"fish","habitats":["ocean"],"regions":["Oceania"],"traits":["camouflage","leafy","tiny"],"hooks":["camouflage","weird"],"kid":"medium","visual":0.98,"source":0.86,"image":0.82,"risk":0.01,"license":0.1,"facts":["has leaf-like body parts","drifts among seaweed","is related to seahorses"]},
    {"id":"garden-eel","name":"Garden Eel","scientificName":"Heteroconger hassi","taxonomy":"fish","habitats":["ocean","reef"],"regions":["global"],"traits":["tiny","group","sand"],"hooks":["tiny","weird"],"kid":"medium","visual":0.84,"source":0.84,"image":0.76,"risk":0.01,"license":0.12,"facts":["pokes out of sandy burrows","lives in groups that look like a garden","ducks down when startled"]},
    {"id":"mandarinfish","name":"Mandarinfish","scientificName":"Synchiropus splendidus","taxonomy":"fish","habitats":["ocean","reef"],"regions":["Asia","Oceania"],"traits":["bright-color","tiny","reef"],"hooks":["colorful","tiny"],"kid":"medium","visual":0.99,"source":0.86,"image":0.84,"risk":0.01,"license":0.1,"facts":["has swirling blue and orange colors","lives around reefs","is a small bottom-dwelling fish"]},
    {"id":"pika","name":"Pika","scientificName":"Ochotona princeps","taxonomy":"mammal","habitats":["mountain"],"regions":["Americas","Asia"],"traits":["tiny","round","cute"],"hooks":["cute","tiny"],"kid":"medium","visual":0.88,"source":0.86,"image":0.84,"risk":0.01,"license":0.08,"facts":["collects plant piles called haypiles","lives among mountain rocks","makes sharp squeaking calls"]},
    {"id":"secretary-bird","name":"Secretary Bird","scientificName":"Sagittarius serpentarius","taxonomy":"bird","habitats":["grassland","savanna"],"regions":["Africa"],"traits":["long-legs","crest","wings"],"hooks":["speedy","weird"],"kid":"medium","visual":0.96,"source":0.86,"image":0.84,"risk":0.05,"license":0.08,"facts":["walks on long legs through grasslands","has dramatic head feathers","hunts mostly on the ground"]},
    {"id":"jerboa","name":"Jerboa","scientificName":"Jaculus","taxonomy":"mammal","habitats":["desert"],"regions":["Africa","Asia"],"traits":["tiny","long-legs","jumper"],"hooks":["tiny","speedy"],"kid":"medium","visual":0.9,"source":0.82,"image":0.72,"risk":0.01,"license":0.16,"facts":["hops on long back legs","has a long balancing tail","lives in dry desert areas"]},
    {"id":"sand-cat","name":"Sand Cat","scientificName":"Felis margarita","taxonomy":"mammal","habitats":["desert"],"regions":["Africa","Asia"],"traits":["cat","cute","sand-color"],"hooks":["cute","camouflage"],"kid":"medium","visual":0.96,"source":0.84,"image":0.76,"risk":0.03,"license":0.16,"facts":["has furry feet for hot sand","is small and desert-colored","is active mostly at night"]},
]


def read_json(p: Path) -> Any:
    return json.loads(p.read_text())


def write_json(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def fetch_json(url: str, params: Json | None = None, timeout: int = HTTP_TIMEOUT) -> Any:
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode(params)}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (ssl.SSLCertVerificationError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            raise
        # Some local Python installs do not share macOS' trust store. These
        # calls only read public catalog/source APIs and never send secrets, so
        # fall back to an unverified context rather than making Phase 1 unusable.
        with urlopen(req, timeout=timeout, context=ssl._create_unverified_context()) as response:  # noqa: SLF001
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("_transportWarnings", []).append("used unverified TLS fallback because local Python certificate store rejected the server certificate")
            return payload


def fetch_bytes(url: str, timeout: int = HTTP_TIMEOUT, max_bytes: int = 25_000_000) -> tuple[bytes, Json]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})

    def read_response(response: Any, transport_warnings: list[str] | None = None) -> tuple[bytes, Json]:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(1024 * 128)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"download exceeded max bytes ({max_bytes})")
            chunks.append(chunk)
        return b"".join(chunks), {
            "contentType": response.headers.get("Content-Type"),
            "contentLengthHeader": response.headers.get("Content-Length"),
            "finalURL": response.geturl(),
            "transportWarnings": transport_warnings or [],
        }

    try:
        with urlopen(req, timeout=timeout) as response:
            return read_response(response)
    except (ssl.SSLCertVerificationError, URLError) as exc:
        if isinstance(exc, URLError) and not isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            raise
        with urlopen(req, timeout=timeout, context=ssl._create_unverified_context()) as response:  # noqa: SLF001
            return read_response(response, ["used unverified TLS fallback because local Python certificate store rejected the server certificate"])


def safe_fetch_json(url: str, params: Json | None = None, timeout: int = HTTP_TIMEOUT) -> tuple[Any | None, str | None]:
    try:
        return fetch_json(url, params=params, timeout=timeout), None
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_animals(root: Path) -> list[Json]:
    return [read_json(p) for p in sorted((root / "animals").glob("*.json"))]


def load_packs(root: Path) -> list[Json]:
    return sorted([read_json(p) for p in (root / "packs").glob("*.json")], key=lambda p: (p.get("sortOrder", 9999), p.get("id", "")))


def load_policy(root: Path, name: str) -> Json:
    path = root / "policy" / name
    return read_json(path) if path.exists() else {}


def sha256_hex(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def plain_text(value: str | None) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


def display_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def source_shape(m: Json) -> Json:
    out = {
        "id": m["id"], "name": m["name"], "species": m["species"]["displayName"], "caption": m["copy"]["caption"], "imageFileName": m["image"]["primaryFileName"],
        "attributionName": m["provenance"]["photo"]["attributionName"], "sourcePageURL": m["provenance"]["fact"]["sourcePageURL"], "licenseName": m["provenance"]["photo"]["licenseName"], "licenseURL": m["provenance"]["photo"]["licenseURL"], "provenance": m["provenance"]["origin"],
        "shortDescription": m["copy"]["shortDescription"], "factSourceName": m["provenance"]["fact"]["sourceName"], "factSourceURL": m["provenance"]["fact"]["sourceURL"], "photoCommonsFile": m["provenance"]["photo"]["commonsFile"], "photoCommonsPageURL": m["provenance"]["photo"]["commonsPageURL"],
    }
    fp = m["image"].get("focalPoint")
    if fp:
        out["focalPointX"] = fp["x"]
        out["focalPointY"] = fp["y"]
    return out


def live_equivalence(root: Path, source_app_repo: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    src_animals = read_json(source_app_repo / "Content/animals/animals.json")
    src_packs = sorted([read_json(p) for p in (source_app_repo / "Content/packs").glob("*.json")], key=lambda p: (p.get("sortOrder", 9999), p.get("id", "")))
    src_rewards = read_json(source_app_repo / "Content/rewards/rewards.json")
    animals = load_animals(root)
    packs = load_packs(root)
    by_src = {a["id"]: a for a in src_animals}
    by_m = {a["id"]: a for a in animals}
    if len(src_animals) != len(animals):
        errors.append(f"animal count mismatch source={len(src_animals)} migrated={len(animals)}")
    missing = sorted(set(by_src) - set(by_m))
    extra = sorted(set(by_m) - set(by_src))
    if missing:
        errors.append(f"missing migrated animals: {missing}")
    if extra:
        errors.append(f"extra migrated animals: {extra}")
    fields = ["id", "name", "species", "caption", "imageFileName", "attributionName", "sourcePageURL", "licenseName", "licenseURL", "provenance", "shortDescription", "factSourceName", "factSourceURL", "photoCommonsFile", "photoCommonsPageURL", "focalPointX", "focalPointY"]
    for aid, s in by_src.items():
        if aid not in by_m:
            continue
        rt = source_shape(by_m[aid])
        for key in fields:
            if s.get(key) != rt.get(key):
                errors.append(f"{aid}: field {key} mismatch source={s.get(key)!r} migrated={rt.get(key)!r}")
    sp = {p["id"]: p for p in src_packs}
    mp = {p["id"]: p for p in packs}
    if len(sp) != len(mp):
        errors.append(f"pack count mismatch source={len(sp)} migrated={len(mp)}")
    for pid, p in sp.items():
        if pid not in mp:
            errors.append(f"missing migrated pack: {pid}")
            continue
        if p != mp[pid]:
            errors.append(f"{pid}: pack record mismatch")
    rewards_path = root / "rewards/rewards.json"
    if not rewards_path.exists():
        errors.append("missing migrated rewards/rewards.json")
    elif read_json(rewards_path) != src_rewards:
        errors.append("reward config mismatch")
    src_enc = source_app_repo / "Content/encyclopedia/encyclopedia.json"
    migrated_enc = root / "encyclopedia/encyclopedia.json"
    if src_enc.exists():
        if not migrated_enc.exists():
            warnings.append("source encyclopedia exists but migrated encyclopedia/encyclopedia.json is missing")
        elif read_json(migrated_enc) != read_json(src_enc):
            errors.append("encyclopedia sidecar mismatch")
    return errors, warnings


def validate_publish(root: Path, allow_staging: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    latest_path = root / "dist/latest.json"
    if not latest_path.exists():
        return ["missing dist/latest.json"], warnings
    latest = read_json(latest_path)
    required = ["schemaVersion", "catalogVersion", "publishedAt", "minAppVersion", "manifestURL", "manifestSHA256", "signatureAlgorithm", "signature"]
    for k in required:
        if k not in latest:
            errors.append(f"dist/latest.json missing {k}")
    version = latest.get("catalogVersion")
    catalog_path = root / "dist" / f"catalog-v{int(version):04d}.json" if isinstance(version, int) else None
    if not catalog_path or not catalog_path.exists():
        errors.append(f"missing versioned catalog for version {version!r}")
    staging = latest.get("stagingOnly") is True
    if staging and allow_staging:
        warnings.append("publish validation allowed unsigned staging latest.json")
    else:
        if latest.get("signatureAlgorithm") != "P256.ECDSA.SHA256":
            errors.append("latest.json signatureAlgorithm must be P256.ECDSA.SHA256")
        if not latest.get("manifestSHA256"):
            errors.append("latest.json missing manifestSHA256")
        if not latest.get("signature"):
            errors.append("latest.json missing signature")
        if catalog_path and catalog_path.exists() and latest.get("manifestSHA256") and latest["manifestSHA256"] != sha256_hex(catalog_path):
            errors.append("latest.json manifestSHA256 does not match catalog bytes")
    assets_manifest = root / "dist" / f"assets-manifest-v{int(version):04d}.json" if isinstance(version, int) else None
    if assets_manifest and assets_manifest.exists():
        manifest = read_json(assets_manifest)
        for asset in manifest.get("assets", []):
            if "animalID" not in asset or "fileName" not in asset:
                errors.append("asset entry missing animalID/fileName")
            if not allow_staging:
                for k in ["sha256", "byteSize", "contentType"]:
                    if not asset.get(k):
                        errors.append(f"asset {asset.get('animalID')}: missing {k}")
    else:
        warnings.append("assets manifest not found for this catalog version")
    return errors, warnings


def validate_common(root: Path, mode: str, source_app_repo: str | None = None, allow_staging: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    animals = load_animals(root)
    packs = load_packs(root)
    ids = [a.get("id") for a in animals]
    if len(ids) != len(set(ids)):
        errors.append("duplicate animal IDs in animals/*.json")
    byid = {a["id"]: a for a in animals if "id" in a}
    for a in animals:
        aid = a.get("id", "<missing>")
        for path in [("name",), ("species", "displayName"), ("copy", "caption"), ("image", "primaryFileName"), ("provenance", "origin"), ("provenance", "photo", "attributionName"), ("provenance", "photo", "licenseName"), ("provenance", "fact", "sourcePageURL"), ("review", "status")]:
            cur: Any = a
            for part in path:
                cur = cur.get(part) if isinstance(cur, dict) else None
            if cur in (None, ""):
                errors.append(f"{aid}: missing required field {'.'.join(path)}")
        if not a.get("tags", {}).get("taxonomy"):
            warnings.append(f"{aid}: missing taxonomy tag")
        if a.get("review", {}).get("tagsStatus") != "needsTagReview":
            warnings.append(f"{aid}: tagsStatus should remain needsTagReview until human tag review")
        fp = a.get("image", {}).get("focalPoint")
        if fp is None and not a.get("image", {}).get("focalPointGrandfathered"):
            warnings.append(f"{aid}: missing focalPoint and not grandfathered")
    pack_ids = [p.get("id") for p in packs]
    if len(pack_ids) != len(set(pack_ids)):
        errors.append("duplicate pack IDs")
    for p in packs:
        pid = p.get("id", "<missing>")
        animal_ids = p.get("animalIDs", [])
        if len(animal_ids) != len(set(animal_ids)):
            errors.append(f"{pid}: duplicate animalIDs")
        for aid in animal_ids:
            if aid not in byid:
                errors.append(f"{pid}: missing animal {aid}")
        if p.get("coverAnimalID") not in animal_ids:
            errors.append(f"{pid}: coverAnimalID not in animalIDs")
    if mode == "baseline":
        if len(animals) != 200:
            errors.append(f"baseline requires 200 animals, found {len(animals)}")
        if len(packs) != 20:
            errors.append(f"baseline requires 20 packs, found {len(packs)}")
        for p in packs:
            if len(p.get("animalIDs", [])) != 10:
                errors.append(f"baseline pack {p.get('id')} must have 10 animals")
        report_path = root / "indexes/migration-report.json"
        if not report_path.exists():
            errors.append("missing indexes/migration-report.json")
        else:
            report = read_json(report_path)
            eq = report.get("equivalence", {})
            if not eq.get("passed"):
                errors.append(f"migration equivalence failed: {eq.get('failureCount')} failures")
            if report.get("newAnimalsAdded") != 0:
                errors.append("baseline must not add new animals")
        if source_app_repo:
            live_errors, live_warnings = live_equivalence(root, Path(source_app_repo).resolve())
            errors.extend(live_errors)
            warnings.extend(live_warnings)
    elif mode == "publish":
        pub_errors, pub_warnings = validate_publish(root, allow_staging)
        errors.extend(pub_errors)
        warnings.extend(pub_warnings)
    elif mode == "expansion":
        if len(animals) < 200:
            errors.append("expansion catalog cannot have fewer than 200 animals")
    return errors, warnings


def existing_index(animals: list[Json]) -> Json:
    return {
        "ids": {a.get("id") for a in animals},
        "names": {norm(a.get("name")) for a in animals},
        "species": {norm(a.get("species", {}).get("displayName")) for a in animals},
        "source_urls": {a.get("provenance", {}).get("fact", {}).get("sourcePageURL") for a in animals if a.get("provenance", {}).get("fact", {}).get("sourcePageURL")},
    }


def candidate_duplicate_reason(candidate: Json, index: Json) -> str | None:
    cid = candidate.get("id") or norm(candidate.get("name"))
    if cid in index["ids"]:
        return "id"
    if norm(candidate.get("name")) in index["names"]:
        return "name"
    scientific = norm(candidate.get("scientificName"))
    if scientific and scientific in index["species"]:
        return "scientificName"
    return None


def theme_terms(theme: str) -> set[str]:
    base = {norm(theme)} if theme else set()
    for key, vals in THEME_HINTS.items():
        if norm(theme) == key or norm(theme) in [norm(v) for v in vals]:
            base.update(norm(v) for v in vals)
            base.add(key)
    return {t for t in base if t}


def theme_match(candidate: Json, theme: str) -> float:
    if not theme:
        return 0.0
    terms = theme_terms(theme)
    searchable = {norm(candidate.get("taxonomy"))}
    searchable.update(norm(h) for h in candidate.get("habitats", []))
    searchable.update(norm(t) for t in candidate.get("traits", []))
    searchable.update(norm(h) for h in candidate.get("hooks", []))
    searchable.update(norm(r) for r in candidate.get("regions", []))
    searchable.update(norm(part) for part in re.split(r"\s+", candidate.get("name", "")))
    return 1.0 if terms & searchable else 0.0


def ratios(counts: Counter[str], total: int) -> dict[str, float]:
    denom = max(1, total)
    return {k: v / denom for k, v in counts.items()}


def infer_taxonomy_from_text(text: str) -> str:
    value = text.lower()
    if any(w in value for w in ["frog", "toad", "newt", "salamander", "amphibian", "caecilian"]):
        return "amphibian"
    if any(w in value for w in ["snake", "lizard", "turtle", "tortoise", "crocodile", "alligator", "gecko", "skink", "reptile"]):
        return "reptile"
    if any(w in value for w in ["fish", "shark", "ray", "eel", "seadragon", "seahorse"]):
        return "fish"
    if any(w in value for w in ["beetle", "moth", "butterfly", "mantis", "ant", "spider", "crab", "lobster", "snail", "worm", "insect", "arachnid", "mollusc", "mollusk"]):
        return "invertebrate"
    if any(w in value for w in ["bird", "eagle", "owl", "parrot", "duck", "goose", "heron", "hornbill", "tanager", "pigeon", "dove"]):
        return "bird"
    return "mammal"


def infer_traits_from_text(text: str, taxonomy: str) -> list[str]:
    value = text.lower()
    traits: list[str] = []
    for word, trait in [
        ("stripe", "stripes"), ("spot", "spots"), ("horn", "horns"), ("wing", "wings"),
        ("bright", "bright-color"), ("color", "colorful"), ("camouflage", "camouflage"),
        ("nocturnal", "nocturnal"), ("night", "nocturnal"), ("giant", "giant"), ("large", "large"),
        ("small", "tiny"), ("tiny", "tiny"), ("climb", "climber"), ("tree", "climber"),
        ("shell", "shell"), ("venom", "venom"), ("glide", "glider"), ("tail", "tail"),
    ]:
        if word in value:
            traits.append(trait)
    if taxonomy == "bird":
        traits.append("wings")
    if taxonomy in {"reptile", "fish"}:
        traits.append("scales")
    if taxonomy == "invertebrate":
        traits.append("tiny")
    seen: set[str] = set()
    return [t for t in traits if not (t in seen or seen.add(t))] or [taxonomy]


def infer_hooks_from_traits(traits: list[str], text: str) -> list[str]:
    value = text.lower()
    hooks: list[str] = []
    for trait in traits:
        if trait in {"tiny"}:
            hooks.append("tiny")
        elif trait in {"giant", "large"}:
            hooks.append("giant")
        elif trait in {"camouflage"}:
            hooks.append("camouflage")
        elif trait in {"nocturnal"}:
            hooks.append("nocturnal")
        elif trait in {"bright-color", "colorful", "spots", "stripes"}:
            hooks.append("colorful")
        elif trait in {"shell", "horns"}:
            hooks.append("armored")
    if any(w in value for w in ["fast", "leap", "jump", "fly", "glide"]):
        hooks.append("speedy")
    if not hooks:
        hooks.append("cute" if any(w in value for w in ["panda", "fox", "rabbit", "marten", "cat"]) else "weird")
    seen: set[str] = set()
    return [h for h in hooks if not (h in seen or seen.add(h))]


def inferred_habitats_for_theme(theme: str, text: str) -> list[str]:
    value = f"{theme} {text}".lower()
    habitats: list[str] = []
    for habitat, words in {
        "forest": ["forest", "rainforest", "woodland", "jungle", "canopy"],
        "ocean": ["ocean", "marine", "reef", "sea", "coastal"],
        "wetland": ["wetland", "marsh", "swamp", "river", "pond", "stream"],
        "grassland": ["grassland", "savanna", "prairie", "meadow"],
        "desert": ["desert", "arid", "sand"],
        "mountain": ["mountain", "alpine", "highland"],
        "polar": ["polar", "arctic", "antarctic"],
        "backyard": ["backyard", "garden", "urban"],
        "farm": ["farm", "domestic"],
        "cave": ["cave"],
    }.items():
        if any(w in value for w in words):
            habitats.append(habitat)
    return habitats or [norm(theme) or "forest"]


def wikidata_search(query: str, limit: int) -> tuple[list[Json], list[str]]:
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "uselang": "en",
        "type": "item",
        "limit": min(50, max(1, limit)),
        "search": query,
    }
    payload, error = safe_fetch_json("https://www.wikidata.org/w/api.php", params)
    if error:
        return [], [f"wikidata search {query!r}: {error}"]
    return payload.get("search", []), []


def wikidata_entities(ids: list[str]) -> tuple[dict[str, Json], list[str]]:
    if not ids:
        return {}, []
    params = {
        "action": "wbgetentities",
        "format": "json",
        "languages": "en",
        "props": "labels|descriptions|claims|sitelinks",
        "ids": "|".join(ids[:50]),
    }
    payload, error = safe_fetch_json("https://www.wikidata.org/w/api.php", params)
    if error:
        return {}, [f"wikidata entities: {error}"]
    return payload.get("entities", {}), []


def claim_values(entity: Json, prop: str) -> list[str]:
    out: list[str] = []
    for claim in entity.get("claims", {}).get(prop, []):
        datavalue = claim.get("mainsnak", {}).get("datavalue", {})
        value = datavalue.get("value")
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            if "id" in value:
                out.append(value["id"])
            elif "text" in value:
                out.append(value["text"])
    return out


def wikipedia_title(entity: Json) -> str | None:
    sitelink = entity.get("sitelinks", {}).get("enwiki", {})
    return sitelink.get("title")


def candidate_from_wikidata_search_hit(hit: Json, entity: Json, theme: str) -> Json | None:
    label = entity.get("labels", {}).get("en", {}).get("value") or hit.get("label")
    if not label:
        return None
    description = entity.get("descriptions", {}).get("en", {}).get("value") or hit.get("description") or ""
    text = f"{label} {description}"
    if not any(word in description.lower() for word in ["species", "animal", "bird", "mammal", "fish", "frog", "insect", "reptile", "amphibian", "genus"]):
        return None
    taxonomy = infer_taxonomy_from_text(text)
    traits = infer_traits_from_text(text, taxonomy)
    commons_images = claim_values(entity, "P18")
    scientific_names = claim_values(entity, "P225")
    wikidata_id = entity.get("id") or hit.get("id")
    page_title = wikipedia_title(entity)
    return {
        "id": norm(label),
        "name": label,
        "scientificName": scientific_names[0] if scientific_names else None,
        "taxonomy": taxonomy,
        "habitats": inferred_habitats_for_theme(theme, text),
        "regions": ["needs-review"],
        "traits": traits,
        "hooks": infer_hooks_from_traits(traits, text),
        "kid": "medium" if any(w in label.lower() for w in ["frog", "fox", "cat", "bird", "eagle", "turtle", "fish"]) else "surprise",
        "visual": 0.82 if commons_images else 0.68,
        "source": 0.92,
        "image": 0.9 if commons_images else 0.42,
        "risk": 0.12 if any(w in text.lower() for w in ["venom", "poison", "predator", "shark", "spider"]) else 0.03,
        "license": 0.08 if commons_images else 0.18,
        "facts": [description] if description else [],
        "externalIDs": {"wikidata": wikidata_id, **({"wikipediaTitle": page_title} if page_title else {})},
        "sourceURLs": {"wikidata": f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else None, **({"wikipedia": wikipedia_url(page_title)} if page_title else {})},
        "mediaHints": {"wikidataImage": commons_images[0] if commons_images else None},
        "sourceAdapter": "wikidata-api",
    }


def discover_live_candidates(theme: str, count: int, offline: bool = False) -> tuple[list[Json], Json]:
    diagnostics: Json = {"sourceAdapters": [], "warnings": [], "queries": []}
    if offline:
        diagnostics["warnings"].append("live discovery disabled by --offline; using local seed queue only")
        return [], diagnostics
    terms = [theme, *list(theme_terms(theme))]
    broad_taxa = ["frog", "lizard", "snake", "bird", "beetle", "moth", "mammal", "fish"]
    queries = []
    for taxon in broad_taxa:
        queries.append(f"{theme} {taxon}")
    for term in terms[:4]:
        queries.append(f"{term} animal species")
    seen_ids: set[str] = set()
    hits: list[Json] = []
    for query in queries[:10]:
        diagnostics["queries"].append(query)
        found, warnings = wikidata_search(query, max(8, min(25, count)))
        diagnostics["warnings"].extend(warnings)
        for hit in found:
            qid = hit.get("id")
            if qid and qid not in seen_ids:
                seen_ids.add(qid)
                hits.append(hit)
        time.sleep(0.05)
    entities, warnings = wikidata_entities([h.get("id") for h in hits if h.get("id")])
    diagnostics["warnings"].extend(warnings)
    diagnostics["sourceAdapters"].append({"name": "Wikidata API", "kind": "trusted-structured-source", "hitCount": len(hits), "entityCount": len(entities)})
    candidates: list[Json] = []
    seen_slugs: set[str] = set()
    for hit in hits:
        entity = entities.get(hit.get("id"), {})
        candidate = candidate_from_wikidata_search_hit(hit, entity, theme)
        if not candidate:
            continue
        if candidate["id"] in seen_slugs:
            continue
        seen_slugs.add(candidate["id"])
        candidates.append(candidate)
    return candidates, diagnostics


def score_candidate(candidate: Json, animals: list[Json], packs: list[Json], balance_policy: Json, novelty_policy: Json, theme: str) -> Json:
    tax_counts = Counter(a.get("tags", {}).get("taxonomy", "unknown") for a in animals)
    habitat_counts = Counter(h for a in animals for h in a.get("tags", {}).get("habitats", []))
    hook_counts = Counter(h for a in animals for h in a.get("tags", {}).get("hookArchetypes", []))
    total = max(1, len(animals))
    targets = balance_policy.get("globalTargets", {})
    tax_target = targets.get("taxonomy", {}).get(candidate["taxonomy"], 0.0)
    tax_actual = tax_counts.get(candidate["taxonomy"], 0) / total
    habitat_gaps = []
    for habitat in candidate.get("habitats", []):
        target = targets.get("habitat", {}).get(habitat, 0.0)
        actual = habitat_counts.get(habitat, 0) / total
        habitat_gaps.append(target - actual)
    balance_gap_score = max(0.0, tax_target - tax_actual) * 34 + max([0.0] + habitat_gaps) * 28
    overrepresented_habitat_penalty = abs(min([0.0] + habitat_gaps)) * 18
    allowed_hooks = novelty_policy.get("hookArchetypes", [])
    least_hook_count = min([hook_counts.get(h, 0) for h in allowed_hooks], default=0)
    candidate_hook_counts = [hook_counts.get(h, 0) for h in candidate.get("hooks", [])]
    novelty_gap_score = max(0.0, (sum(hook_counts.values()) / max(1, len(allowed_hooks))) - min(candidate_hook_counts or [least_hook_count])) * 0.18
    kid_recognition_score = {"common": 10.0, "medium": 7.0, "surprise": 4.5, "obscure": 2.5}.get(candidate.get("kid"), 5.0)
    visual_distinctiveness_score = float(candidate.get("visual", 0.6)) * 10
    source_quality_score = float(candidate.get("source", 0.7)) * 10
    image_availability_score = float(candidate.get("image", 0.6)) * 10
    index = existing_index(animals)
    duplicate_reason = candidate_duplicate_reason(candidate, index)
    duplicate_similarity_penalty = 100.0 if duplicate_reason else 0.0
    recent_window = novelty_policy.get("recentDropWindow", 4)
    recent_pack_ids = [aid for p in packs[-recent_window:] for aid in p.get("animalIDs", [])]
    by_id = {a["id"]: a for a in animals}
    recent_habitats = Counter(h for aid in recent_pack_ids for h in by_id.get(aid, {}).get("tags", {}).get("habitats", []))
    recent_hooks = Counter(h for aid in recent_pack_ids for h in by_id.get(aid, {}).get("tags", {}).get("hookArchetypes", []))
    recent_drop_similarity_penalty = sum(recent_habitats.get(h, 0) for h in candidate.get("habitats", [])) * 0.18 + sum(recent_hooks.get(h, 0) for h in candidate.get("hooks", [])) * 0.22
    scary_or_gory_risk_penalty = float(candidate.get("risk", 0.0)) * 12
    licensing_complexity_penalty = float(candidate.get("license", 0.1)) * 10
    theme_bonus = theme_match(candidate, theme) * 9
    total_score = (
        balance_gap_score
        + novelty_gap_score
        + kid_recognition_score
        + visual_distinctiveness_score
        + source_quality_score
        + image_availability_score
        + theme_bonus
        - duplicate_similarity_penalty
        - recent_drop_similarity_penalty
        - overrepresented_habitat_penalty
        - scary_or_gory_risk_penalty
        - licensing_complexity_penalty
    )
    return {
        "candidateID": candidate["id"],
        "name": candidate["name"],
        "score": round(total_score, 3),
        "themeMatch": theme_match(candidate, theme) > 0,
        "duplicate": duplicate_reason,
        "components": {
            "balance_gap_score": round(balance_gap_score, 3),
            "novelty_gap_score": round(novelty_gap_score, 3),
            "kid_recognition_score": round(kid_recognition_score, 3),
            "visual_distinctiveness_score": round(visual_distinctiveness_score, 3),
            "source_quality_score": round(source_quality_score, 3),
            "image_availability_score": round(image_availability_score, 3),
            "theme_bonus": round(theme_bonus, 3),
            "duplicate_similarity_penalty": round(duplicate_similarity_penalty, 3),
            "recent_drop_similarity_penalty": round(recent_drop_similarity_penalty, 3),
            "overrepresented_habitat_penalty": round(overrepresented_habitat_penalty, 3),
            "scary_or_gory_risk_penalty": round(scary_or_gory_risk_penalty, 3),
            "licensing_complexity_penalty": round(licensing_complexity_penalty, 3),
        },
        "tags": {"taxonomy": candidate["taxonomy"], "habitats": candidate.get("habitats", []), "regions": candidate.get("regions", []), "traits": candidate.get("traits", []), "hookArchetypes": candidate.get("hooks", [])},
        "facts": candidate.get("facts", []),
        "externalIDs": candidate.get("externalIDs", {}),
        "sourceURLs": candidate.get("sourceURLs", {}),
        "mediaHints": candidate.get("mediaHints", {}),
        "review": {"needsHumanReview": True, "source": candidate.get("sourceAdapter", "local-seed-queue")},
    }


def discover_candidates(root: Path, theme: str, count: int, include_duplicates: bool = False, source: str = "live", offline: bool = False) -> Json:
    animals = load_animals(root)
    packs = load_packs(root)
    balance_policy = load_policy(root, "balance-policy.json")
    novelty_policy = load_policy(root, "novelty-policy.json")
    live_candidates: list[Json] = []
    diagnostics: Json = {"sourceAdapters": [], "warnings": [], "queries": []}
    if source in {"live", "auto"}:
        live_candidates, diagnostics = discover_live_candidates(theme, count, offline=offline)
    source_candidates = live_candidates if source == "live" and live_candidates else []
    if source in {"local", "auto"} or (source == "live" and not source_candidates):
        source_candidates.extend(CANDIDATE_SEEDS)
        diagnostics.setdefault("sourceAdapters", []).append({"name": "local seed queue", "kind": "curated-local-fallback", "hitCount": len(CANDIDATE_SEEDS)})
    elif source == "live":
        # Keep a small curated fallback mixed in after live candidates so a
        # sparse live response can still fill draft packs, without hiding the
        # fact that live structured sources were queried first.
        source_candidates.extend(CANDIDATE_SEEDS)
        diagnostics.setdefault("sourceAdapters", []).append({"name": "local seed queue", "kind": "curated-fill", "hitCount": len(CANDIDATE_SEEDS)})
    scored = []
    duplicates = []
    seen_candidate_ids: set[str] = set()
    for candidate in source_candidates:
        if candidate.get("id") in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate.get("id"))
        item = score_candidate(candidate, animals, packs, balance_policy, novelty_policy, theme)
        if item["duplicate"] and not include_duplicates:
            duplicates.append({"candidateID": item["candidateID"], "name": item["name"], "reason": item["duplicate"]})
            continue
        scored.append(item)
    scored.sort(key=lambda c: (c["themeMatch"], c["score"], c["candidateID"]), reverse=True)
    return {
        "schemaVersion": 1,
        "theme": theme,
        "requestedCount": count,
        "returnedCount": min(count, len(scored)),
        "existingCatalogRead": {"animalCount": len(animals), "packCount": len(packs)},
        "sourceMode": source,
        "sourceDiagnostics": diagnostics,
        "duplicateCandidatesFiltered": duplicates,
        "scoringFormula": "balance_gap + novelty_gap + kid_recognition + visual_distinctiveness + source_quality + image_availability + theme_bonus - duplicate_similarity - recent_drop_similarity - overrepresented_habitat - scary_or_gory_risk - licensing_complexity",
        "candidates": scored[:count],
    }


def load_review_candidates(root: Path) -> list[Json]:
    candidates: list[Json] = []
    for pattern in ["review/**/*.json", "candidates/**/*.json", "drafts/**/*.json"]:
        for path in root.glob(pattern):
            try:
                payload = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            for item in payload.get("candidates", []) if isinstance(payload, dict) else []:
                if item.get("candidateID"):
                    candidates.append({
                        "id": item.get("candidateID"),
                        "name": item.get("name"),
                        "scientificName": item.get("scientificName"),
                        "taxonomy": item.get("tags", {}).get("taxonomy", "mammal"),
                        "habitats": item.get("tags", {}).get("habitats", []),
                        "regions": item.get("tags", {}).get("regions", []),
                        "traits": item.get("tags", {}).get("traits", []),
                        "hooks": item.get("tags", {}).get("hookArchetypes", []),
                        "kid": "medium",
                        "visual": item.get("components", {}).get("visual_distinctiveness_score", 7) / 10,
                        "source": item.get("components", {}).get("source_quality_score", 7) / 10,
                        "image": item.get("components", {}).get("image_availability_score", 6) / 10,
                        "risk": item.get("components", {}).get("scary_or_gory_risk_penalty", 0) / 12,
                        "license": item.get("components", {}).get("licensing_complexity_penalty", 1) / 10,
                        "facts": item.get("facts", []),
                        "externalIDs": item.get("externalIDs", {}),
                        "sourceURLs": item.get("sourceURLs", {}),
                        "mediaHints": item.get("mediaHints", {}),
                        "sourceAdapter": item.get("review", {}).get("source", "review-artifact"),
                    })
    return candidates


def find_candidate_or_existing(root: Path, candidate_id: str) -> tuple[str, Json | None]:
    slug = norm(candidate_id)
    for candidate in load_review_candidates(root):
        if candidate.get("id") == slug or norm(candidate.get("name")) == slug:
            return "candidate", candidate
    for seed in CANDIDATE_SEEDS:
        if seed["id"] == slug or norm(seed["name"]) == slug:
            return "candidate", seed
    for animal in load_animals(root):
        if animal.get("id") == slug or norm(animal.get("name")) == slug:
            return "existing", animal
    return "missing", None


def commons_search_url(name: str) -> str:
    return "https://commons.wikimedia.org/w/index.php?search=" + quote_plus(name) + "&title=Special:MediaSearch&type=image"


def wikipedia_url(name: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote_plus(name.replace(" ", "_"))


def commons_file_page_url(title: str) -> str:
    return "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"), safe="_:")


def license_allowed(license_short_name: str | None, policy: Json) -> bool:
    value = (license_short_name or "").lower()
    if not value:
        return False
    rejected = [m.lower() for m in policy.get("rejectedLicenseMarkers", [])]
    if any(marker.lower() in value for marker in rejected):
        return False
    allowed = [m.lower() for m in policy.get("allowedLicenseFamilies", [])]
    return any(value.startswith(a.lower()) or a.lower() in value for a in allowed)


def media_title_review_flags(title: str | None, mime: str | None) -> list[str]:
    lowered = (title or "").lower()
    flags: list[str] = []
    if any(term in lowered for term in MEDIA_REJECT_TITLE_TERMS):
        flags.append("likely-unsuitable-title")
    if lowered.endswith(".svg") or (mime or "") == "image/svg+xml":
        flags.append("vector-or-map-needs-review")
    return flags


def commons_media_candidates(name: str, limit: int, policy: Json) -> tuple[list[Json], list[str]]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": name,
        "gsrnamespace": 6,
        "gsrlimit": min(max(limit, 1), 20),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
    }
    payload, error = safe_fetch_json("https://commons.wikimedia.org/w/api.php", params)
    if error:
        return [], [f"commons media search {name!r}: {error}"]
    pages = payload.get("query", {}).get("pages", {})
    results: list[Json] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        ext = info.get("extmetadata", {})
        license_name = (ext.get("LicenseShortName") or ext.get("License" ) or {}).get("value")
        artist = (ext.get("Artist") or {}).get("value")
        credit = (ext.get("Credit") or {}).get("value")
        title = page.get("title")
        mime = info.get("mime")
        allowed = license_allowed(license_name, policy)
        title_flags = media_title_review_flags(title, mime)
        results.append({
            "title": title,
            "commonsPageURL": commons_file_page_url(title) if title else None,
            "thumbURL": info.get("thumburl"),
            "originalURL": info.get("url"),
            "mime": mime,
            "width": info.get("width"),
            "height": info.get("height"),
            "byteSize": info.get("size"),
            "licenseName": license_name,
            "licenseURL": (ext.get("LicenseUrl") or {}).get("value"),
            "attributionNameHTML": artist or credit,
            "licenseAllowed": allowed,
            "reviewFlags": title_flags + [flag for flag, present in {
                "license-needs-review": not allowed,
                "non-image-mime": not (mime or "").startswith("image/"),
                "low-resolution": min(info.get("width") or 0, info.get("height") or 0) < 800,
                "identity-needs-human-confirmation": True,
                "kid-safety-needs-human-confirmation": True,
            }.items() if present],
        })
    results.sort(key=lambda r: (r["licenseAllowed"], "likely-unsuitable-title" not in r.get("reviewFlags", []), "vector-or-map-needs-review" not in r.get("reviewFlags", []), min(r.get("width") or 0, r.get("height") or 0), r.get("byteSize") or 0), reverse=True)
    return results, []


def media_search_queries(item: Json) -> list[str]:
    negative = " -skull -skeleton -taxidermy -taxidermied -specimen -museum -bone -pelt -dead -roadkill"
    name = item.get("name") or item.get("id") or ""
    scientific = item.get("scientificName") or item.get("species", {}).get("scientificName") or item.get("species", {}).get("displayName") or ""
    queries = [f"{name}{negative}"]
    if scientific and scientific.lower() != name.lower():
        queries.append(f"{scientific} animal{negative}")
    queries.append(f"{name} photo{negative}")
    return [q.strip() for q in queries if q.strip()]


def commons_media_candidates_for_item(item: Json, limit: int, policy: Json) -> tuple[list[Json], list[str], list[str]]:
    by_title: dict[str, Json] = {}
    warnings: list[str] = []
    queries = media_search_queries(item)
    per_query_limit = min(max(limit, 8), 20)
    for query in queries:
        results, query_warnings = commons_media_candidates(query, per_query_limit, policy)
        warnings.extend(query_warnings)
        for result in results:
            title = result.get("title") or result.get("originalURL") or ""
            if title and title not in by_title:
                result["searchQuery"] = query
                by_title[title] = result
    merged = list(by_title.values())
    merged.sort(key=lambda r: (r["licenseAllowed"], "likely-unsuitable-title" not in r.get("reviewFlags", []), "vector-or-map-needs-review" not in r.get("reviewFlags", []), min(r.get("width") or 0, r.get("height") or 0), r.get("byteSize") or 0), reverse=True)
    return merged[: max(limit, 1)], warnings, queries


def media_file_extension(candidate: Json, content_type: str | None = None) -> str:
    title = candidate.get("title") or ""
    suffix = Path(title).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".svg"}:
        return suffix
    guessed = mimetypes.guess_extension((content_type or candidate.get("mime") or "").split(";")[0].strip())
    return guessed or ".img"


def write_contact_sheet(bundle_dir: Path, candidate: Json, downloads: list[Json], warnings: list[str]) -> Path:
    rows: list[str] = []
    for index, item in enumerate(downloads, start=1):
        rel = html.escape(item["localPath"])
        title = html.escape(item.get("title") or f"option {index}")
        license_name = html.escape(item.get("licenseName") or "unknown license")
        attribution = html.escape(plain_text(item.get("attributionNameHTML")) or "unknown attribution")
        commons_url = html.escape(item.get("commonsPageURL") or "")
        sha = html.escape(item.get("sha256") or "")
        dims = html.escape(f"{item.get('width') or '?'} × {item.get('height') or '?'}")
        rows.append(f"""
        <article class=\"card\">
          <img src=\"{rel}\" alt=\"{title}\">
          <div class=\"meta\">
            <h2>{index}. {title}</h2>
            <p><strong>{license_name}</strong> · {dims}</p>
            <p>{attribution}</p>
            <p><a href=\"{commons_url}\">Commons source page</a></p>
            <code>{sha}</code>
          </div>
        </article>
        """)
    warning_html = "".join(f"<li>{html.escape(w)}</li>" for w in warnings) or "<li>None from the downloader; still requires human identity/kid-safety review.</li>"
    doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>AnimalSwipe media contact sheet: {html.escape(candidate.get('name') or candidate.get('id') or 'candidate')}</title>
  <style>
    body {{ margin: 0; padding: 32px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #10141c; color: #f6efe3; }}
    header {{ max-width: 960px; margin: 0 auto 24px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(32px, 5vw, 56px); letter-spacing: -0.05em; }}
    p, li {{ color: #cbd3d1; line-height: 1.45; }}
    .grid {{ max-width: 1180px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }}
    .card {{ border: 1px solid rgba(255,255,255,.14); border-radius: 18px; overflow: hidden; background: rgba(255,255,255,.06); }}
    img {{ width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; background: #05070a; }}
    .meta {{ padding: 16px; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; }}
    code {{ display: block; overflow-wrap: anywhere; color: #9eddd4; font-size: 12px; }}
    a {{ color: #dfb76d; }}
    .warnings {{ max-width: 960px; margin: 0 auto 24px; padding: 16px 20px; border: 1px solid rgba(255,208,138,.32); border-radius: 16px; background: rgba(255,208,138,.08); }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(candidate.get('name') or candidate.get('id') or 'Candidate')} media review</h1>
    <p>Downloaded Commons originals for human review only. This sheet does not approve media, add an animal, or publish content.</p>
  </header>
  <section class=\"warnings\"><strong>Review warnings/checks</strong><ul>{warning_html}</ul></section>
  <main class=\"grid\">{''.join(rows)}</main>
</body>
</html>
"""
    path = bundle_dir / "contact-sheet.html"
    path.write_text(doc)
    return path


def download_media_bundle(root: Path, candidate: Json, media_candidates: list[Json], limit: int, max_bytes: int) -> Json:
    bundle_dir = root / "review" / "media" / norm(candidate.get("id") or candidate.get("name"))
    originals_dir = bundle_dir / "originals"
    originals_dir.mkdir(parents=True, exist_ok=True)
    downloads: list[Json] = []
    warnings: list[str] = []
    eligible = [c for c in media_candidates if c.get("licenseAllowed") and (c.get("mime") or "").startswith("image/") and c.get("originalURL") and "likely-unsuitable-title" not in c.get("reviewFlags", []) and "vector-or-map-needs-review" not in c.get("reviewFlags", [])]
    for index, option in enumerate(eligible[: max(limit, 0)], start=1):
        try:
            data, response_meta = fetch_bytes(option["originalURL"], max_bytes=max_bytes)
            content_type = response_meta.get("contentType") or option.get("mime")
            ext = media_file_extension(option, content_type)
            filename = f"{index:02d}-{norm(option.get('title') or candidate.get('id'))}{ext}"
            local_path = originals_dir / filename
            local_path.write_bytes(data)
            record = {
                **option,
                "localPath": str(local_path.relative_to(bundle_dir)),
                "absolutePath": str(local_path),
                "sha256": sha256_bytes(data),
                "downloadedByteSize": len(data),
                "httpContentType": content_type,
                "httpContentLengthHeader": response_meta.get("contentLengthHeader"),
                "finalURL": response_meta.get("finalURL"),
                "transportWarnings": response_meta.get("transportWarnings", []),
                "reviewFlags": sorted(set(option.get("reviewFlags", []) + ["downloaded-original-needs-human-review"])),
            }
            downloads.append(record)
            warnings.extend(response_meta.get("transportWarnings", []))
        except (URLError, HTTPError, TimeoutError, OSError, ValueError) as exc:
            warnings.append(f"download failed for {option.get('title')}: {type(exc).__name__}: {exc}")
    manifest = {
        "schemaVersion": 1,
        "candidate": candidate.get("id"),
        "name": candidate.get("name"),
        "status": "downloaded-media-needs-human-review" if downloads else "no-media-downloaded",
        "bundleDir": str(bundle_dir),
        "downloadedCount": len(downloads),
        "maxBytesPerFile": max_bytes,
        "downloads": downloads,
        "warnings": warnings,
        "needsHumanReview": True,
    }
    write_json(bundle_dir / "manifest.json", manifest)
    contact_sheet = write_contact_sheet(bundle_dir, candidate, downloads, warnings)
    manifest["contactSheetPath"] = str(contact_sheet)
    write_json(bundle_dir / "manifest.json", manifest)
    return manifest


def wikipedia_summary_facts(name_or_title: str) -> tuple[list[str], Json]:
    title = name_or_title.replace(" ", "_")
    payload, error = safe_fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='_')}")
    if error or not isinstance(payload, dict):
        return [], {"source": "Wikipedia REST summary", "warning": error}
    extract = payload.get("extract") or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if s.strip()]
    facts = sentences[:3]
    return facts, {"source": "Wikipedia REST summary", "title": payload.get("title"), "url": payload.get("content_urls", {}).get("desktop", {}).get("page"), "warning": None}


def media_brief(root: Path, candidate_id: str, download: bool = False, download_limit: int = 3, max_bytes: int = 25_000_000) -> Json:
    status, item = find_candidate_or_existing(root, candidate_id)
    license_policy = load_policy(root, "license-policy.json")
    if status == "missing" or item is None:
        return {"schemaVersion": 1, "candidate": candidate_id, "status": "missing", "error": "candidate not found in local seed queue or existing catalog"}
    if status == "existing":
        return {
            "schemaVersion": 1,
            "candidate": candidate_id,
            "status": "duplicate-existing-catalog-animal",
            "action": "media search skipped unless replacing approved bundled media is explicitly requested",
            "existingAnimal": {"id": item.get("id"), "name": item.get("name"), "imageFileName": item.get("image", {}).get("primaryFileName"), "sourceRelativePath": item.get("image", {}).get("sourceRelativePath"), "licenseName": item.get("provenance", {}).get("photo", {}).get("licenseName"), "licenseURL": item.get("provenance", {}).get("photo", {}).get("licenseURL"), "commonsPageURL": item.get("provenance", {}).get("photo", {}).get("commonsPageURL")},
        }
    media_candidates, warnings, media_queries = commons_media_candidates_for_item(item, max(8, download_limit), license_policy)
    payload = {
        "schemaVersion": 1,
        "candidate": item["id"],
        "name": item["name"],
        "status": "media-candidates-needs-human-review",
        "sourceAdapter": "Wikimedia Commons API",
        "searchTargets": [
            {"source": "Wikimedia Commons", "url": commons_search_url(media_queries[0] if media_queries else item["name"]), "priority": 1, "queries": media_queries},
            {"source": "Wikipedia", "url": wikipedia_url(item["name"]), "priority": 2},
        ],
        "commonsCandidates": media_candidates,
        "warnings": warnings,
        "licensePolicy": license_policy,
        "acceptanceChecklist": [
            "species identity is correct",
            "license is Public Domain, CC0, CC BY, or CC BY-SA",
            "no NC/ND/unclear-license media",
            "attribution author/name and source URL are captured",
            "image is bright, portrait-crop friendly, and kid-safe",
            "no graphic predation, injury, death, watermark, or heavy clutter",
        ],
        "initialImageAvailabilityScore": item.get("image"),
        "needsHumanReview": True,
    }
    if download:
        payload["downloadArtifacts"] = download_media_bundle(root, item, media_candidates, download_limit, max_bytes)
    return payload


def draft_copy(root: Path, candidate_id: str, allow_existing: bool = False) -> Json:
    status, item = find_candidate_or_existing(root, candidate_id)
    if status == "missing" or item is None:
        return {"schemaVersion": 1, "candidate": candidate_id, "status": "missing", "error": "candidate not found in local seed queue or existing catalog"}
    if status == "existing" and not allow_existing:
        return {
            "schemaVersion": 1,
            "candidate": candidate_id,
            "status": "duplicate-existing-catalog-animal",
            "action": "copy draft skipped to avoid replacing approved migrated copy",
            "existingCopy": {"caption": item.get("copy", {}).get("caption"), "shortDescription": item.get("copy", {}).get("shortDescription")},
        }
    if status == "existing":
        name = item.get("name")
        tags = item.get("tags", {})
        facts = [item.get("copy", {}).get("shortDescription") or f"{name} is already in AnimalSwipe."]
    else:
        name = item["name"]
        tags = {"taxonomy": item["taxonomy"], "habitats": item.get("habitats", []), "regions": item.get("regions", []), "traits": item.get("traits", []), "hookArchetypes": item.get("hooks", [])}
        wiki_title = item.get("externalIDs", {}).get("wikipediaTitle") or name
        wiki_facts, wiki_source = wikipedia_summary_facts(wiki_title)
        facts = wiki_facts or item.get("facts", [])
    fact_a = facts[0] if facts else f"{name} has a distinctive animal story."
    fact_b = facts[1] if len(facts) > 1 else fact_a
    hook = (tags.get("hookArchetypes") or ["weird"])[0]
    return {
        "schemaVersion": 1,
        "candidate": norm(name),
        "name": name,
        "status": "draft-needs-human-review",
        "llmPolicy": "Rule-based local placeholder only; future LLM drafts must use provided facts and open review artifacts, never publish directly.",
        "providedFacts": facts,
        "factSource": wiki_source if status != "existing" else {"source": "existing migrated copy"},
        "captionOptions": [
            f"{name} has a {hook.replace('-', ' ')} trick to notice.",
            f"Look closely: {name} is built for {', '.join(tags.get('habitats', [])[:1]) or 'its habitat'} life.",
            f"{name} keeps one clever secret: {fact_a.rstrip('.')}.",
        ],
        "shortDescription": f"{name} is a {tags.get('taxonomy', 'animal')} with kid-safe review notes: {fact_b.rstrip('.')}.",
        "funFact": fact_a,
        "tags": tags,
        "safetyFlags": ["needsHumanReview"],
        "needsHumanReview": True,
    }


def assemble_pack(root: Path, theme: str, size: int, source: str = "live", offline: bool = False) -> Json:
    animals = load_animals(root)
    balance_policy = load_policy(root, "balance-policy.json")
    pack_rules = balance_policy.get("packRules", {})
    # Use a broad queue so strict diversity rules can fill with complementary
    # animals if a theme-heavy prefix would over-repeat one habitat/hook.
    discovery = discover_candidates(root, theme, max(len(CANDIDATE_SEEDS), size * 8), include_duplicates=False, source=source, offline=offline)
    queue = discovery["candidates"]
    chosen: list[Json] = []
    tax = Counter()
    habitats = Counter()
    hooks = Counter()
    recognizables = 0
    surprises = 0
    min_surprises = pack_rules.get("minSurpriseAnimalsPerPack", 2)

    def candidate_kid(item: Json) -> str:
        # Live candidates don't have a durable kid score yet. Use the scoring
        # component as a transparent approximation for draft assembly only.
        score = item.get("components", {}).get("kid_recognition_score", 5)
        if score >= 9:
            return "common"
        if score >= 6:
            return "medium"
        return "surprise"

    def candidate_record(item: Json, relaxed: bool = False) -> Json:
        tags = item.get("tags", {})
        record = {
            "id": item["candidateID"],
            "name": item["name"],
            "score": item["score"],
            "taxonomy": tags.get("taxonomy", "unknown"),
            "habitats": tags.get("habitats", []),
            "hooks": tags.get("hookArchetypes", []),
            "kid": candidate_kid(item),
            "source": item.get("review", {}).get("source"),
            "externalIDs": item.get("externalIDs", {}),
        }
        if relaxed:
            record["relaxedFill"] = True
        return record

    def can_take(item: Json, relaxed: bool = False) -> bool:
        tags = item.get("tags", {})
        candidate_habitats = tags.get("habitats", [])
        taxonomy = tags.get("taxonomy", "unknown")
        if not relaxed:
            remaining_slots_after_this = size - len(chosen) - 1
            needed_surprises_after_this = max(0, min_surprises - (surprises + (1 if candidate_kid(item) == "surprise" else 0)))
            if needed_surprises_after_this > remaining_slots_after_this:
                return False
            if tax[taxonomy] >= pack_rules.get("maxSameTaxonomyPerPack", 5):
                return False
            if any(habitats[h] >= pack_rules.get("maxSameHabitatPerPack", 4) for h in candidate_habitats):
                return False
        else:
            relaxed_habitat_cap = pack_rules.get("maxSameHabitatPerPack", 4) + 2
            if any(habitats[h] >= relaxed_habitat_cap for h in candidate_habitats):
                return False
        return True

    def take(item: Json, relaxed: bool = False) -> None:
        nonlocal recognizables, surprises
        record = candidate_record(item, relaxed=relaxed)
        chosen.append(record)
        tax[record["taxonomy"]] += 1
        for h in record["habitats"]:
            habitats[h] += 1
        for h in record["hooks"]:
            hooks[h] += 1
        if record["kid"] in {"common", "medium"}:
            recognizables += 1
        if record["kid"] == "surprise":
            surprises += 1

    for scored in queue:
        if can_take(scored):
            take(scored)
        if len(chosen) == size:
            break
    if len(chosen) < size:
        chosen_ids = {c["id"] for c in chosen}
        relaxed_queue = sorted(queue, key=lambda item: (candidate_kid(item) == "surprise", item["score"]), reverse=True)
        for scored in relaxed_queue:
            if scored["candidateID"] in chosen_ids:
                continue
            if can_take(scored, relaxed=True):
                take(scored, relaxed=True)
                chosen_ids.add(scored["candidateID"])
            if len(chosen) == size:
                break
    cover = max(chosen, key=lambda c: (c["score"], len(set(c.get("hooks", [])) & {"colorful", "cute", "giant"})), default=None)
    warnings = []
    if len(chosen) < size:
        warnings.append(f"only assembled {len(chosen)} of requested {size} candidates under diversity constraints")
    if any(c.get("relaxedFill") for c in chosen):
        warnings.append("used relaxed habitat fill to satisfy requested pack size; human review should check diversity")
    if recognizables < pack_rules.get("minRecognizableAnimalsPerPack", 3):
        warnings.append("below minRecognizableAnimalsPerPack")
    if surprises < min_surprises:
        warnings.append("below minSurpriseAnimalsPerPack")
    novelty_policy = load_policy(root, "novelty-policy.json")
    min_hooks = novelty_policy.get("packRules", {}).get("minHookArchetypesPerPack", 3)
    if len(hooks) < min_hooks:
        warnings.append("below minHookArchetypesPerPack")
    return {
        "schemaVersion": 1,
        "status": "draft-pack-needs-human-review",
        "theme": theme,
        "size": size,
        "sourceMode": source,
        "sourceDiagnostics": discovery.get("sourceDiagnostics", {}),
        "packNameOptions": [f"{theme.title()} Finders", f"{theme.title()} Wonders", f"{theme.title()} Surprise"],
        "coverCandidateID": cover["id"] if cover else None,
        "animalIDs": [c["id"] for c in chosen],
        "animals": chosen,
        "summary": {"taxonomy": dict(tax), "habitats": dict(habitats), "hookArchetypes": dict(hooks), "recognizableCount": recognizables, "surpriseCount": surprises, "existingCatalogAnimalCount": len(animals)},
        "warnings": warnings,
        "commitBehavior": "No files were changed; this is a review draft only.",
        "needsHumanReview": True,
    }


def latest_matching_file(root: Path, patterns: list[str]) -> str | None:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root.glob(pattern))
    if not matches:
        return None
    return relative_path(root, max(matches, key=lambda p: p.stat().st_mtime))


def review_batch(root: Path, batch_id: str, theme: str | None, candidates: list[str], pack_path: str | None = None) -> Json:
    normalized = [norm(c) for c in candidates]
    animal_reviews: list[Json] = []
    for candidate in normalized:
        media_manifest = root / "review" / "media" / candidate / "manifest.json"
        media_manifest_payload = read_json(media_manifest) if media_manifest.exists() else None
        animal_reviews.append({
            "candidate": candidate,
            "copyArtifact": latest_matching_file(root, [f"review/copy-{candidate}.json", f"review/**/copy-{candidate}.json"]),
            "mediaBrief": latest_matching_file(root, [f"review/media-{candidate}.json", f"review/**/media-{candidate}.json"]),
            "mediaManifest": relative_path(root, media_manifest) if media_manifest.exists() else None,
            "contactSheet": relative_path(root, Path(media_manifest_payload.get("contactSheetPath"))) if media_manifest_payload and media_manifest_payload.get("contactSheetPath") else None,
            "downloadedMediaCount": media_manifest_payload.get("downloadedCount") if media_manifest_payload else 0,
            "requiredApprovals": [
                "identity confirmed against source URLs/scientific name",
                "kid-safety approved: no gore, distress, watermark, or confusing crop",
                "license and attribution fields verified from source page",
                "copy is factual, age-appropriate, and source-backed",
                "tags/balance reviewed for catalog diversity",
            ],
        })

    normalized_theme = norm(theme)
    normalized_batch_id = norm(batch_id)
    branch_slug = normalized_batch_id if normalized_theme and normalized_batch_id.startswith(normalized_theme) else norm("-".join(filter(None, [theme, batch_id])))
    branch_slug = branch_slug or normalized_batch_id or "batch"
    return {
        "schemaVersion": 1,
        "batchID": batch_id,
        "theme": theme,
        "status": "review-batch-needs-human-approval",
        "policy": {
            "prCadence": "one pull request per curation turn/batch, whether that batch contains one animal or several",
            "publishOnApprovedMerge": True,
            "githubSourceOfTruth": True,
            "cloudflareDeliveryOnly": True,
        },
        "branchName": f"catalog/{branch_slug}",
        "prTitle": f"Catalog batch: {theme or 'mixed'} ({len(normalized)} animal{'s' if len(normalized) != 1 else ''})",
        "animalReviews": animal_reviews,
        "packArtifact": pack_path or latest_matching_file(root, [f"review/pack-*{norm(theme)}*.json"] if theme else ["review/pack-*.json"]),
        "mergeGates": [
            "python3 scripts/catalog.py validate --mode expansion",
            "python3 scripts/catalog.py validate --mode publish",
            "human reviewer checks every requiredApprovals item for each animal",
            "approved PR merge to main triggers live catalog build/publish workflow",
        ],
        "suggestedGhCommands": [
            f"git switch -c catalog/{branch_slug}",
            "git add animals packs review assets indexes README.md docs scripts policy .github",
            f"git commit -m \"Add catalog batch: {theme or 'mixed'}\"",
            f"gh pr create --draft --title \"Catalog batch: {theme or 'mixed'} ({len(normalized)} animal{'s' if len(normalized) != 1 else ''})\" --body-file review/batches/{batch_id}-pr-body.md",
        ],
    }


def review_batch_pr_body(batch: Json) -> str:
    rows = []
    for item in batch.get("animalReviews", []):
        rows.append(f"| `{item['candidate']}` | {item.get('copyArtifact') or 'missing'} | {item.get('mediaBrief') or 'missing'} | {item.get('contactSheet') or 'missing'} | {item.get('downloadedMediaCount') or 0} |")
    table = "\n".join(rows) or "| _none_ | | | | |"
    gates = "\n".join(f"- [ ] `{gate}`" if gate.startswith("python3 ") else f"- [ ] {gate}" for gate in batch.get("mergeGates", []))
    return f"""# {batch.get('prTitle')}

Review batch: `{batch.get('batchID')}`  
Theme: `{batch.get('theme') or 'mixed'}`  
Status: `{batch.get('status')}`

## Candidate artifacts

| Candidate | Copy artifact | Media brief | Contact sheet | Downloads |
|---|---|---|---|---:|
{table}

Pack artifact: `{batch.get('packArtifact') or 'none'}`

## Merge gates

{gates}

## Publish policy

- [ ] This PR only changes source-of-truth catalog/review artifacts.
- [ ] Approval confirms these animals should become live after merge.
- [ ] Merging an approved PR to `main` triggers the live catalog build/publish workflow.
"""


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    errors, warnings = validate_common(root, args.mode, args.source_app_repo, args.allow_staging)
    for w in warnings:
        print("WARN:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print(f"❌ Catalog validation failed ({args.mode}): {len(errors)} errors, {len(warnings)} warnings")
        return 1
    print(f"✅ Catalog validation passed ({args.mode}): {len(warnings)} warnings")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    animals = load_animals(root)
    packs = load_packs(root)
    tax = Counter(a.get("tags", {}).get("taxonomy", "unknown") for a in animals)
    habitats = Counter(h for a in animals for h in a.get("tags", {}).get("habitats", []))
    hooks = Counter(h for a in animals for h in a.get("tags", {}).get("hookArchetypes", []))
    print(f"Animals: {len(animals)}")
    print(f"Packs: {len(packs)}")
    print("Taxonomy:", dict(sorted(tax.items())))
    print("Top habitats:", dict(habitats.most_common(10)))
    print("Top hooks:", dict(hooks.most_common(10)))
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    animals = load_animals(root)
    policy_path = root / "policy/balance-policy.json"
    if not policy_path.exists():
        print("missing policy/balance-policy.json")
        return 1
    policy = read_json(policy_path)
    total = max(1, len(animals))
    tax = Counter(a.get("tags", {}).get("taxonomy", "unknown") for a in animals)
    habitats = Counter(h for a in animals for h in a.get("tags", {}).get("habitats", []))
    print("Taxonomy gaps vs target:")
    for key, target in policy.get("globalTargets", {}).get("taxonomy", {}).items():
        actual = tax.get(key, 0) / total
        print(f"- {key}: actual={actual:.3f} target={target:.3f} gap={target-actual:+.3f}")
    print("Habitat gaps vs target:")
    for key, target in policy.get("globalTargets", {}).get("habitat", {}).items():
        actual = habitats.get(key, 0) / total
        print(f"- {key}: actual={actual:.3f} target={target:.3f} gap={target-actual:+.3f}")
    return 0


def maybe_write(args: argparse.Namespace, payload: Json, default_name: str) -> None:
    if not getattr(args, "write", None):
        display_json(payload)
        return
    out = Path(args.write)
    if out.is_dir() or str(args.write).endswith("/"):
        out = out / default_name
    write_json(out, payload)
    print(f"wrote {out}")


def cmd_discover(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    payload = discover_candidates(root, args.theme, args.count, args.include_duplicates, source=args.source, offline=args.offline)
    maybe_write(args, payload, f"discover-{norm(args.theme)}.json")
    return 0


def cmd_media(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    payload = media_brief(root, args.candidate, download=args.download, download_limit=args.download_limit, max_bytes=args.max_bytes)
    maybe_write(args, payload, f"media-{norm(args.candidate)}.json")
    return 0 if payload.get("status") != "missing" else 1


def cmd_draft_copy(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    payload = draft_copy(root, args.candidate, args.allow_existing)
    maybe_write(args, payload, f"copy-{norm(args.candidate)}.json")
    return 0 if payload.get("status") != "missing" else 1


def cmd_assemble_pack(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    payload = assemble_pack(root, args.theme, args.size, source=args.source, offline=args.offline)
    maybe_write(args, payload, f"pack-draft-{norm(args.theme)}.json")
    return 0


def cmd_review_batch(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    payload = review_batch(root, args.id, args.theme, args.candidates, args.pack)
    out_dir = Path(args.write or (root / "review" / "batches"))
    if out_dir.suffix:
        batch_path = out_dir
        out_dir = out_dir.parent
    else:
        batch_path = out_dir / f"{args.id}.json"
    write_json(batch_path, payload)
    pr_body_path = out_dir / f"{args.id}-pr-body.md"
    pr_body_path.parent.mkdir(parents=True, exist_ok=True)
    pr_body_path.write_text(review_batch_pr_body(payload))
    print(f"wrote {batch_path}")
    print(f"wrote {pr_body_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AnimalSwipe catalog CLI: validate baseline content, inspect balance gaps, and create local review drafts for future animals.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--root", default=".", help="catalog repo root")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate catalog structure and artifacts")
    v.add_argument("--mode", choices=["baseline", "expansion", "publish"], default="baseline")
    v.add_argument("--source-app-repo")
    v.add_argument("--allow-staging", action="store_true", help="permit unsigned staging latest.json during Phase 0/2 dry runs")
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("summarize", help="summarize current catalog counts and tags")
    s.set_defaults(func=cmd_summarize)

    g = sub.add_parser("gaps", help="show taxonomy and habitat gaps against policy targets")
    g.set_defaults(func=cmd_gaps)

    discover_help = """
    Discover candidate animals from trusted structured sources without modifying the catalog.

    The command always reads animals/*.json and packs/*.json first. In live mode
    it queries the Wikidata API, enriches candidates with Wikidata entity data,
    and can fall back to the curated local seed queue if the network/source is
    sparse. Exact ID, common-name, and scientific-name duplicates are filtered
    by default. Scoring includes every Phase 1 term from the plan:

      score = balance_gap_score
            + novelty_gap_score
            + kid_recognition_score
            + visual_distinctiveness_score
            + source_quality_score
            + image_availability_score
            + theme_bonus
            - duplicate_similarity_penalty
            - recent_drop_similarity_penalty
            - overrepresented_habitat_penalty
            - scary_or_gory_risk_penalty
            - licensing_complexity_penalty

    Output is a ranked review queue with external IDs and source diagnostics.
    It is not approved content and it does not create animal files, download
    images, call an LLM, or publish anything.

    Examples:
      python3 scripts/catalog.py discover --theme forest --count 50
      python3 scripts/catalog.py discover --theme wetland --count 20 --write review/discover-wetland.json
      python3 scripts/catalog.py discover --theme forest --source live
      python3 scripts/catalog.py discover --theme forest --source local --offline
    """
    d = sub.add_parser(
        "discover",
        help="rank future animal candidates for a theme",
        description=textwrap.dedent(discover_help),
        epilog="Next steps: run media and draft-copy for selected candidate IDs, then assemble-pack for a proposed drop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    d.add_argument("--theme", required=True, help="theme or gap to optimize for, e.g. forest, wetland, ocean, night")
    d.add_argument("--count", type=int, default=50, help="maximum candidates to return")
    d.add_argument("--source", choices=["live", "local", "auto"], default="live", help="candidate source mode: Wikidata/API first, local curated queue, or both")
    d.add_argument("--offline", action="store_true", help="disable network calls and use only local/fallback candidates")
    d.add_argument("--include-duplicates", action="store_true", help="include candidates that duplicate existing catalog IDs/names/species with a penalty")
    d.add_argument("--write", help="write JSON output to a file or directory instead of stdout")
    d.set_defaults(func=cmd_discover)

    media_help = """
    Create a license-aware media research brief for a candidate.

    By default this queries Wikimedia Commons metadata only. Add --download to
    fetch a small capped set of license-allowed original files into
    review/media/<candidate>/originals/, hash them, and generate a local HTML
    contact sheet. Downloaded files are review artifacts only: the command does
    not approve media, add animals, or publish content.
    """
    m = sub.add_parser(
        "media",
        help="create a license-aware media research brief for a candidate",
        description=textwrap.dedent(media_help),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    m.add_argument("--candidate", required=True, help="candidate ID or existing animal ID, e.g. red-fox")
    m.add_argument("--download", action="store_true", help="download allowed Commons originals into review/media/<candidate>/ and create a contact sheet")
    m.add_argument("--download-limit", type=int, default=3, help="maximum original files to download when --download is set")
    m.add_argument("--max-bytes", type=int, default=25_000_000, help="maximum bytes per downloaded original")
    m.add_argument("--write", help="write JSON output to a file or directory instead of stdout")
    m.set_defaults(func=cmd_media)

    c = sub.add_parser("draft-copy", help="create kid-safe draft copy artifact from local candidate facts")
    c.add_argument("--candidate", required=True, help="candidate ID or existing animal ID, e.g. red-fox")
    c.add_argument("--allow-existing", action="store_true", help="allow draft output for an animal already in the migrated baseline")
    c.add_argument("--write", help="write JSON output to a file or directory instead of stdout")
    c.set_defaults(func=cmd_draft_copy)

    a = sub.add_parser("assemble-pack", help="assemble a balanced draft pack from discovered candidates")
    a.add_argument("--theme", required=True, help="theme to optimize for, e.g. forest")
    a.add_argument("--size", type=int, default=10, help="number of animals in the draft pack")
    a.add_argument("--source", choices=["live", "local", "auto"], default="live", help="candidate source mode for pack assembly")
    a.add_argument("--offline", action="store_true", help="disable network calls and use local/fallback candidates")
    a.add_argument("--write", help="write JSON output to a file or directory instead of stdout")
    a.set_defaults(func=cmd_assemble_pack)

    rb_help = """
    Create a PR-ready review batch packet for one curation turn.

    Use this after discover/media/draft-copy/assemble-pack and before making a
    GitHub PR. The packet lists every candidate, known review artifacts,
    required human approval checks, validation gates, a suggested branch name,
    and a generated PR body. It does not approve animals or modify catalog
    source records.
    """
    rb = sub.add_parser(
        "review-batch",
        help="create a PR-ready review/approval packet for a batch of candidates",
        description=textwrap.dedent(rb_help),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rb.add_argument("--id", required=True, help="stable batch ID, e.g. forest-2026-05-31")
    rb.add_argument("--theme", help="batch theme, e.g. forest")
    rb.add_argument("--candidate", dest="candidates", action="append", required=True, help="candidate ID to include; repeat for multiple animals")
    rb.add_argument("--pack", help="optional pack draft artifact path")
    rb.add_argument("--write", help="output directory or JSON path; defaults to review/batches/")
    rb.set_defaults(func=cmd_review_batch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
