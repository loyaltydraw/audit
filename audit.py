#!/usr/bin/env python3
"""
LoyaltyDraw public audit tool (Levels 1, 2, 3)

- Level 1: Snapshot integrity
    Hash raw snapshot.csv (BLAKE2b-256) and compare to winners.json.snapshot_hash_hex.

- Level 2: Structural & internal coherence
    Parse snapshot.csv (shard,user_id,weight) and verify:
      * canonical ordering (shard asc; within shard user_id asc)
      * no negative weights; integers are valid
      * totals match winners.json.totals
      * canonical snapshot hash computed from rows equals winners.json.snapshot_hash_hex

- Level 3: Reproduce winners (post-reveal)
    If commit.seed_hex is available, recompute winners using Efraimidis–Spirakis
    weighted sampling without replacement and compare display aliases to published ones.

Standard library only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import hashlib
from typing import Iterable, List, Tuple, Dict, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# ------------- Helpers (IO) ------------- #

def is_url(s: str) -> bool:
    try:
        p = urlparse(s)
        return p.scheme in ("http", "https")
    except Exception:
        return False

def read_bytes(path_or_url: str, timeout: float = 30.0) -> bytes:
    if is_url(path_or_url):
        req = Request(path_or_url, headers={"User-Agent": "LoyaltyDraw-Audit/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    else:
        with open(path_or_url, "rb") as f:
            return f.read()

def load_json(path_or_url: str) -> dict:
    data = read_bytes(path_or_url)
    return json.loads(data.decode("utf-8"))

# ------------- Helpers (format) ------------- #

def blake2b_hex(data: bytes, digest_size: int = 32) -> str:
    h = hashlib.blake2b(digest_size=digest_size)
    h.update(data)
    return h.hexdigest()

def display_alias(uuid_like: str) -> str:
    s = str(uuid_like).replace("-", "").lower()
    if len(s) < 12:
        return s
    return f"{s[:8]}…{s[-4:]}"

def format_short_hex(hx: str) -> str:
    hx = (hx or "").lower()
    if len(hx) <= 16:
        return hx
    return f"{hx[:4]}…{hx[-4:]}"

# ------------- Snapshot parsing & validation ------------- #

Row = Tuple[int, str, int]  # (shard, user_id, weight)

def parse_snapshot_csv(raw: bytes) -> List[Row]:
    text = raw.decode("utf-8")
    rdr = csv.DictReader(io.StringIO(text))
    headers = set(rdr.fieldnames or [])
    required = {"shard", "user_id", "weight"}
    if not required.issubset(headers):
        raise ValueError("snapshot.csv must contain columns: shard,user_id,weight")
    rows: List[Row] = []
    for i, rec in enumerate(rdr, start=2):
        try:
            shard = int(rec["shard"])
            user_id = str(rec["user_id"])
            weight = int(rec["weight"])
        except Exception as e:
            raise ValueError(f"invalid row at csv line {i}: {e}")
        rows.append((shard, user_id, weight))
    return rows

def compute_canonical_snapshot_hash(period: str, rows: Iterable[Row]) -> str:
    h = hashlib.blake2b(digest_size=32)
    h.update(b"snapshot|ver:1|period:")
    h.update(period.encode("utf-8"))
    for shard, user_id, weight in rows:
        h.update(b"|shard:"); h.update(str(shard).encode("utf-8"))
        h.update(b"|user:");  h.update(str(user_id).encode("utf-8"))
        h.update(b"|w:");     h.update(str(weight).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()

def validate_canonical_order(rows: List[Row]) -> Tuple[bool, Optional[str]]:
    """Ensure shards are non-decreasing, and within each shard user_id is ascending."""
    last_shard = None
    last_user = None
    for idx, (shard, user, weight) in enumerate(rows):
        if last_shard is None or shard > last_shard:
            last_shard = shard
            last_user = None
        elif shard < last_shard:
            return False, f"row {idx}: shard decreased ({shard} < {last_shard})"
        if last_user is not None and user < last_user:
            return False, f"row {idx}: user_id not ascending within shard {shard} ('{user}' < '{last_user}')"
        last_user = user
    return True, None

# ------------- ES reproduction ------------- #

def derive_u(seed: bytes, period: str, shard: int, user_id: str) -> float:
    h = hashlib.blake2b(digest_size=32)
    h.update(b"derive_u|ver:1|")
    h.update(seed)
    h.update(b"|period:"); h.update(period.encode("utf-8"))
    h.update(b"|shard:");  h.update(str(shard).encode("utf-8"))
    h.update(b"|user:");   h.update(user_id.encode("utf-8"))
    n = int.from_bytes(h.digest(), "big")
    denom = float(1 << 256)
    u = (n % (1 << 256)) / denom
    if u <= 0.0:
        u = 5e-324
    return u

def reproduce_winners(seed_hex: str, period: str, rows: List[Row], k_total: int) -> List[Tuple[str, int]]:
    seed = bytes.fromhex(seed_hex)
    scored: List[Tuple[float, str, int]] = []  # (score, user_id, weight)
    for shard, user_id, weight in rows:
        if weight <= 0:
            continue
        u = derive_u(seed, period, shard, str(user_id))
        score = -math.log(u) / float(weight)
        scored.append((score, str(user_id), weight))
    scored.sort(key=lambda t: t[0])  # smallest (best) first
    top = scored[:k_total]
    return [(uid, w) for _, uid, w in top]

# ------------- CLI ------------- #

def build_sources(args) -> Tuple[str, str]:
    """
    Determine winners.json URL/path and snapshot.csv URL/path from args.
    Supports:
      - base + period
      - explicit winners + snapshot (either/both may be URL or path)
    """
    if args.winners or args.snapshot:
        if not (args.winners and args.snapshot):
            raise SystemExit("When using explicit paths/URLs, provide BOTH --winners and --snapshot.")
        return args.winners, args.snapshot

    if not (args.base and args.period):
        raise SystemExit("Provide --base and --period, or use --winners and --snapshot.")

    base = args.base.rstrip("/")
    per  = args.period.strip()
    return f"{base}/{per}/winners.json", f"{base}/{per}/snapshot.csv"

def main():
    ap = argparse.ArgumentParser(description="LoyaltyDraw public audit tool")
    ap.add_argument("--period", help="Period (YYYY-MM) when using --base")
    ap.add_argument("--base", help="Artifact base URL (e.g., https://audit.loyaltydraw.com)")
    ap.add_argument("--winners", help="Path/URL to winners.json")
    ap.add_argument("--snapshot", help="Path/URL to snapshot.csv")
    ap.add_argument("--level", default="all", choices=["all", "1", "2", "3"], help="Which checks to run")
    ap.add_argument("--on-missing-seed", default="skip", choices=["error", "skip", "warn"],
                    help="Level 3 behavior if the seed is not revealed")
    ap.add_argument("--quiet", action="store_true", help="Less verbose output")
    args = ap.parse_args()

    winners_src, snapshot_src = build_sources(args)

    if not args.quiet:
        mode = "Local/URL mixed" if (is_url(winners_src) != is_url(snapshot_src)) else ("URL" if is_url(winners_src) else "Local")
        print("== LoyaltyDraw Audit ==")
        if args.period:
            print(f"Period         : {args.period}")
        if args.base:
            print(f"Base           : {args.base}")
        print(f"Mode           : {mode}\n")

    # Load winners.json & snapshot.csv
    winners = load_json(winners_src)
    snapshot_bytes = read_bytes(snapshot_src)

    period = winners.get("period") or (args.period or "").strip()
    if not period:
        raise SystemExit("Unable to determine period (not in winners.json and not provided via --period).")

    # Flatten published alias list (primary + alternates)
    pub_primary = winners.get("winners_primary") or []
    pub_alts    = winners.get("winners_alternates") or []
    pub_aliases = [w.get("alias") for w in (pub_primary + pub_alts) if isinstance(w, dict) and "alias" in w]

    # Determine seed (post-reveal)
    commit = winners.get("commit") or {}
    seed_hex = commit.get("seed_hex") or winners.get("seed_hex")  # legacy support

    want_levels = {"1", "2", "3"} if args.level == "all" else {args.level}

    # ----- Level 1 -----
    if "1" in want_levels:
        expected = (winners.get("snapshot_hash_hex") or "").strip().lower()
        computed = blake2b_hex(snapshot_bytes).strip().lower()
        print("[Level 1] Snapshot integrity")
        print(f"  expected     : {format_short_hex(expected)}")
        print(f"  computed     : {format_short_hex(computed)}")
        if expected == computed and expected:
            print("  result       : ✅ MATCH\n")
        else:
            print("  result       : ❌ MISMATCH\n")
            sys.exit(2)

    # Parse rows once for Level 2 / Level 3
    rows = parse_snapshot_csv(snapshot_bytes)

    # ----- Level 2 -----
    if "2" in want_levels:
        print("[Level 2] Structure & coherence")
        # totals
        totals = winners.get("totals") or {}
        expected_users   = int(totals.get("users") or 0)
        expected_entries = int(totals.get("entries") or 0)
        actual_users   = len(rows)
        actual_entries = sum(max(0, int(w)) for _, _, w in rows)
        ok_totals = (expected_users == actual_users) and (expected_entries == actual_entries)
        print(f"  rows         : {actual_users}")
        print(f"  totals       : users={actual_users} entries={actual_entries}  {'✅ match winners.json' if ok_totals else '❌ do not match winners.json'}")

        # ordering
        ok_order, reason = validate_canonical_order(rows)
        print(f"  ordering     : {'✅ canonical' if ok_order else f'❌ not canonical: {reason}'}")

        # canonical snapshot hash from rows
        recomputed = compute_canonical_snapshot_hash(period, rows).strip().lower()
        expected_h = (winners.get("snapshot_hash_hex") or "").strip().lower()
        print(f"  hash         : {'✅ canonical snapshot hash matches' if expected_h == recomputed else '❌ canonical snapshot hash mismatch'}")
        if not (ok_totals and ok_order and expected_h == recomputed):
            print()
            sys.exit(3)
        print()

    # ----- Level 3 -----
    if "3" in want_levels:
        if not seed_hex:
            msg = "seed is not revealed yet in winners.json.commit.seed_hex"
            if args.on_missing_seed == "error":
                print("[Level 3] Reproduce winners")
                print(f"  status       : ❌ {msg}")
                sys.exit(4)
            elif args.on_missing_seed == "warn":
                print("[Level 3] Reproduce winners")
                print(f"  status       : ⚠️  {msg}")
                print()
                return
            else:
                print("[Level 3] Reproduce winners")
                print(f"  status       : ⏭️  skipped - {msg}")
                print()
                return

        k_primary    = int(winners.get("k_primary") or 0)
        k_alternates = int(winners.get("k_alternates") or 0)
        k_total      = k_primary + k_alternates

        print("[Level 3] Reproduce winners")
        print(f"  seed_hex     : {format_short_hex(seed_hex)}")
        print(f"  k_primary    : {k_primary}")
        print(f"  k_alternates : {k_alternates}")

        recomputed_full = reproduce_winners(seed_hex, period, rows, k_total)
        recomputed_aliases = [display_alias(uid) for uid, _ in recomputed_full]

        if len(recomputed_aliases) != len(pub_aliases):
            print(f"  compare      : ❌ size mismatch (computed {len(recomputed_aliases)} vs published {len(pub_aliases)})")
            sys.exit(5)

        if recomputed_aliases == pub_aliases:
            print("  compare      : ✅ aliases match\n")
        else:
            print("  compare      : ❌ first differences:")
            for i, (a, b) in enumerate(zip(recomputed_aliases, pub_aliases)):
                if a != b:
                    print(f"    idx {i}: computed={a} published={b}")
                    if i > 10:
                        break
            print()
            sys.exit(6)

if __name__ == "__main__":
    main()
