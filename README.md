# AnimalSwipe Catalog

Source-of-truth workspace for AnimalSwipe remote catalog content and automation.
GitHub is the intended home for curated catalog source, scripts, prompts, policies,
source originals, review artifacts, generated audit history, and public verification
keys. Cloudflare remains delivery-only for signed manifests and optimized runtime
assets; the workers.dev staging URL is acceptable for now.

Current milestone: Phase 0 migration baseline. The first generated catalog version (`v0001`) is a one-file-per-animal migration of the existing AnimalSwipe bundled library. No new animals should be added until baseline equivalence passes.

## Fast loop

```bash
python3 scripts/migrate_existing.py --source-app-repo ../AnimalSwipe --output . --version 1
python3 scripts/catalog.py validate --mode baseline --source-app-repo ../AnimalSwipe
python3 scripts/catalog.py validate --mode expansion
python3 scripts/catalog.py validate --mode publish --allow-staging
python3 scripts/catalog.py summarize
python3 scripts/catalog.py gaps
python3 scripts/catalog.py discover --theme forest --count 50 --source live
python3 scripts/catalog.py media --candidate red-fox
python3 scripts/catalog.py media --candidate pine-marten --download --download-limit 3 --write review/media-pine-marten.json
python3 scripts/catalog.py draft-copy --candidate red-fox
python3 scripts/catalog.py assemble-pack --theme forest --size 10 --source live
python3 scripts/catalog.py review-batch --id forest-YYYY-MM-DD --theme forest --candidate pine-marten
```

For the discovery scoring contract and examples:

```bash
python3 scripts/catalog.py discover --help
```


## Phase 0 status

`v0001` is a staging baseline generated from the bundled AnimalSwipe app content. It intentionally has `stagingOnly: true` and unsigned asset/hash fields; true `publish` validation without `--allow-staging` remains blocked until Phase 2 signing and asset hashing are implemented.

Generated baseline artifacts:

- `animals/{id}.json` — 200 migrated animal records with proposed inline tags marked `needsTagReview`.
- `packs/{id}.json` — 20 migrated pack records with original animal order preserved.
- `rewards/rewards.json` — copied reward configuration.
- `encyclopedia/encyclopedia.json` — copied existing sidecar encyclopedia content.
- `indexes/duplicate-index.json`
- `indexes/balance-baseline.json`
- `indexes/migration-report.json`
- `dist/catalog-v0001.json`
- `dist/latest.json`


## Cloudflare staging

Local Cloudflare scaffolding exists for Phase 2:

```bash
python3 scripts/prepare_signed_manifest.py --source-app-repo ../AnimalSwipe --version 1
python3 scripts/catalog.py validate --mode publish
python3 scripts/cloudflare_upload.py --bucket animalswipe-catalog-staging --version 1 --source-app-repo ../AnimalSwipe --include-assets --dry-run
wrangler deploy --env staging --dry-run
```

R2 must be enabled once in the Cloudflare dashboard before `wrangler r2 bucket create animalswipe-catalog-staging` and real uploads can succeed. See `docs/cloudflare-setup.md`.

## Phase 1 local CLI status

The CLI now has the local review-draft commands from the automation plan:

- `summarize` — current catalog counts and tag distribution.
- `gaps` — taxonomy and habitat gaps against `policy/balance-policy.json`.
- `discover` — reads the migrated catalog first, queries Wikidata as a trusted structured source in `--source live` mode, filters exact duplicates by default, scores balance/novelty/safety/licensing terms, and emits a ranked review queue with external IDs/source diagnostics.
- `media` — queries Wikimedia Commons metadata for candidate image options, license fields, dimensions, source URLs, and human-review flags; with `--download`, fetches a capped set of license-allowed originals into `review/media/<candidate>/`, hashes them, and writes a local contact sheet; existing migrated animals are treated as duplicates and skipped by default.
- `draft-copy` — creates a rule-based kid-safe draft artifact from source facts/Wikipedia summary data; marked human-review-only and never publishable directly.
- `assemble-pack` — balanced draft pack proposal from discovered candidates, without writing animal files.
- `review-batch` — creates a PR-ready approval packet and PR body for one curation turn/batch.

These commands do not add animals, call an LLM, or publish remote content unless a future command explicitly does so. Downloaded media remains a review artifact until a human approves identity, kid-safety, crop suitability, and attribution.

## Review and PR cadence

Use one GitHub pull request per curation turn/batch. A batch can contain one animal or multiple animals that were discovered, reviewed, and assembled together in that turn. The PR should include the animal source records, media/copy review artifacts, pack/index updates, and the generated `review/batches/<id>-pr-body.md` checklist. Once that PR has an approving review and is merged to `main`, `.github/workflows/live-catalog.yml` builds, signs, and publishes the live remote catalog so those animals are included in the library.

See `docs/review-approval-workflow.md`.
