# AnimalSwipe Catalog

Source-of-truth workspace for AnimalSwipe remote catalog content and automation.

Current milestone: Phase 0 migration baseline. The first generated catalog version (`v0001`) is a one-file-per-animal migration of the existing AnimalSwipe bundled library. No new animals should be added until baseline equivalence passes.

## Fast loop

```bash
python3 scripts/migrate_existing.py --source-app-repo ../AnimalSwipe --output . --version 1
python3 scripts/catalog.py validate --mode baseline --source-app-repo ../AnimalSwipe
python3 scripts/catalog.py validate --mode expansion
python3 scripts/catalog.py validate --mode publish --allow-staging
python3 scripts/catalog.py summarize
python3 scripts/catalog.py gaps
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
