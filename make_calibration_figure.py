#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibration figure: does the confidence know when the adapter is wrong?

Reads the per-pair CSVs the public constraint-gauge runner writes (columns
dw_true, dw_pred_round, hit, conf) and plots accuracy per confidence decile for
the two arms that share identical winding predictions and differ only in what
they report as confidence:

  cycle-conf   how many winding discontinuities accumulate around closed paths
  radius-conf  distance from the scroll centre, a plausible-looking stand-in

Identical windings, so any difference in these curves is the confidence signal
alone. A useful confidence rises left to right. An anti-calibrated one falls,
and is worse than having none, because a solver will trust it exactly where it
should not.

Usage:
  python3 make_calibration_figure.py --node run_node_dense_pairs.csv \\
      --radius run_node-radiusconf_dense_pairs.csv --out calibration.png
"""
import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def deciles(path, nbins=10):
    rows = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            conf = float(r["conf"])
            hit = r["hit"].strip().lower() == "true"
            rows.append((conf, hit))
    rows.sort(key=lambda t: t[0])
    n = len(rows)
    out = []
    for i in range(nbins):
        lo, hi = i * n // nbins, (i + 1) * n // nbins
        chunk = rows[lo:hi]
        if not chunk:
            continue
        out.append(sum(1 for _, h in chunk if h) / len(chunk))
    overall = sum(1 for _, h in rows if h) / n
    return out, overall, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", required=True)
    ap.add_argument("--radius", required=True)
    ap.add_argument("--out", default="calibration.png")
    a = ap.parse_args()

    cyc, cyc_all, n = deciles(a.node)
    rad, rad_all, _ = deciles(a.radius)
    x = list(range(1, len(cyc) + 1))

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
    ax.plot(x, cyc, "o-", color="#2b7bba", lw=2, ms=6, label="cycle-conf (shipped)")
    ax.plot(x, rad, "s--", color="#c0392b", lw=2, ms=5,
            label="radius-conf (shipped as a negative)")
    ax.axhline(cyc_all, color="#888", lw=1, ls=":")
    ax.annotate(f"overall accuracy {cyc_all:.3f}", (0.6, cyc_all), fontsize=8,
                color="#666", va="bottom")

    ax.set_xticks(x)
    ax.set_xlabel("confidence decile  (1 = least confident, 10 = most)")
    ax.set_ylabel("accuracy on the pairs in that decile")
    ax.set_title("Does the confidence know when it is wrong?\n"
                 f"identical winding predictions, {n} PHerc Paris 4 pairs",
                 fontsize=11)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(a.out)
    print("wrote", a.out)
    print("cycle-conf deciles:", " ".join(f"{v:.3f}" for v in cyc))
    print("radius-conf deciles:", " ".join(f"{v:.3f}" for v in rad))


if __name__ == "__main__":
    main()
