"""Bidirectional Dijkstra over the Last.fm similarity graph."""

import heapq
from lastfm import LastFM


def find_chain(lastfm: LastFM, from_name: str, to_name: str,
               branch: int = 50, budget_per_side: int = 60) -> dict | None:
    """
    Find the strongest chain of similar artists between two artists.
    Returns {from, to, hops, path, total_score} or None.

    Uses bidirectional Dijkstra: both endpoints expand simultaneously toward
    each other, each with a priority queue ordered by 1-match (lower = stronger).
    Stops when the classic bidirectional termination condition holds or both
    budgets are exhausted. Edge weights are derived from observed similarity
    scores and treated as undirected (best match wins for each pair).
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
    # Best match seen for each undirected pair (stored as frozenset for lookup)
    pair_match = {}  # frozenset({u, v}) -> match

    def record_edge(u, v, match):
        key = frozenset((u, v))
        if match > pair_match.get(key, -1.0):
            pair_match[key] = match

    INF = float("inf")

    # Forward state (expanding from from_lc)
    fwd_dist = {from_lc: 0.0}
    fwd_expanded = set()
    fwd_heap = [(0.0, from_lc)]
    fwd_budget = [0]

    # Backward state (expanding from to_lc)
    bwd_dist = {to_lc: 0.0}
    bwd_expanded = set()
    bwd_heap = [(0.0, to_lc)]
    bwd_budget = [0]

    best = INF   # best complete path weight found so far
    best_mid = None  # the node bridging the two halves

    def expand_one(heap, dist, expanded, budget, other_dist):
        nonlocal best, best_mid
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, INF):
                continue
            if u in expanded:
                continue
            expanded.add(u)
            budget[0] += 1

            artist_display = canon.get(u, u)
            try:
                similar = lastfm.similar_artists(artist_display, limit=branch)
            except Exception:
                similar = []

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
                # Check if this creates a complete path
                if v in other_dist:
                    candidate = nd + other_dist[v]
                    if candidate < best:
                        best = candidate
                        best_mid = v

            # Also check u itself against the other side
            if u in other_dist:
                candidate = d + other_dist[u]
                if candidate < best:
                    best = candidate
                    best_mid = u

            return True  # expanded one node
        return False  # heap empty

    while (fwd_budget[0] < budget_per_side or bwd_budget[0] < budget_per_side):
        fwd_top = fwd_heap[0][0] if fwd_heap else INF
        bwd_top = bwd_heap[0][0] if bwd_heap else INF

        # Classic bidirectional stopping condition
        if best < INF and fwd_top + bwd_top >= best:
            break

        # Expand the side with the smaller frontier value, respecting budgets
        if fwd_budget[0] < budget_per_side and (fwd_top <= bwd_top or bwd_budget[0] >= budget_per_side):
            if not expand_one(fwd_heap, fwd_dist, fwd_expanded, fwd_budget, bwd_dist):
                if bwd_budget[0] >= budget_per_side:
                    break
        elif bwd_budget[0] < budget_per_side:
            if not expand_one(bwd_heap, bwd_dist, bwd_expanded, bwd_budget, fwd_dist):
                break
        else:
            break

    if best_mid is None:
        # Direct path: maybe to_lc ended up in fwd_dist
        if to_lc in fwd_dist:
            best_mid = to_lc
            best = fwd_dist[to_lc]
        else:
            return None

    # Reconstruct the path.
    # Build a combined undirected adjacency from pair_match for shortest-path tracing.
    # We re-run Dijkstra on the discovered subgraph for accurate prev pointers.
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

    # Trace path back
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
