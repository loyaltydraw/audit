# Loyalty Draw - Public Audit Kit

Verify any Loyalty Draw period using the public artifacts at:

- Winners (JSON): `https://audit.loyaltydraw.com/<YYYY-MM>/winners.json`
- Snapshot (CSV): `https://audit.loyaltydraw.com/<YYYY-MM>/snapshot.csv`

This kit lets anyone confirm:

- **Level 1 – Snapshot integrity (pre-reveal)**  
  The published `snapshot.csv` is exactly the one used to run the draw.
- **Level 2 – Structural & internal coherence**  
  The snapshot is well-formed (ordering, types, totals) and its **canonical snapshot hash** matches what the draw reported.
- **Level 3 – Reproduce winners (post-reveal)**  
  Once the seed is revealed in `winners.json`, recompute the winners and compare to the published winners.

> No third-party packages. Requires **Python 3.10+** only.

---

## Quick start (copy/paste)

```bash
git clone https://github.com/loyaltydraw/audit.git
cd audit
python3 audit.py --period 2025-07 --base https://audit.loyaltydraw.com
```

- If the seed has **not** been revealed yet, Level 1 & Level 2 run; Level 3 is skipped (or warned).
- If the seed **has** been revealed, Levels 1, 2 **and** 3 run.

**Windows**: use python instead of python3.

---

## No internet? Use local files

Download the two files (same folder):
```
./winners.json
./snapshot.csv
```

Run:
```
python3 audit.py --winners ./winners.json --snapshot ./snapshot.csv
```

(You can also mix: one local, one URL.)

---

## What each level checks

**Level 1 - Snapshot integrity (pre-reveal)**

- Compute **BLAKE2b-256** of the raw `snapshot.csv` bytes.
- Compare to `winners.json.snapshot_hash_hex`.
- ✅ **Match = the draw used exactly that snapshot**.

**Level 2 - Structural & internal coherence**

- Parse `snapshot.csv` (`shard,user_id,weight`) and verify:
  - Shards are non-decreasing (0..buckets-1) and users within a shard are ascending (canonical ordering).
  - No negative weights; types are correct.
  - Totals (`users`, `entries`) equal `winners.json.totals`.
- Recompute the **canonical snapshot hash** from the parsed records and confirm it equals `winners.json.snapshot_hash_hex`.

**Level 3 - Reproduce winners (post-reveal)**

- Use `winners.json.commit.seed_hex` (revealed seed).
- Recompute scores via **Efraimidis–Spirakis** weighted sampling *without replacement*:
  ```
  For each entrant (user_id, weight, shard):
    u = BLAKE2b-256( "derive_u|ver:1|" + seed
                     + "|period:" + PERIOD
                     + "|shard:"  + SHARD
                     + "|user:"   + USER_ID )
    score = -ln(u) / weight
  Keep K = k_primary + k_alternates smallest scores (best first).
  ```
- Convert full IDs from the snapshot to **display aliases** for comparison:
  ```
  alias = first8 + "…" + last4     # e.g., c0ffee12…9f0e
  ```
- Compare recomputed aliases with ```winners_primary``` + ```winners_alternates```.

---

## Typical output

**Before seed reveal**

```
== LoyaltyDraw Audit ==
Mode           : URL
Period         : 2025-07
Base           : https://audit.loyaltydraw.com

[Level 1] Snapshot integrity
  expected     : e3fd…7a21
  computed     : e3fd…7a21
  result       : ✅ MATCH

[Level 2] Structure & coherence
  rows         : 18,234
  totals       : users=18,234 entries=47,901  ✅ match winners.json
  ordering     : ✅ canonical
  hash         : ✅ canonical snapshot hash matches

[Level 3] Reproduce winners
  status       : ⏭️  skipped - seed not revealed yet
```

**After seed reveal**

```
[Level 3] Reproduce winners
  seed_hex     : ab12cd34…9f01eeff
  k_primary    : 111
  k_alternates : 235
  compare      : ✅ aliases match
```

If something doesn’t match, the tool prints the first few differences.

---

## Command reference 

```
python3 audit.py \
  --period 2025-07 \
  --base https://audit.loyaltydraw.com \
  --level all            # all | 1 | 2 | 3   (default: all)
  --on-missing-seed skip # error | skip | warn   (default: skip)
  --winners <path-or-url>
  --snapshot <path-or-url>
  --quiet                # less verbose
```
- Use either ```--base + --period``` or explicit ```--winners/--snapshot```.
- ```--on-missing-seed``` controls Level 3 when the seed hasn’t been revealed yet.

---

## Make targets (optional)

```
make verify    PERIOD=2025-07 BASE=https://audit.loyaltydraw.com   # Levels 1 + 2
make reproduce PERIOD=2025-07 BASE=https://audit.loyaltydraw.com   # Level 3 (requires seed)
make audit     PERIOD=2025-07 BASE=https://audit.loyaltydraw.com   # Levels 1 + 2 + 3 (L3 skipped if no seed)
```

---

## GitHub Actions (optional)

Manual workflow in `.github/workflows/audit.yml`:
- Inputs: `period` (e.g., 2025-07), `base` (default `https://audit.loyaltydraw.com`)
- Runs: `python3 audit.py --period $period --base $base --level all --on-missing-seed skip`

---

## Privacy notes 

- Public winners show **display aliases** only (first8…last4).
- Full IDs remain in `snapshot.csv` (to enable re-computation) and in our internal ledger.
- Aliases are **not linkable across months**.

--- 

## Troubleshooting

- "**snapshot hash mismatch**"
  Hard refresh / re-download, confirm the period path. If mismatch persists, file an issue with both files attached.
- "**seed not revealed**"
  Level 3 skips (or warns) until the reveal step updates `winners.json.commit.seed_hex`.
- "**python not found**"
  Install Python 3.10+ from python.org. On macOS/Linux use `python3`; on Windows use `python`.


