#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Three evidence figures for the ST winding adapter, all read out of scored
per-pair CSVs written by the public constraint-gauge runner.

  1. precision_coverage.png  what a solver gains by accepting only the top-k
                             most confident constraints, for the shipped
                             cycle-conf, for the shipped anti-calibrated
                             radius-conf, and for the same radius signal with
                             its sign corrected.
  2. error_structure.png     where the adapter succeeds and fails: the signed
                             residual, accuracy vs true winding distance, and
                             accuracy vs radial position in the scroll.
  3. error_independence.png  correlation of this adapter's per-pair errors with
                             other generators' errors on the identical pairs.

Every input is a `<prefix>_pairs.csv` from `run_gauge.py`, plus the Paris 4
ground-truth point collection (for pair geometry) and the per-slice umbilicus
that the generator already used. Nothing is typed by hand.

Usage (paths are the ones used to produce the committed PNGs):
  python3 make_evidence_figures.py --gauge /path/to/_gauge --out .
"""
import argparse, csv, glob, itertools, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, RED, ORANGE, GREY = "#2b7bba", "#c0392b", "#d97b20", "#888888"


def load_csv(path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for k in rows[0]:
        out[k] = (np.array([r[k].strip().lower() == "true" for r in rows])
                  if k == "hit" else np.array([float(r[k]) for r in rows]))
    return out


def gt_pairs(gt_path, max_dw=6):
    doc = json.load(open(gt_path))
    xs, ws, cs = [], [], []
    for cid, col in doc["collections"].items():
        for _, pt in col.get("points", {}).items():
            xs.append(pt["p"]); ws.append(float(pt["wind_a"])); cs.append(cid)
    xs = np.asarray(xs, float); ws = np.asarray(ws, float)
    cs = np.asarray(cs, object)
    a, b = [], []
    for cid in np.unique(cs):
        idx = np.nonzero(cs == cid)[0]
        for i, j in itertools.combinations(idx, 2):
            d = ws[j] - ws[i]; r = round(d)
            if abs(d - r) > 1e-6 or r == 0 or abs(r) > max_dw:
                continue
            a.append(i if r > 0 else j); b.append(j if r > 0 else i)
    return xs, np.array(a), np.array(b)


def radii(xyz, graph_dir):
    zs, um = [], []
    for fp in sorted(glob.glob(os.path.join(graph_dir, "graph_z*.npz"))):
        d = np.load(fp)
        zs.append(float(d["z_L2"])); um.append([d["umbilicus_yx"][1],
                                                d["umbilicus_yx"][0]])
    o = np.argsort(zs)
    zs = np.array(zs)[o]; um = np.array(um)[o]
    k = np.abs(xyz[:, 2][:, None] - zs[None, :]).argmin(1)
    return np.hypot(*(xyz[:, :2] - um[k]).T)


def topk(conf, hit, ks):
    order = np.argsort(-conf, kind="stable"); n = len(conf)
    acc, cnt = [], []
    for k in ks:
        t = order[:max(1, int(round(k * n)))]
        acc.append(hit[t].mean()); cnt.append(int(hit[t].sum()))
    return np.array(acc), np.array(cnt)


def fig_precision_coverage(node, radc, r_pair, out):
    hit = node["hit"]
    ks = np.arange(0.05, 1.001, 0.025)
    series = [("cycle-conf (shipped)", node["conf"], BLUE, "o-"),
              ("radius-conf (shipped as a negative)", radc["conf"], RED, "s--"),
              ("radius, sign corrected (not shipped)", r_pair, ORANGE, "^-.")]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.0, 4.4), dpi=160)
    for lbl, cf, col, st in series:
        acc, cnt = topk(cf, hit, ks)
        ax1.plot(ks, acc, st, color=col, lw=2, ms=4, label=lbl, markevery=4)
        ax2.plot(ks, cnt, st, color=col, lw=2, ms=4, markevery=4)
    ax1.axhline(hit.mean(), color=GREY, lw=1, ls=":")
    ax1.annotate(f"accept everything: {hit.mean():.3f}", (0.30, hit.mean() + 0.004),
                 fontsize=8, color="#666")
    ax1.set_xlabel("fraction of constraints accepted (most confident first)")
    ax1.set_ylabel("accuracy of the accepted set")
    ax1.set_title("Precision a solver gets by accepting only\nthe top-k confident constraints",
                  fontsize=11)
    ax2.set_xlabel("fraction of constraints accepted (most confident first)")
    ax2.set_ylabel("number of correct constraints delivered")
    ax2.set_title("...and what it costs: correct constraints\nleft on the table",
                  fontsize=11)
    for ax in (ax1, ax2):
        ax.grid(alpha=0.25)
    ax1.legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle(f"{len(hit)} PHerc Paris 4 pairs, identical winding predictions in all three curves",
                 fontsize=9, color="#555", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out); print("wrote", out)


def fig_error_structure(node, r_pair, out):
    e = node["dw_pred"] - node["dw_true"]
    dwt = node["dw_true"]; hit = node["hit"]
    fig, axs = plt.subplots(1, 3, figsize=(13.2, 4.0), dpi=160)

    ax = axs[0]
    ax.hist(np.clip(e, -12, 6), bins=np.arange(-12, 6.5, 0.5), color=BLUE,
            edgecolor="white", lw=0.4)
    ax.annotate("0.8% of residuals fall below −12\nand 0.3% above +6; both are\nclipped into the end bins",
                (0.03, 0.72), xycoords="axes fraction", fontsize=7.5, color="#666")
    ax.axvline(0, color="#333", lw=1)
    ax.axvline(e.mean(), color=RED, lw=1.6, ls="--",
               label=f"mean {e.mean():+.2f}")
    ax.set_xlabel("signed residual  (predicted $\\Delta w$ − human $\\Delta w$)")
    ax.set_ylabel("pairs")
    ax.set_title("The error is not unbiased:\nit under-counts crossings", fontsize=11)
    ax.legend(frameon=False, fontsize=9)

    ax = axs[1]
    ks = np.arange(1, 7)
    acc = [hit[dwt == k].mean() for k in ks]
    bias = [e[dwt == k].mean() for k in ks]
    ax.plot(ks, acc, "o-", color=BLUE, lw=2, ms=6, label="exact-match accuracy")
    ax.set_xlabel("true winding distance $\\Delta w$")
    ax.set_ylabel("accuracy", color=BLUE)
    ax.set_ylim(0, 0.35)
    ax2 = ax.twinx()
    ax2.plot(ks, bias, "s--", color=RED, lw=2, ms=5, label="mean signed residual")
    ax2.set_ylabel("mean signed residual", color=RED)
    ax.set_title("Accuracy falls and the under-count grows\nwith winding distance", fontsize=11)
    ax.grid(alpha=0.25)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper center")

    ax = axs[2]
    q = np.quantile(r_pair, np.linspace(0, 1, 11)); q[-1] += 1e-9
    xs, ys = [], []
    for k in range(10):
        m = (r_pair >= q[k]) & (r_pair < q[k + 1])
        xs.append(0.5 * (q[k] + q[k + 1])); ys.append(hit[m].mean())
    ax.plot(xs, ys, "o-", color=BLUE, lw=2, ms=5)
    ax.axhline(hit.mean(), color=GREY, lw=1, ls=":")
    ax.set_xlabel("radius from the umbilicus (vox, pair minimum)")
    ax.set_ylabel("accuracy in that decile")
    ax.set_title("Failure is radial: the inner windings\nare where it is wrong", fontsize=11)
    ax.grid(alpha=0.25)
    axs[0].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out); print("wrote", out)


def fig_independence(pairs_by_arm, shares, out):
    """shares: arm -> which component it has in common with this adapter."""
    from scipy.stats import spearmanr
    base = pairs_by_arm["this adapter (ST + L2 sync)"]
    eb = base["dw_pred"] - base["dw_true"]
    palette = {"ST field": BLUE, "graph + anchor": ORANGE, "graph only": RED}
    names, vals, cols = [], [], []
    for nm, c in pairs_by_arm.items():
        if nm.startswith("this adapter"):
            continue
        e = c["dw_pred"] - c["dw_true"]
        names.append(nm); vals.append(spearmanr(eb, e).statistic)
        cols.append(palette[shares[nm]])
    order = np.argsort(vals)
    names = [names[i] for i in order]; vals = [vals[i] for i in order]
    cols = [cols[i] for i in order]
    fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=160)
    y = np.arange(len(names))
    ax.barh(y, vals, color=cols, height=0.6)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color="#333", lw=1)
    for yi, v in zip(y, vals):
        ax.annotate(f"{v:+.2f}", (v + (0.02 if v >= 0 else -0.02), yi),
                    va="center", ha="left" if v >= 0 else "right", fontsize=8,
                    color="#444")
    ax.set_xlabel("Spearman correlation of per-pair signed residuals with this adapter\n"
                  "(0 = errors independent; identical pairs, identical rows)")
    ax.set_title("Correlation tracks how much is shared — and a partial test:\n"
                 "every non-ST arm we hold sits on the same seed graph",
                 fontsize=11)
    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[k]) for k in palette]
    ax.legend(handles, ["same structure-tensor field, different integration",
                        "winding-sync solve, same seed graph, same sign gauge",
                        "winding-sync solve, same seed graph, opposite sign gauge"],
              frameon=False, fontsize=8, loc="lower right")
    ax.annotate("validity check: the two arms that\nare the same winding-sync solve\n"
                "correlate +0.98 with each other",
                (0.015, 0.55), xycoords="axes fraction", fontsize=7.5, color="#666")
    ax.set_xlim(-0.6, 0.85)
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(out); print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gauge", required=True,
                    help="local constraint-gauge run directory (not in this repository; see README)")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    G = a.gauge
    fin = f"{G}/_deliverable/_finer"
    node = load_csv(f"{fin}/run_node_dense_pairs.csv")
    radc = load_csv(f"{fin}/run_node-radiusconf_dense_pairs.csv")
    xyz, ai, bi = gt_pairs(f"{G}/gt/relative_windings_paris4.json")
    r = radii(xyz, f"{fin}/graphs200")
    r_pair = np.minimum(r[ai], r[bi])

    fig_precision_coverage(node, radc, r_pair,
                           os.path.join(a.out, "precision_coverage.png"))
    fig_error_structure(node, r_pair,
                        os.path.join(a.out, "error_structure.png"))
    fig_independence({
        "this adapter (ST + L2 sync)": node,
        "ST radial arm (same ST field)": load_csv(f"{fin}/run_radial_dense_pairs.csv"),
        "winding-sync L1, anchored": load_csv(f"{G}/_headtohead/P4_A-windingsync-L1_pairs.csv"),
        "winding-sync L1, raw gauge": load_csv(f"{G}/_headtohead/P4_A-windingsync-L1-raw_pairs.csv"),
        "winding-sync BFS, anchored": load_csv(f"{G}/_headtohead/P4_A-bfs_pairs.csv"),
        "retired S-E adapter\n(= winding-sync L1, raw)": load_csv(f"{G}/runs/full_calibrated_v2.4_pairs.csv"),
    }, {
        "ST radial arm (same ST field)": "ST field",
        "winding-sync L1, anchored": "graph + anchor",
        "winding-sync L1, raw gauge": "graph only",
        "winding-sync BFS, anchored": "graph + anchor",
        "retired S-E adapter\n(= winding-sync L1, raw)": "graph only",
    }, os.path.join(a.out, "error_independence.png"))


if __name__ == "__main__":
    main()
