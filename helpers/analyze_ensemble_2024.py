import json
import os
import math
import csv
from collections import defaultdict
import matplotlib.pyplot as plt
from gerrychain import Graph
GRAPH_PATH = 'wi_2024_gen_prec_graph_non_nan.json'
ENSEMBLE_NDJSON_PATH = 'rand_ensemble-size-1000-btwn.ndjson'
OUT_DIR = 'ensemble_2024_analysis'
DEM_COL = 'PREDEM24'
REP_COL = 'PREREP24'

def load_graph(path):
    print(f'Loading graph from {path} ...')
    graph = Graph.from_json(path)
    print(f'Graph has {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges')
    return graph

def load_ensemble_ndjson(path):
    print(f'Loading ensemble plans from {path} ...')
    plans = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            plans.append(json.loads(line))
    print(f'Loaded {len(plans)} plans from NDJSON')
    return plans

def aggregate_votes_by_district(graph, assignment, dem_key=DEM_COL, rep_key=REP_COL):
    dem_by_dist = defaultdict(float)
    rep_by_dist = defaultdict(float)
    two_party_by_dist = defaultdict(float)
    for node_id, dist in assignment.items():
        if node_id not in graph.nodes:
            continue
        attr = graph.nodes[node_id]
        dem = attr.get(dem_key, 0.0) or 0.0
        rep = attr.get(rep_key, 0.0) or 0.0
        try:
            dem = float(dem)
        except (TypeError, ValueError):
            dem = 0.0
        try:
            rep = float(rep)
        except (TypeError, ValueError):
            rep = 0.0
        two = dem + rep
        dem_by_dist[dist] += dem
        rep_by_dist[dist] += rep
        two_party_by_dist[dist] += two
    return (dem_by_dist, rep_by_dist, two_party_by_dist)

def compute_efficiency_gap(dem_by_dist, rep_by_dist):
    wasted_dem_total = 0.0
    wasted_rep_total = 0.0
    total_two_party = 0.0
    for dist in dem_by_dist.keys():
        dem = dem_by_dist[dist]
        rep = rep_by_dist[dist]
        total = dem + rep
        if total <= 0:
            continue
        total_two_party += total
        threshold = math.floor(total / 2.0) + 1
        if dem > rep:
            dem_wasted = dem - threshold
            rep_wasted = rep
        elif rep > dem:
            rep_wasted = rep - threshold
            dem_wasted = dem
        else:
            dem_wasted = dem / 2.0
            rep_wasted = rep / 2.0
        wasted_dem_total += max(dem_wasted, 0.0)
        wasted_rep_total += max(rep_wasted, 0.0)
    if total_two_party == 0:
        return float('nan')
    eg = (wasted_dem_total - wasted_rep_total) / total_two_party
    return eg

