# Public Audit Results - <YYYY-MM>

**Artifacts**
- Winners: `https://audit.loyaltydraw.com/<YYYY-MM>/winners.json`
- Snapshot: `https://audit.loyaltydraw.com/<YYYY-MM>/snapshot.csv`

**Commands used**
`python3 audit.py --period <YYYY-MM> --base https://audit.loyaltydraw.com --level all --on-missing-seed skip`

**Summary**
- Level 1 (snapshot integrity): ✅ match
- Level 2 (structure & coherence): ✅ ok
- Level 3 (reproduce winners): ✅ ok / ⏭️ skipped (seed not revealed yet)

**Notes**
- Seed commitment: `<seed_commit_hex>`
- Seed reveal: `<revealed_at or pending>`