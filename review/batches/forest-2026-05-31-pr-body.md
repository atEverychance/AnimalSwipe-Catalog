# Catalog batch: forest (1 animal)

Review batch: `forest-2026-05-31`  
Theme: `forest`  
Status: `review-batch-needs-human-approval`

## Candidate artifacts

| Candidate | Copy artifact | Media brief | Contact sheet | Downloads |
|---|---|---|---|---:|
| `pine-marten` | review/copy-pine-marten.json | review/media-pine-marten.json | review/media/pine-marten/contact-sheet.html | 2 |

Pack artifact: `review/pack-forest-live.json`

## Merge gates

- [ ] `python3 scripts/catalog.py validate --mode expansion`
- [ ] `python3 scripts/catalog.py validate --mode publish`
- [ ] human reviewer checks every requiredApprovals item for each animal
- [ ] approved PR merge to main triggers live catalog build/publish workflow

## Publish policy

- [ ] This PR only changes source-of-truth catalog/review artifacts.
- [ ] Approval confirms these animals should become live after merge.
- [ ] Merging an approved PR to `main` triggers the live catalog build/publish workflow.
