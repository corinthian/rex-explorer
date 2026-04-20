"""Bidirectional Dijkstra over the Last.fm similarity graph."""

import heapq
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from lastfm import LastFM

WORKERS = 3

logger = logging.getLogger(__name__)


def find_chain(lastfm: LastFM, from_name: str, to_name: str,
               branch: int = 50, budgets: tuple = (60, 200)) -> dict | None:
    """Find the strongest chain of similar artists between two artists.
    Returns {from, to, hops, path, total_score} or None.
    Tries each budget in sequence, returning on first success."""
    start = time.monotonic()
    stats_before = dict(lastfm.stats)
    result = None
    for budget in budgets:
        result = _find_chain_once(lastfm, from_name, to_name, branch, budget)
        if result is not None:
            break
    elapsed = time.monotonic() - start
    s = lastfm.stats
    delta = {k: s[k] - stats_before[k] for k in s}
    total = sum(delta.values())
    if result is not None:
        logger.info(
            "chain %s\u2192%s: %d calls (%d cache, %d dedup, %d net) "
            "elapsed=%.1fs hops=%d score=%.4f",
            from_name, to_name, total,
            delta["cache_hit"], delta["dedup_hit"], delta["network"],
            elapsed, result["hops"], result["total_score"],
        )
    else:
        logger.info(
            "chain %s\u2192%s: no path; %d calls (%d cache, %d dedup, %d net) elapsed=%.1fs",
            from_name, to_name, total,
            delta["cache_hit"], delta["dedup_hit"], delta["network"],
            elapsed,
        )
    return result


def _find_chain_once(lastfm: LastFM, from_name: str, to_name: str,
                     branch: int = 50, budget_per_side: int = 60) -> dict | None:
    """
    Single-pass bidirectional Dijkstra over the Last.fm similarity graph.
    Both endpoints expand simultaneously via ThreadPoolExecutor (WORKERS=3).
    Stops when the bidirectional termination condition holds or budgets exhaust.
    """
    def lc(s):
        return s.lower()

    from_lc = lc(from_name)
    to_lc = lc(to_name)

    if from_lc == to_lc:
        return {
            "from": from_name, "to": to_name, "hops": 0,
            "path": [{"name": from_name, "match_to_next": None}],
            "total_score": 0.0,
        }

    canon = {from_lc: from_name, to_lc: to_name}
    pair_match = {}  # frozenset({u, v}) -> best match seen

    def record_edge(u, v, match):
        key = frozenset((u, v))
        if match > pair_match.get(key, -1.0):
            pair_match[key] = match

    INF = float("inf")

    fwd_dist = {from_lc: 0.0}
    fwd_expanded = set()
    fwd_heap = [(0.0, from_lc)]
    fwd_budget = [0]

    bwd_dist = {to_lc: 0.0}
    bwd_expanded = set()
    bwd_heap = [(0.0, to_lc)]
    bwd_budget = [0]

    best = INF
    best_mid = None

    def top(heap):
        return heap[0][0] if heap else INF

    def pop_live(heap, dist, expanded):
        """Pop the best live (non-stale, non-expanded) entry. Returns (d, u) or None."""
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, INF) or u in expanded:
                continue
            return d, u
        return None

    def integrate(u, d, similar, dist, other_dist, heap):
        nonlocal best, best_mid
        for sim in similar:
            v = lc(sim["name"])
            if v == u:
                continue  # Last.fm occasionally returns an artist as its own similar
            if v not in canon:
                canon[v] = sim["name"]
            record_edge(u, v, sim["match"])
            nd = d + (1.0 - sim["match"])
            if nd < dist.get(v, INF):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
            if v in other_dist:
                candidate = nd + other_dist[v]
                if candidate < best:
                    best = candidate
                    best_mid = v
        if u in other_dist:
            candidate = d + other_dist[u]
            if candidate < best:
                best = candidate
                best_mid = u

    def _safe_fetch(artist_name):
        try:
            return lastfm.similar_artists(artist_name, limit=branch)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        while fwd_budget[0] < budget_per_side or bwd_budget[0] < budget_per_side:
            ft = top(fwd_heap)
            bt = top(bwd_heap)

            if best < INF and ft + bt >= best:
                break

            # Collect up to WORKERS candidates using the existing side-selection rule.
            # Expand all immediately so within-batch duplicate artists skip themselves.
            candidates = []  # list of ("fwd"|"bwd", u, d)
            for _ in range(WORKERS):
                ft = top(fwd_heap)
                bt = top(bwd_heap)
                use_fwd = (fwd_budget[0] < budget_per_side and
                           (ft <= bt or bwd_budget[0] >= budget_per_side))
                if use_fwd:
                    cand = pop_live(fwd_heap, fwd_dist, fwd_expanded)
                    if cand is not None:
                        d, u = cand
                        fwd_expanded.add(u)
                        fwd_budget[0] += 1
                        candidates.append(("fwd", u, d))
                        continue
                    if bwd_budget[0] >= budget_per_side:
                        break
                    # fwd heap exhausted; fall through to try bwd
                if bwd_budget[0] < budget_per_side:
                    cand = pop_live(bwd_heap, bwd_dist, bwd_expanded)
                    if cand is None:
                        break
                    d, u = cand
                    bwd_expanded.add(u)
                    bwd_budget[0] += 1
                    candidates.append(("bwd", u, d))
                else:
                    break

            if not candidates:
                break

            futures = [ex.submit(_safe_fetch, canon.get(u, u)) for (_, u, _) in candidates]
            results = [f.result() for f in futures]

            for (side, u, d), similar in zip(candidates, results):
                if side == "fwd":
                    integrate(u, d, similar, fwd_dist, bwd_dist, fwd_heap)
                else:
                    integrate(u, d, similar, bwd_dist, fwd_dist, bwd_heap)

    if best_mid is None:
        if to_lc in fwd_dist:
            best_mid = to_lc
            best = fwd_dist[to_lc]
        else:
            return None

    # Reconstruct path: re-run Dijkstra on the discovered subgraph for accurate prev pointers.
    adj = {}
    for pair, match in pair_match.items():
        if len(pair) < 2:
            continue
        u, v = tuple(pair)
        adj.setdefault(u, []).append((v, match))
        adj.setdefault(v, []).append((u, match))

    dist2 = {from_lc: 0.0}
    prev2 = {}
    h2 = [(0.0, from_lc)]
    while h2:
        d, u = heapq.heappop(h2)
        if d > dist2.get(u, INF):
            continue
        if u == to_lc:
            break
        for v, match in adj.get(u, []):
            nd = d + (1.0 - match)
            if nd < dist2.get(v, INF):
                dist2[v] = nd
                prev2[v] = u
                heapq.heappush(h2, (nd, v))

    if to_lc not in dist2:
        return None

    path_lc = []
    cur = to_lc
    seen = set()
    while cur is not None and cur not in seen:
        path_lc.append(cur)
        seen.add(cur)
        if cur == from_lc:
            break
        cur = prev2.get(cur)

    if not path_lc or path_lc[-1] != from_lc:
        return None
    path_lc.reverse()

    result_path = []
    for i, node_lc in enumerate(path_lc):
        if i < len(path_lc) - 1:
            nxt = path_lc[i + 1]
            match = pair_match.get(frozenset((node_lc, nxt)), 0.0)
        else:
            match = None
        result_path.append({"name": canon.get(node_lc, node_lc), "match_to_next": match})

    return {
        "from": result_path[0]["name"],
        "to": result_path[-1]["name"],
        "hops": len(path_lc) - 1,
        "path": result_path,
        "total_score": round(dist2[to_lc], 4),
    }
