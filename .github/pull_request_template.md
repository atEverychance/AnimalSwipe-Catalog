# Catalog batch

## Scope

- Theme/batch:
- Animals added or changed:
- Pack(s) touched:

## Review artifacts

- [ ] `review/batches/<id>.json`
- [ ] `review/batches/<id>-pr-body.md`
- [ ] Media contact sheet(s)
- [ ] Copy/source artifact(s)

## Per-animal approval

For every animal in this PR:

- [ ] Species identity confirmed from source URLs/scientific name.
- [ ] Image is kid-safe and visually suitable.
- [ ] License, attribution name, license URL, and source URL verified.
- [ ] Copy is factual, age-appropriate, and source-backed.
- [ ] Tags/pack placement reviewed for balance.

## Validation

- [ ] `python3 scripts/catalog.py validate --mode expansion`
- [ ] `python3 scripts/catalog.py validate --mode publish`

## Live publish policy

- [ ] Approval means these animals should become live after merge.
- [ ] Merging this approved PR to `main` triggers `.github/workflows/live-catalog.yml`.
