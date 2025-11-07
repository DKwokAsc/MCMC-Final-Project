import argparse
import inspect
import json
import math
import random
from functools import partial

import networkx as nx
from gerrychain import Graph, Partition, constraints, MarkovChain, metrics
from gerrychain.updaters import Tally, Election
from gerrychain.proposals import recom

# Field detection
def detect_fields(graph):
    n0 = next(iter(graph.nodes))
    attrs = graph.nodes[n0]

    # Population
    pop_col = None
    for cand in ("TOT_POP", "PERSONS", "PERSONS18"):
        if cand in attrs:
            pop_col = cand
            break
    if pop_col is None:
        raise KeyError("No population column found (tried TOT_POP, PERSONS, PERSONS18).")

    # Democratic/Republican vote columns
    dem_rep_candidates = [
        ("PRES12D", "PRES12R"),
        ("PREDEM24", "PREREP24"),
        ("USHDEM24", "USHREP24"),
        ("WSADEM24", "WSAREP24"),
        ("WSSDEM24", "WSSREP24"),
    ]
    dem_col = rep_col = None
    for d, r in dem_rep_candidates:
        if d in attrs and r in attrs:
            dem_col, rep_col = d, r
            break
    if dem_col is None:
        raise KeyError("No Dem/Rep vote columns found.")

    # Assignment keys
    plan_candidates = [
        ("538DEM_PL", "FiveThirtyEight Democratic-favoring"),
        ("538GOP_PL", "FiveThirtyEight Republican-favoring"),
        ("538CPCT__1", "FiveThirtyEight Compactness-favoring"),
        ("CONG_DIST", "Congressional"),
        ("SLDL_DIST", "State Lower"),
        ("SLDU_DIST", "State Upper"),
    ]
    plans = [(k, label) for (k, label) in plan_candidates if k in attrs]
    if not plans:
        raise KeyError("No assignment keys found (looked for 538*, CONG_DIST, SLDL_DIST, SLDU_DIST).")

    return pop_col, dem_col, rep_col, plans

# ---------- Globals (filled after setup) ----------
DEM_KEY = None
REP_KEY = None
POP_KEY = None
UPDATERS = None
PLANS = None

def setup_from_graph(graph):
    global DEM_KEY, REP_KEY, POP_KEY, UPDATERS, PLANS
    POP_KEY, DEM_KEY, REP_KEY, PLANS = detect_fields(graph)
    UPDATERS = {
        "population": Tally(POP_KEY, alias="population"),
        DEM_KEY: Tally(DEM_KEY, alias=DEM_KEY),
        REP_KEY: Tally(REP_KEY, alias=REP_KEY),
        "ELECT": Election("ELECT", {"Dem": DEM_KEY, "Rep": REP_KEY}),
    }

# ---------- Preprocessing ----------
def _coerce_numeric(x):
    try:
        v = float(x)
        if math.isnan(v):
            return 0.0
        return v
    except Exception:
        return 0.0

def preprocess_graph(graph, pop_key: str, dem_key: str, rep_key: str, drop_zero_pop: bool = False):
    # Remove islands
    islands = [n for n, deg in graph.degree() if deg == 0]
    if islands:
        print(f"Removing {len(islands)} island node(s).")
        graph.remove_nodes_from(islands)

    fixed_pop_nan = fixed_dem_nan = fixed_rep_nan = 0
    for n in list(graph.nodes):
        a = graph.nodes[n]

        pv = _coerce_numeric(a.get(pop_key, 0))
        if pv == 0.0 and (a.get(pop_key, None) is None or str(a.get(pop_key)).lower() in ("nan", "none")):
            fixed_pop_nan += 1
        a[pop_key] = int(round(pv))

        dv = _coerce_numeric(a.get(dem_key, 0))
        if dv == 0.0 and (a.get(dem_key, None) is None or str(a.get(dem_key)).lower() in ("nan", "none")):
            fixed_dem_nan += 1
        a[dem_key] = int(round(dv))

        rv = _coerce_numeric(a.get(rep_key, 0))
        if rv == 0.0 and (a.get(rep_key, None) is None or str(a.get(rep_key)).lower() in ("nan", "none")):
            fixed_rep_nan += 1
        a[rep_key] = int(round(rv))

    if fixed_pop_nan or fixed_dem_nan or fixed_rep_nan:
        print(f"Patched NaNs -> 0  | pop: {fixed_pop_nan}  dem: {fixed_dem_nan}  rep: {fixed_rep_nan}")

    if drop_zero_pop:
        zeros = [n for n in graph.nodes if graph.nodes[n].get(pop_key, 0) == 0]
        if zeros:
            print(f"Dropping {len(zeros)} zero-pop node(s).")
            graph.remove_nodes_from(zeros)

# ---------- Helpers ----------
def seats_gop_by_tally(partition) -> int:
    D = partition[DEM_KEY]
    R = partition[REP_KEY]
    return sum(int(R[d] > D[d]) for d in partition.parts)

def efficiency_gap(partition):
    return metrics.efficiency_gap(partition["ELECT"])

