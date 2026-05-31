# Cloudflare staging setup

Wrangler is authenticated locally with OAuth. No API token is required for local setup.

## Current target names

- Account email: `ai@everychance.ca`
- Account ID: `cff4d411f5dadab48c92e2c2a6be049d`
- workers.dev subdomain: `everychance-ai.workers.dev`
- Staging Worker: `animalswipe-catalog-staging`
- Staging Worker URL: `https://animalswipe-catalog-staging.everychance-ai.workers.dev`
- Staging R2 bucket: `animalswipe-catalog-staging`
- Production Worker: `animalswipe-catalog`
- Production Worker URL: `https://animalswipe-catalog.everychance-ai.workers.dev`
- Production R2 bucket: `animalswipe-catalog-prod`

## Current status

Completed:

```bash
wrangler r2 bucket create animalswipe-catalog-staging
python3 scripts/prepare_signed_manifest.py --source-app-repo ../AnimalSwipe --version 1
python3 scripts/catalog.py validate --mode publish
python3 scripts/cloudflare_upload.py --bucket animalswipe-catalog-staging --version 1 --source-app-repo ../AnimalSwipe --include-assets
wrangler deploy --env staging
```

Results:

- R2 bucket exists: `animalswipe-catalog-staging`.
- 203 objects uploaded: `latest.json`, `catalog/catalog-v0001.json`, `catalog/assets-manifest-v0001.json`, and 200 `assets/*.jpg` files.
- R2 round-trip verification passed for `latest.json`, `catalog/catalog-v0001.json`, and sample asset `assets/tiger.jpg`.
- workers.dev subdomain registered: `everychance-ai`.
- Staging Worker deployed at `https://animalswipe-catalog-staging.everychance-ai.workers.dev`.
- HTTPS verification passed for `/health`, `/latest.json`, `/catalog/catalog-v0001.json`, and sample `/assets/tiger.jpg`.
- Worker version deployed: `a1ce85ff-0d3e-4093-8fbb-df8a7172c45c`.
- GitHub repo visibility is public: `https://github.com/atEverychance/AnimalSwipe-Catalog`.
- `main` branch protection is enabled with one required approving PR review and conversation resolution.
- Live GitHub Actions workflow is active: `.github/workflows/live-catalog.yml`.

## Verification commands

```bash
BASE=https://animalswipe-catalog-staging.everychance-ai.workers.dev
curl "$BASE/health"
curl "$BASE/latest.json"
curl "$BASE/catalog/catalog-v0001.json"
curl -I "$BASE/assets/tiger.jpg"
python3 scripts/catalog.py validate --mode baseline --source-app-repo ../AnimalSwipe
python3 scripts/catalog.py validate --mode expansion
python3 scripts/catalog.py validate --mode publish
```

## Signing keys

`prepare_signed_manifest.py` creates the private P-256 key at:

```text
~/.animalswipe/catalog-signing-key-p256.pem
```

That file must stay out of Git. The public key is exported to `keys/catalog-public-key-p256.pem` for future iOS verification.

## Current delivery decisions

- Production/staging delivery can use the workers.dev domain for now; a custom `catalog.animalswipe.app` route is optional later.
- GitHub is the source-of-truth for everything editorial/curatorial: catalog records, review history, scripts, prompts, policies, source originals, generated audit artifacts, and public verification keys.
- Cloudflare is delivery-only: signed generated manifests and optimized runtime assets are uploaded to R2 and served by Workers.

## Remaining production decisions

- Whether large source originals require Git LFS once new source images are added; default to plain Git until file sizes or repo growth justify LFS.
- Approved PR merge to `main` is the live approval gate. The GitHub Actions workflow builds/signs/uploads the live catalog after verifying the merged PR had at least one approving review. The remaining setup need is adding the `CLOUDFLARE_API_TOKEN` GitHub secret.

## GitHub Actions Cloudflare token

Required repo secrets:

- `CATALOG_SIGNING_KEY_P256` — set.
- `CLOUDFLARE_ACCOUNT_ID` — set.
- `CLOUDFLARE_API_TOKEN` — not set yet.

Cloudflare does not allow creating this deploy token from the current Wrangler OAuth login. API-created tokens require an initial dashboard-created token with `API Tokens Write`, and the current OAuth token only has Wrangler deployment scopes. Create a scoped token in the Cloudflare dashboard with Account permissions: `Account Settings: Read`, `Workers Scripts: Edit`, and `Workers R2 Storage: Edit`, then install it with:

```bash
printf '<token>' | gh secret set CLOUDFLARE_API_TOKEN --repo atEverychance/AnimalSwipe-Catalog
```