def compute_mean_median(dem_by_dist, rep_by_dist):
    shares = []
    for dist in dem_by_dist.keys():
        dem = dem_by_dist[dist]
        rep = rep_by_dist[dist]
        total = dem + rep
        if total <= 0:
            continue
        shares.append(dem / total)
    if not shares:
        return float('nan')
    shares_sorted = sorted(shares)
    n = len(shares_sorted)
    mean_share = sum(shares_sorted) / n
    if n % 2 == 1:
        median_share = shares_sorted[n // 2]
    else:
        median_share = 0.5 * (shares_sorted[n // 2 - 1] + shares_sorted[n // 2])
    return mean_share - median_share

def compute_partisan_bias(dem_by_dist, rep_by_dist):
    shares = []
    total_dem = 0.0
    total_rep = 0.0
    for dist in dem_by_dist.keys():
        dem = dem_by_dist[dist]
        rep = rep_by_dist[dist]
        total = dem + rep
        if total <= 0:
            continue
        shares.append(dem / total)
        total_dem += dem
        total_rep += rep
    if not shares or total_dem + total_rep == 0:
        return float('nan')
    statewide_dem_share = total_dem / (total_dem + total_rep)
    shift = 0.5 - statewide_dem_share
    swung_shares = [min(max(s + shift, 0.0), 1.0) for s in shares]
    num_dists = len(swung_shares)
    dem_seats_at_50 = sum((1 for s in swung_shares if s > 0.5))
    seat_share_dem_50 = dem_seats_at_50 / num_dists
    return seat_share_dem_50 - 0.5

def compute_declination(dem_by_dist, rep_by_dist):
    shares = []
    for dist in dem_by_dist.keys():
        dem = dem_by_dist[dist]
        rep = rep_by_dist[dist]
        total = dem + rep
        if total <= 0:
            continue
        shares.append(dem / total)
    if not shares:
        return float('nan')
    shares_sorted = sorted(shares)
    n = len(shares_sorted)
    k = sum((1 for s in shares_sorted if s <= 0.5))
    if k == 0 or k == n:
        return float('nan')
    mean_R = sum(shares_sorted[:k]) / k
    mean_D = sum(shares_sorted[k:]) / (n - k)
    theta_R = math.atan((0.5 - mean_R) * n / k)
    theta_D = math.atan((mean_D - 0.5) * n / (n - k))
    decl = (theta_D - theta_R) * 180.0 / math.pi
    return decl

def compute_competitiveness(dem_by_dist, rep_by_dist, low=0.45, high=0.55):
    count = 0
    for dist in dem_by_dist.keys():
        dem = dem_by_dist[dist]
        rep = rep_by_dist[dist]
        total = dem + rep
        if total <= 0:
            continue
        share = dem / total
        if low <= share <= high:
            count += 1
    return count

def make_hist(values, title, xlabel, outfile, bins=30):
    clean_vals = [v for v in values if not math.isnan(v)]
    if not clean_vals:
        print(f'[WARN] No finite values to plot for {title}, skipping.')
        return
    plt.figure()
    plt.hist(clean_vals, bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('Number of plans')
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()
    print(f'Saved: {outfile}')

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    graph = load_graph(GRAPH_PATH)
    plans = load_ensemble_ndjson(ENSEMBLE_NDJSON_PATH)
    metrics = []
    total_dem_state = 0.0
    total_rep_state = 0.0
    for node_id in graph.nodes:
        attr = graph.nodes[node_id]
        d = float(attr.get(DEM_COL, 0.0) or 0.0)
        r = float(attr.get(REP_COL, 0.0) or 0.0)
        total_dem_state += d
        total_rep_state += r
    if total_dem_state + total_rep_state > 0:
        statewide_dem_share = total_dem_state / (total_dem_state + total_rep_state)
    else:
        statewide_dem_share = float('nan')
    print(f'Statewide Dem share (2024 presidential): {statewide_dem_share:.4f}')
    for plan in plans:
        idx = plan.get('plan_index')
        num_districts = plan.get('num_districts')
        eg_from_gen = plan.get('efficiency_gap')
        rep_seats_generated = plan.get('rep_seats_won')
        dem_seats_generated = plan.get('dem_seats_won')
        assignment_raw = plan.get('assignment', {})
        assignment = {int(node): int(dist) for node, dist in assignment_raw.items()}
        dem_by_dist, rep_by_dist, two_by_dist = aggregate_votes_by_district(graph, assignment)
        dem_seats = 0
        gop_seats = 0
        ties = 0
        for dist in dem_by_dist.keys():
            dem = dem_by_dist[dist]
            rep = rep_by_dist[dist]
            if dem > rep:
                dem_seats += 1
            elif rep > dem:
                gop_seats += 1
            else:
                ties += 1
        D = dem_seats + gop_seats + ties
        seat_share_dem = dem_seats / D if D > 0 else float('nan')
        seat_share_gop = gop_seats / D if D > 0 else float('nan')
        eg = compute_efficiency_gap(dem_by_dist, rep_by_dist)
        mm = compute_mean_median(dem_by_dist, rep_by_dist)
        pbias = compute_partisan_bias(dem_by_dist, rep_by_dist)
        decl = compute_declination(dem_by_dist, rep_by_dist)
        comp_45_55 = compute_competitiveness(dem_by_dist, rep_by_dist, 0.45, 0.55)
        comp_48_52 = compute_competitiveness(dem_by_dist, rep_by_dist, 0.48, 0.52)
        metrics.append({'plan_index': idx, 'num_districts': num_districts, 'rep_seats_generated': rep_seats_generated, 'dem_seats_generated': dem_seats_generated, 'gop_seats_recomputed': gop_seats, 'dem_seats_recomputed': dem_seats, 'ties': ties, 'seat_share_gop': seat_share_gop, 'seat_share_dem': seat_share_dem, 'efficiency_gap_generated': eg_from_gen, 'efficiency_gap_recomputed': eg, 'mean_median': mm, 'partisan_bias': pbias, 'declination_deg': decl, 'competitive_45_55': comp_45_55, 'competitive_48_52': comp_48_52, 'statewide_dem_share': statewide_dem_share})
    if metrics:
        csv_path = os.path.join(OUT_DIR, 'plan_metrics_2024.csv')
        fieldnames = list(metrics[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metrics)
        print(f'Wrote metrics for {len(metrics)} plans to {csv_path}')
    else:
        print('No metrics computed (no plans?)')
        return
    get = lambda key: [m[key] for m in metrics]
    make_hist(get('gop_seats_recomputed'), 'GOP seats distribution (2024 ensemble)', 'GOP seats', os.path.join(OUT_DIR, 'hist_gop_seats_2024.png'), bins=range(0, max(get('gop_seats_recomputed') + [0]) + 2))
    make_hist(get('efficiency_gap_recomputed'), 'Efficiency gap distribution (Dem-positive, GOP-negative) – 2024', 'Efficiency gap', os.path.join(OUT_DIR, 'hist_efficiency_gap_2024.png'))
    make_hist(get('mean_median'), 'Mean–median difference (Dem share) – 2024 ensemble', 'Mean − median (Dem share)', os.path.join(OUT_DIR, 'hist_mean_median_2024.png'))
    make_hist(get('partisan_bias'), 'Partisan bias (seat share at 50% votes − 0.5) – 2024', 'Partisan bias', os.path.join(OUT_DIR, 'hist_partisan_bias_2024.png'))
    make_hist(get('declination_deg'), 'Declination distribution (degrees; + => GOP advantage) – 2024', 'Declination (degrees)', os.path.join(OUT_DIR, 'hist_declination_2024.png'))
    make_hist(get('competitive_45_55'), 'Competitive seats (45–55% Dem) per plan – 2024', '# of 45–55% seats', os.path.join(OUT_DIR, 'hist_competitive_45_55_2024.png'))
    make_hist(get('competitive_48_52'), 'Highly competitive seats (48–52% Dem) per plan – 2024', '# of 48–52% seats', os.path.join(OUT_DIR, 'hist_competitive_48_52_2024.png'))
    print('Done generating 2024 ensemble metrics and plots.')
if __name__ == '__main__':
    main()
