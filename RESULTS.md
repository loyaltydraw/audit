# Public Audit Results - `<YYYY-MM>`

## Artifacts
- Winners:  https://audit.loyaltydraw.com/<`<YYYY-MM>`>/winners.json
- Snapshot: https://audit.loyaltydraw.com/<`<YYYY-MM>`>/snapshot.csv

## Command used
`python3 audit.py --period <YYYY-MM> --base https://audit.loyaltydraw.com --level all --on-missing-seed skip`

## Summary
- Level 1 - snapshot integrity: ✅ match
- Level 2 - structure & coherence: ✅ ok (canonical CSV-bytes hash match)
- Level 3 - reproduce winners: ✅ ok  /  ⏭️ skipped (seed not revealed)

## Details

### Level 1
- expected hash: `<winners.json.snapshot_hash_hex>`
- computed hash: `<blake2b256(snapshot.csv)>`
- result: ✅ match / ❌ mismatch

### Level 2
- rows (users): `<N_users>`
- totals: `users=<N_users> entries=<sum(weights)>` - `<match/nomatch> winners.json.totals`
- ordering: `<canonical / not canonical>`
- canonical CSV-bytes hash: `<match / mismatch>`

### Level 3 (post-reveal)
- seed commit: `<commit.seed_commit_hex>`
- seed revealed at: `<commit.revealed_at or 'pending'>`
- seed hex (short): `<ab12…9f01>` (only after reveal)
- k_primary: `<111>`
- k_alternates: `<222>`
- comparison: `<aliases match / first diff at index i: computed=… published=…>`

## Notes
- Any discrepancies: `<brief note or ‘none’>`