def make_recom_proposal(pop_col, ideal_pop, epsilon):
    # Pass only supported kwargs for installed GerryChain
    sig = inspect.signature(recom)
    allowed = set(sig.parameters.keys())
    candidate_kwargs = dict(
        pop_col=pop_col,
        pop_target=ideal_pop,
        epsilon=epsilon,
        node_repeats=2,
        max_attempts=10000,    # dropped if unsupported
        pair_reselection=True  # dropped if unsupported
    )
    kwargs = {k: v for k, v in candidate_kwargs.items() if k in allowed}
    return partial(recom, **kwargs)

def is_partition_contiguous(partition) -> bool:
    G = partition.graph
    for nodes in partition.parts.values():
        sub = G.subgraph(nodes)
        if sub.number_of_nodes() == 0 or not nx.is_connected(sub):
            return False
    return True

def assignment_dict(partition):
    # JSON-serializable mapping node -> district label
    return {str(node): int(label) for node, label in partition.assignment.items()}

# ---------- Streaming saver ----------
def stream_plans_ndjson(
    graph,
    samples=50,
    steps_between=100, 
    epsilon=0.02,
    seed=24,
    out_path="ensemble_plans.ndjson",
    burn_in=0,
    thin=1,
):
    random.seed(seed)

    # Choose starting assignment
    pref_order = ["538CPCT__1", "SLDL_DIST", "SLDU_DIST", "CONG_DIST"]
    have = [k for (k, _) in PLANS]
    start_key = next((cand for cand in pref_order if cand in have), have[0])

    initial = Partition(graph, assignment=start_key, updaters=UPDATERS)
    k = len(initial.parts)
    total_pop = sum(initial["population"].values())
    ideal = total_pop / k
    print(f"Start plan: {start_key} | Districts: {k} | Total pop: {int(total_pop)} | Ideal: {ideal:.2f}")

    proposal = make_recom_proposal(pop_col=POP_KEY, ideal_pop=ideal, epsilon=epsilon)
    pop_ok = constraints.within_percent_of_ideal_population(initial, percent=epsilon * 100, pop_key="population")

    chain = MarkovChain(
        proposal=proposal,
        constraints=[pop_ok],
        accept=lambda p: True,
        initial_state=initial,
        total_steps=(samples + burn_in) * (steps_between + 1) * thin + 100,  
    )

    # Overwrite output file at start
    open(out_path, "w").close()

    saved = 0
    saved_states_seen = 0

    with open(out_path, "a", encoding="utf-8") as f:
        for step, state in enumerate(chain):
            # Save every (steps_between+1)-th step
            if step % (steps_between + 1) != steps_between:
                continue

            saved_states_seen += 1
            if saved_states_seen <= burn_in:
                continue
            if (saved_states_seen - burn_in - 1) % thin != 0:
                continue

            contig = is_partition_contiguous(state)
            gop = seats_gop_by_tally(state)
            eg = efficiency_gap(state)

            # Each plan is its own JSON object WITH its own 'meta'
            obj = {
                "meta": {
                    "source_graph": "pretty_print.json",
                    "epsilon": epsilon,
                    "seed": seed,
                    "steps_between": steps_between,
                    "burn_in": burn_in,
                    "thin": thin,
                    "pop_key": POP_KEY,
                    "dem_key": DEM_KEY,
                    "rep_key": REP_KEY,
                },
                "index": saved + 1,
                "contiguous": contig,
                "gop_seats": gop,
                "efficiency_gap": eg,
                "assignment": assignment_dict(state),
            }

            # Write immediately 
            with open(out_path, "a", encoding="utf-8") as pf:
                json.dump(obj, pf, indent=2, ensure_ascii=False)
                pf.write("\n\n")  # blank line between plans

            f.flush()



            print(f"[saved {saved + 1:3d}] GOP={gop:2d}  EG={eg: .4f}")
            saved += 1
            if saved >= samples:
                break

    print(f"\nStream-saved {saved} plans to {out_path} (NDJSON: one JSON object per line).")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10, help="How many plans to save")
    parser.add_argument("--epsilon", type=float, default=0.02, help="Population tolerance (e.g., 0.02 = ±2%)")
    parser.add_argument("--seed", type=int, default=24)
    parser.add_argument("--burn_in", type=int, default=0)
    parser.add_argument("--thin", type=int, default=1)
    parser.add_argument("--drop_zero_pop", action="store_true")
    parser.add_argument("--out", type=str, default="ensemble_plans.ndjson", help="Output NDJSON file")
    args = parser.parse_args()

    filename = "pretty_print.json"  # hard-coded dataset
    print(f"Loading graph from {filename} ...")
    graph = Graph.from_json(filename)

    pop_col, dem_col, rep_col, _ = detect_fields(graph)
    preprocess_graph(graph, pop_col, dem_col, rep_col, drop_zero_pop=args.drop_zero_pop)
    setup_from_graph(graph)

    stream_plans_ndjson(
        graph,
        samples=args.samples,
        steps_between=100, 
        epsilon=args.epsilon,
        seed=args.seed,
        out_path=args.out,
        burn_in=args.burn_in,
        thin=args.thin,
    )


if __name__ == "__main__":
    main()