# Review and approval workflow

Use **one GitHub pull request per curation turn/batch**. A batch can contain one animal or several animals discovered and reviewed in the same turn. Do not open one PR per animal unless only one animal is ready.

## Why batch PRs

- Keeps review atomic: candidate records, media, copy, pack changes, and audit artifacts land together.
- Makes human approval explicit without requiring a CMS.
- Avoids noisy one-animal PR churn while keeping batches small enough to review carefully.
- Preserves GitHub as the editorial source of truth; Cloudflare remains delivery-only.

## Batch states

1. **Candidate** — `discover`, `media`, `draft-copy`, and `assemble-pack` artifacts exist under `review/`; no catalog source record is approved yet.
2. **Review PR** — one branch/PR contains all source and review artifacts for that turn.
3. **Approved/Merged** — human checklist passes and the PR merges into the catalog repo.
4. **Live publish** — once an approved PR is merged to `main`, GitHub Actions builds, signs, and uploads the live catalog so those animals become part of the remote library.

## Recommended turn loop

```bash
python3 scripts/catalog.py discover --theme forest --count 20 --source live --write review/discover-forest-live.json
python3 scripts/catalog.py media --candidate pine-marten --download --download-limit 3 --write review/media-pine-marten.json
python3 scripts/catalog.py draft-copy --candidate pine-marten --write review/copy-pine-marten.json
python3 scripts/catalog.py assemble-pack --theme forest --size 10 --source live --write review/pack-forest-live.json
python3 scripts/catalog.py review-batch --id forest-YYYY-MM-DD --theme forest --candidate pine-marten
```

`review-batch` writes:

- `review/batches/<id>.json` — machine-readable approval packet.
- `review/batches/<id>-pr-body.md` — PR body/checklist for `gh pr create --body-file`.

## Branch and PR convention

- Branch: `catalog/<theme>-<batch-id>`
- PR title: `Catalog batch: <theme> (<n> animals)`
- PR scope: all animals added in that turn, their media/copy review artifacts, and any pack/index changes.

Example:

```bash
git switch -c catalog/forest-YYYY-MM-DD
git add animals packs review assets indexes README.md docs scripts policy .github
git commit -m "Add catalog batch: forest"
gh pr create --draft --title "Catalog batch: forest (3 animals)" --body-file review/batches/forest-YYYY-MM-DD-pr-body.md
```

## Required human checks per animal

- Species identity matches source URLs and scientific name.
- Image is kid-safe: no gore, distress, watermark, misleading crop, or clutter that makes the animal hard to see.
- License is allowed by `policy/license-policy.json`; attribution name, license URL, and source URL are captured.
- Copy is factual, age-appropriate, and backed by source facts.
- Tags and pack inclusion do not worsen catalog balance in a way the reviewer rejects.

## Merge gates

```bash
python3 scripts/catalog.py validate --mode expansion
python3 scripts/catalog.py validate --mode publish
```

## Live publish trigger

The private GitHub repo has a live publish workflow at `.github/workflows/live-catalog.yml`.

- Trigger: a PR targeting `main` is closed as merged, or a manual `workflow_dispatch` run.
- Guard: for PR-triggered runs, the workflow refuses to publish unless the merged PR has at least one `APPROVED` review.
- Build: `scripts/build_catalog.py` generates a fresh versioned catalog from the merged source files.
- Sign: `scripts/prepare_signed_manifest.py --channel production` creates a live `dist/latest.json` with `stagingOnly: false`.
- Publish: `scripts/cloudflare_upload.py` uploads catalog artifacts and available source assets to `animalswipe-catalog-prod`, then deploys the production Worker.

Required GitHub secrets:

- `CATALOG_SIGNING_KEY_P256` — already set from the local signing key.
- `CLOUDFLARE_ACCOUNT_ID` — already set.
- `CLOUDFLARE_API_TOKEN` — still required before the first live publish can complete.

GitHub branch protection for private repos is unavailable on the current plan, so the workflow itself enforces the approval requirement before deployment.
