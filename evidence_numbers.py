#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every number in ADAPTER_EVIDENCE_2026-08-19.md, printed from files on disk.

Inputs, all of them `<prefix>_pairs.csv` files written by the public
constraint-gauge runner, plus the Paris 4 ground-truth point collection and the
per-slice umbilicus the generator already used:

  _deliverable/_finer/run_{node,radial,node-radiusconf}_dense_pairs.csv
  _deliverable/_finer/run_{node,radial,node-radiusconf}_pairs.csv
  _deliverable/run_{node,radial}_pairs.csv
  _headtohead/P4_A-{windingsync-L1,windingsync-L1-raw,bfs}_pairs.csv
  runs/full_{calibrated,uniform}_v2.4_pairs.csv
  gt/relative_windings_paris4.json
  _deliverable/_finer/graphs200/graph_z*.npz   (umbilicus per slice)

Run:  python3 evidence_numbers.py [/path/to/_gauge]

Sections: 0 alignment, 1 error structure, 2 precision/coverage,
3 error correlation between arms, 4 ablations, 5 baseline provenance.
No network, no GPU, no third-party code executed.
"""
import sys
import csv, glob, itertools, json, os
import numpy as np

if len(sys.argv) < 2:
    sys.exit("usage: evidence_numbers.py /path/to/_gauge  "
             "(your local constraint-gauge run directory; not in this repository — see README)")
G = sys.argv[1]
FIN = f"{G}/_deliverable/_finer"
H2H = f"{G}/_headtohead"

# ---------- 1. reconstruct the GT pairs exactly as gauge/gt.py builds them ----
def load_points(path):
    doc = json.load(open(path))
    xs, ws, cs = [], [], []
    for cid, col in doc["collections"].items():
        for _, pt in col.get("points", {}).items():
            xs.append(pt["p"]); ws.append(float(pt["wind_a"])); cs.append(cid)
    return np.asarray(xs, float), np.asarray(ws, float), np.asarray(cs, object)

def build_pairs(xyz, wind, coll, max_dw=6):
    a, b, dws, pc = [], [], [], []
    for cid in np.unique(coll):
        idx = np.nonzero(coll == cid)[0]
        for i, j in itertools.combinations(idx, 2):
            dw = wind[j] - wind[i]; r = round(dw)
            if abs(dw - r) > 1e-6 or r == 0 or abs(r) > max_dw:
                continue
            if r > 0: a.append(i); b.append(j); dws.append(int(r))
            else:     a.append(j); b.append(i); dws.append(int(-r))
            pc.append(cid)
    return (np.array(a), np.array(b), np.array(dws), np.array(pc, object))

xyz, wind, coll = load_points(f"{G}/gt/relative_windings_paris4.json")
ai, bi, dw, pcoll = build_pairs(xyz, wind, coll)
print(f"[gt] {len(xyz)} points, {len(dw)} pairs, {len(np.unique(coll))} collections")

# ---------- per-pair geometry ----------
umbs, zs = {}, []
for fp in sorted(glob.glob(f"{FIN}/graphs200/graph_z*.npz")):
    d = np.load(fp)
    z = float(d["z_L2"]); u = d["umbilicus_yx"]
    umbs[z] = np.array([u[1], u[0]])   # x, y  (common.py convention)
    zs.append(z)
zs = np.array(sorted(zs))
UM = np.array([umbs[z] for z in zs])

def radius(p):
    k = np.abs(p[:, 2][:, None] - zs[None, :]).argmin(1)
    return np.hypot(*(p[:, :2] - UM[k]).T), k

r_a, sl_a = radius(xyz[ai]); r_b, sl_b = radius(xyz[bi])
sep = np.linalg.norm(xyz[ai] - xyz[bi], axis=1)
sep_xy = np.linalg.norm(xyz[ai][:, :2] - xyz[bi][:, :2], axis=1)
dz = np.abs(xyz[ai][:, 2] - xyz[bi][:, 2])
r_mean = 0.5 * (r_a + r_b); z_mean = 0.5 * (xyz[ai][:, 2] + xyz[bi][:, 2])

# ---------- 2. load scored CSVs ----------
def load_csv(path):
    cols = {}
    with open(path) as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
    for k in rows[0]:
        if k == "hit":
            cols[k] = np.array([r[k].strip().lower() == "true" for r in rows])
        else:
            cols[k] = np.array([float(r[k]) for r in rows])
    return cols

ARMS = {
 "node_dense":      f"{FIN}/run_node_dense_pairs.csv",
 "radiusconf_dense":f"{FIN}/run_node-radiusconf_dense_pairs.csv",
 "radial_dense":    f"{FIN}/run_radial_dense_pairs.csv",
 "node_finer":      f"{FIN}/run_node_pairs.csv",
 "radial_finer":    f"{FIN}/run_radial_pairs.csv",
 "radiusconf_finer":f"{FIN}/run_node-radiusconf_pairs.csv",
 "node_coarse":     f"{G}/_deliverable/run_node_pairs.csv",
 "radial_coarse":   f"{G}/_deliverable/run_radial_pairs.csv",
 "ws_L1":           f"{H2H}/P4_A-windingsync-L1_pairs.csv",
 "ws_L1_raw":       f"{H2H}/P4_A-windingsync-L1-raw_pairs.csv",
 "ws_BFS":          f"{H2H}/P4_A-bfs_pairs.csv",
 "se_calibrated":   f"{G}/runs/full_calibrated_v2.4_pairs.csv",
 "se_uniform":      f"{G}/runs/full_uniform_v2.4_pairs.csv",
}
D = {k: load_csv(v) for k, v in ARMS.items()}

# ---------- 3. alignment check ----------
print("\n[align] dw_true column vs reconstructed pair dw (must be exact):")
for k, c in D.items():
    ok = len(c["dw_true"]) == len(dw) and np.array_equal(c["dw_true"], dw.astype(float))
    print(f"   {k:18s} n={len(c['dw_true']):5d}  dw_true==reconstructed: {ok}")

def M1(c):
    m = c["dw_true"] == 1
    return c["hit"][m].mean()
def MAE(c):
    return np.abs(c["dw_pred"] - c["dw_true"]).mean()
def ACC(c):
    return c["hit"].mean()

print("\n[headline] arm | M1(dw=1) | MAE | acc(all pairs)")
for k, c in D.items():
    print(f"   {k:18s} {M1(c):.4f}  {MAE(c):.4f}  {ACC(c):.4f}")

# ============================================================================
# SECTION 1 — ERROR STRUCTURE (shipped arm = node_dense)
# ============================================================================
c = D["node_dense"]
err_c = c["dw_pred"] - c["dw_true"]           # continuous residual
err_r = c["dw_pred_round"] - c["dw_true"]     # integer residual
print("\n" + "="*72)
print("SECTION 1  ERROR STRUCTURE  (arm: S-E-improved-node.dense, 8156 pairs)")
print("="*72)
print(f"signed residual (continuous): mean {err_c.mean():+.4f}  median {np.median(err_c):+.4f} "
      f" sd {err_c.std(ddof=1):.4f}  IQR [{np.percentile(err_c,25):+.3f},{np.percentile(err_c,75):+.3f}]")
print(f"signed residual (rounded)   : mean {err_r.mean():+.4f}  median {np.median(err_r):+.4f} "
      f" sd {err_r.std(ddof=1):.4f}")
neg = (err_r < 0).sum(); pos = (err_r > 0).sum(); zer = (err_r == 0).sum()
print(f"rounded residual sign split : under {neg} ({neg/len(err_r):.3f})  exact {zer} ({zer/len(err_r):.3f})  over {pos} ({pos/len(err_r):.3f})")
# one-sample t on the continuous residual
se = err_c.std(ddof=1)/np.sqrt(len(err_c))
print(f"bias test: mean {err_c.mean():+.4f} +/- {1.96*se:.4f} (95% CI, normal approx) -> "
      f"{'NOT consistent with zero' if abs(err_c.mean())>1.96*se else 'consistent with zero'}")
print(f"sign of prediction correct (dw_pred>0, all dw_true>0): {(c['dw_pred']>0).mean():.4f}")
m1 = c["dw_true"]==1
print(f"  ... on dw=1 pairs only: {(c['dw_pred'][m1]>0).mean():.4f}")

print("\n-- accuracy and bias by true dw --")
print(" dw    n    acc    mean signed resid   mean |resid|   sign-correct")
for k in range(1,7):
    m = c["dw_true"]==k
    print(f" {k}  {m.sum():5d}  {c['hit'][m].mean():.4f}   {err_c[m].mean():+8.3f}      "
          f"{np.abs(err_c[m]).mean():7.3f}      {(c['dw_pred'][m]>0).mean():.4f}")

def bin_report(val, name, nb=5, arr=None):
    arr = c if arr is None else arr
    qs = np.quantile(val, np.linspace(0,1,nb+1)); qs[-1]+=1e-9
    print(f"\n-- accuracy by {name} ({nb} quantile bins) --")
    print(f" bin  range                   n    acc     mean resid   mean dw_true")
    for k in range(nb):
        m = (val>=qs[k]) & (val<qs[k+1])
        print(f"  {k+1}  [{qs[k]:8.1f},{qs[k+1]:8.1f})  {m.sum():5d}  {arr['hit'][m].mean():.4f}  "
              f"{(arr['dw_pred']-arr['dw_true'])[m].mean():+8.3f}   {arr['dw_true'][m].mean():.2f}")
bin_report(sep, "3-D pair separation (vox)")
bin_report(r_mean, "mean radius from umbilicus (vox)")
bin_report(z_mean, "mean z (position along the scroll axis)")
bin_report(dz, "|dz| between endpoints (vox)")

# separation is confounded with dw -> control for it
print("\n-- accuracy by separation WITHIN dw=1 only (removes the dw confound) --")
mm = c["dw_true"]==1
qs = np.quantile(sep[mm], np.linspace(0,1,5+1)); qs[-1]+=1e-9
for k in range(5):
    m = mm & (sep>=qs[k]) & (sep<qs[k+1])
    print(f"  bin{k+1} [{qs[k]:7.1f},{qs[k+1]:7.1f})  n={m.sum():4d}  acc={c['hit'][m].mean():.4f}")

from scipy.stats import spearmanr, pearsonr
print(f"\nSpearman(|dw_pred|, dw_true) = {spearmanr(np.abs(c['dw_pred']), c['dw_true']).statistic:+.4f}")
print(f"Spearman(sep, dw_true)       = {spearmanr(sep, c['dw_true']).statistic:+.4f}   "
      "(how much a naive distance rule already knows)")
print(f"Spearman(|dw_pred|, dw_true) partialled on sep: "
      f"{spearmanr(np.abs(c['dw_pred']), c['dw_true']).statistic:+.4f} raw; see residual test below")
# partial spearman via ranks
def partial_sp(x,y,z):
    rx,ry,rz = [np.argsort(np.argsort(v)).astype(float) for v in (x,y,z)]
    def res(a,b):
        A=np.column_stack([b,np.ones_like(b)]); coef,*_=np.linalg.lstsq(A,a,rcond=None); return a-A@coef
    return pearsonr(res(rx,rz),res(ry,rz)).statistic
print(f"partial Spearman(|dw_pred|, dw_true | separation) = {partial_sp(np.abs(c['dw_pred']), c['dw_true'], sep):+.4f}")
print(f"  same for winding-sync L1: {partial_sp(np.abs(D['ws_L1']['dw_pred']), dw.astype(float), sep):+.4f}")
print(f"  same for S-E spacing baseline: {partial_sp(np.abs(D['se_calibrated']['dw_pred']), dw.astype(float), sep):+.4f}")

# --- how much of the residual is one global gain? (ORACLE: uses GT) ---
print("\n-- is the under-count one scalar? (oracle rescale, uses GT, NOT available to the adapter) --")
g = (c["dw_pred"]*c["dw_true"]).sum()/ (c["dw_pred"]**2).sum()   # least-squares gain on dw_pred
print(f"   least-squares gain g such that g*dw_pred ~ dw_true: g = {g:.4f}")
for gg in [1.0, g]:
    p = gg*c["dw_pred"]; hit = np.round(p)==c["dw_true"]
    m1m = c["dw_true"]==1
    print(f"   g={gg:.3f}:  M1={hit[m1m].mean():.4f}  MAE={np.abs(p-c['dw_true']).mean():.4f}  acc={hit.mean():.4f}")

# ============================================================================
# SECTION 2 — PRECISION / COVERAGE:  what the confidence buys a solver
# ============================================================================
print("\n" + "="*72)
print("SECTION 2  PRECISION / COVERAGE (top-k by confidence)")
print("="*72)

def topk_curve(conf, hit, dwt, ks=None):
    ks = ks if ks is not None else np.arange(0.05,1.001,0.05)
    order = np.argsort(-conf, kind="stable")
    out=[]
    n=len(conf)
    for k in ks:
        take = order[:max(1,int(round(k*n)))]
        m1m = dwt[take]==1
        out.append((k, len(take), hit[take].mean(),
                    hit[take].sum(), hit[take][m1m].mean() if m1m.any() else np.nan))
    return out

hit = c["hit"]; dwt = c["dw_true"]
curves = {
  "cycle-conf (shipped)":      D["node_dense"]["conf"],
  "radius-conf (neg control)": D["radiusconf_dense"]["conf"],
  "radius, sign corrected":    np.minimum(r_a, r_b),
}
print("\n k(frac)  n_kept | " + " | ".join(f"{nm}" for nm in curves))
print("                  | " + " | ".join("acc  n_correct  accdw1" for _ in curves))
rows={}
for nm,cf in curves.items():
    rows[nm]=topk_curve(cf, hit, dwt)
for r in range(len(rows["cycle-conf (shipped)"])):
    k, nk, *_ = rows["cycle-conf (shipped)"][r]
    line=f"  {k:.2f}   {nk:5d} |"
    for nm in curves:
        _,_,acc,nc,a1 = rows[nm][r]
        line += f" {acc:.3f} {int(nc):5d} {a1:.3f} |"
    print(line)
print(f"\n random / no-confidence reference: acc {hit.mean():.4f} at every k; "
      f"M1(dw=1) {hit[dwt==1].mean():.4f}")

# lift numbers
def lift(cf, frac):
    order=np.argsort(-cf,kind="stable"); take=order[:int(round(frac*len(cf)))]
    return hit[take].mean()
for nm,cf in curves.items():
    print(f" {nm:28s} top-10% acc {lift(cf,0.10):.4f}  top-20% {lift(cf,0.20):.4f}  "
          f"top-33% {lift(cf,0.3333):.4f}  bottom-33% {hit[np.argsort(cf,kind='stable')[:int(0.3333*len(cf))]].mean():.4f}")

# AUC of conf as a detector of 'hit'
def auc(score, y):
    from scipy.stats import rankdata
    r=rankdata(score); n1=y.sum(); n0=len(y)-n1
    return (r[y].sum()-n1*(n1+1)/2)/(n1*n0)
for nm,cf in curves.items():
    print(f" {nm:28s} AUC(conf -> hit) = {auc(cf,hit):.4f}   "
          f"AUC on dw=1 subset = {auc(cf[dwt==1],hit[dwt==1]):.4f}")

# what a solver would actually see: accepted constraints and their error
print("\n-- constraint quality of what gets accepted (cycle-conf) --")
order=np.argsort(-D['node_dense']['conf'],kind="stable")
for k in [0.1,0.2,0.33,0.5,1.0]:
    take=order[:int(round(k*len(order)))]
    e=(c["dw_pred"]-c["dw_true"])[take]
    print(f"  top {k:.0%}: n={len(take):5d} acc={hit[take].mean():.4f} MAE={np.abs(e).mean():.4f} "
          f"mean signed={e.mean():+.4f} within-1={(np.abs(np.round(c['dw_pred'][take])-c['dw_true'][take])<=1).mean():.4f}")
print("  full set within-1 (all pairs):",
      f"{(np.abs(c['dw_pred_round']-c['dw_true'])<=1).mean():.4f}")

# gain search done properly
print("\n-- global gain grid search (oracle, uses GT) --")
best=None
for gg in np.arange(0.5,4.01,0.05):
    p=gg*c["dw_pred"]; h=np.round(p)==c["dw_true"]
    a=h.mean()
    if best is None or a>best[1]: best=(gg,a,np.abs(p-c["dw_true"]).mean(),h[dwt==1].mean())
print(f"   best accuracy gain g={best[0]:.2f}: acc={best[1]:.4f} MAE={best[2]:.4f} M1={best[3]:.4f}"
      f"  (vs g=1: acc={hit.mean():.4f} MAE={MAE(c):.4f} M1={M1(c):.4f})")
bm=None
for gg in np.arange(0.5,4.01,0.05):
    p=gg*c["dw_pred"]; m=np.abs(p-c["dw_true"]).mean()
    if bm is None or m<bm[1]: bm=(gg,m)
print(f"   best-MAE gain g={bm[0]:.2f}: MAE={bm[1]:.4f}")
print(f"   mean dw_pred by dw_true: " + " ".join(f"{k}:{c['dw_pred'][dwt==k].mean():+.2f}" for k in range(1,7)))

# does the top-k selection just pick easy (small-dw) pairs?
print("\n-- does a confidence just select easy pairs? mean dw_true of the top-10% --")
for nm,cf in curves.items():
    take=np.argsort(-cf,kind="stable")[:816]
    print(f"   {nm:28s} mean dw_true {dwt[take].mean():.2f} (all pairs {dwt.mean():.2f})")

# bootstrap CI on the top-10% lift
rng=np.random.default_rng(0)
def boot_lift(cf, frac=0.10, B=2000):
    n=len(cf); out=np.empty(B)
    for t in range(B):
        idx=rng.integers(0,n,n)
        cfb=cf[idx]; hb=hit[idx]
        take=np.argsort(-cfb,kind="stable")[:int(frac*n)]
        out[t]=hb[take].mean()-hb.mean()
    return np.percentile(out,[2.5,50,97.5])
for nm,cf in curves.items():
    lo,md,hi=boot_lift(cf)
    print(f"   bootstrap top-10% lift over overall accuracy, {nm:28s}: {md:+.4f} [{lo:+.4f},{hi:+.4f}]")

# combined confidence
comb = (np.argsort(np.argsort(D['node_dense']['conf']))/len(hit)) + (np.argsort(np.argsort(np.minimum(r_a,r_b)))/len(hit))
print(f"\n   rank-sum(cycle, radius) AUC = {auc(comb,hit):.4f}, top-10% acc {lift(comb,0.10):.4f}")

# ============================================================================
# SECTION 3 — INDEPENDENCE OF ERRORS ACROSS ARMS
# ============================================================================
print("\n" + "="*72)
print("SECTION 3  ERROR CORRELATION BETWEEN ARMS (same 8156 pairs, same rows)")
print("="*72)
E = {k: (v["dw_pred"]-v["dw_true"]) for k,v in D.items()}
Hh= {k: v["hit"] for k,v in D.items()}
pick=["node_dense","radial_dense","ws_L1","ws_L1_raw","ws_BFS","se_calibrated"]
print("\nPearson r of signed continuous residuals:")
print("                 " + " ".join(f"{p[:12]:>13s}" for p in pick))
for a in pick:
    print(f" {a:15s} " + " ".join(f"{pearsonr(E[a],E[b]).statistic:+13.3f}" for b in pick))
print("\nSpearman rho of signed continuous residuals:")
for a in pick:
    print(f" {a:15s} " + " ".join(f"{spearmanr(E[a],E[b]).statistic:+13.3f}" for b in pick))

def phi(x,y):
    x=x.astype(float); y=y.astype(float)
    return pearsonr(x,y).statistic
print("\nPhi (Matthews) correlation of hit/miss agreement, and joint-error rates:")
base="node_dense"
for b in pick[1:]:
    ha,hb=Hh[base],Hh[b]
    both_wrong=((~ha)&(~hb)).mean(); indep=(1-ha.mean())*(1-hb.mean())
    either=((ha)|(hb)).mean()
    print(f"  {base} vs {b:14s}: phi={phi(ha,hb):+.4f}  both-wrong {both_wrong:.4f} "
          f"(independent would be {indep:.4f})  either-right {either:.4f} "
          f"(best single {max(ha.mean(),hb.mean()):.4f})")

print("\n-- mean signed residual per arm (who over/under-counts) --")
for k in pick:
    print(f"   {k:15s} mean {E[k].mean():+.3f}  median {np.median(E[k]):+.3f}  acc {Hh[k].mean():.4f}")

# ============================================================================
# SECTION 4 — ABLATIONS ALREADY ON DISK
# ============================================================================
print("\n" + "="*72)
print("SECTION 4  ABLATIONS")
print("="*72)
def cmp(a,b,label):
    ca,cb=D[a],D[b]
    print(f"\n{label}\n   {a:18s} M1 {M1(ca):.4f}  MAE {MAE(ca):.4f}  acc {ACC(ca):.4f}")
    print(f"   {b:18s} M1 {M1(cb):.4f}  MAE {MAE(cb):.4f}  acc {ACC(cb):.4f}")
    print(f"   delta (b-a)        M1 {M1(cb)-M1(ca):+.4f}  MAE {MAE(cb)-MAE(ca):+.4f}  acc {ACC(cb)-ACC(ca):+.4f}")
    ident = np.array_equal(ca["dw_pred"],cb["dw_pred"])
    print(f"   predictions byte-identical: {ident}; pairs where rounded pred differs: "
          f"{(ca['dw_pred_round']!=cb['dw_pred_round']).sum()}")

cmp("node_coarse","node_finer",  "A1  seed-snap coarse graph -> finer graphs200 nodes (same method)")
cmp("node_finer","node_dense",   "A2  point emission: one-per-GT (snap) -> core+densifier, dedup")
cmp("node_dense","radial_dense", "A3  magnitude: L2 group-sync node potential -> radial ST integration")
cmp("node_dense","radiusconf_dense","A4  confidence swap only (cycle-conf -> radius-conf)")
print(f"   AUC(conf->hit): cycle {auc(D['node_dense']['conf'],hit):.4f} vs radius "
      f"{auc(D['radiusconf_dense']['conf'],hit):.4f}")
cmp("ws_L1_raw","ws_L1",         "A5  umbilicus global-sign anchor applied to winding-sync L1 windings")
cmp("se_uniform","se_calibrated","A6  retired S-E adapter: uniform conf -> 'calibrated' conf")
print(f"   AUC(conf->hit) for the calibrated conf: {auc(D['se_calibrated']['conf'],D['se_calibrated']['hit']):.4f} "
      f"(0.5 = no information)")

print("\n-- A5b same anchor on the BFS arm --")
print(f"   ws_BFS raw   M1 {M1(load_csv(f'{H2H}/P4_A-bfs-raw_pairs.csv')):.4f}")
print(f"   ws_BFS anch. M1 {M1(D['ws_BFS']):.4f}")

# graph sizes for A1 description
import glob as _g
n_coarse=[int(np.load(f)['n_nodes']) for f in sorted(_g.glob(f"{G}/_signfix/graph_z*.npz"))]
n_fine  =[int(np.load(f)['n_nodes']) for f in sorted(_g.glob(f"{FIN}/graphs200/graph_z*.npz"))]
print(f"\n   A1 node counts per slice: coarse {n_coarse} (sum {sum(n_coarse)}) ; "
      f"finer {n_fine} (sum {sum(n_fine)})")

# ============================================================================
# SECTION 5 — PROVENANCE OF THE 0.130 BASELINE
# ============================================================================
print("\n" + "="*72)
print("SECTION 5  WHAT IS THE 0.130 BASELINE, LOCALLY?")
print("="*72)
for k in ["se_calibrated","se_uniform","ws_L1_raw","ws_L1","ws_BFS"]:
    print(f"   {k:15s} M1 {M1(D[k]):.4f}  MAE {MAE(D[k]):.4f}")

# ---- 3b: partial correlations (control for dw) and hit-level agreement ------
print("\n-- partial Spearman(err_ours, err_other | dw_true) --")
def _rk(v): return np.argsort(np.argsort(v)).astype(float)
def _res(x, z):
    A = np.column_stack([z, np.ones_like(z)]); k,*_ = np.linalg.lstsq(A, x, rcond=None)
    return x - A @ k
def partial(x, y, z): return pearsonr(_res(_rk(x), _rk(z)), _res(_rk(y), _rk(z))).statistic
for k in ["radial_dense","ws_L1","ws_BFS","ws_L1_raw","se_calibrated"]:
    print(f"   node_dense vs {k:15s} raw {spearmanr(E['node_dense'],E[k]).statistic:+.4f}"
          f"   partial|dw {partial(E['node_dense'],E[k],c['dw_true']):+.4f}")
print("   CONTROL, two arms that are the same winding-sync solve:")
print(f"     se_calibrated vs ws_L1_raw   raw {spearmanr(E['se_calibrated'],E['ws_L1_raw']).statistic:+.4f}"
      f"   partial|dw {partial(E['se_calibrated'],E['ws_L1_raw'],c['dw_true']):+.4f}")

print("\n-- hit/miss agreement on dw=1 pairs only --")
m1msk = c["dw_true"] == 1
for k in ["radial_dense","ws_L1","ws_L1_raw","se_calibrated"]:
    ha, hb = Hh["node_dense"][m1msk], Hh[k][m1msk]
    print(f"   node_dense vs {k:15s} phi {pearsonr(ha.astype(float),hb.astype(float)).statistic:+.4f}"
          f"  both-right {(ha&hb).mean():.4f} (independent {ha.mean()*hb.mean():.4f})"
          f"  either-right {(ha|hb).mean():.4f}")

print("\n-- accuracy by radius decile (pair minimum radius) --")
rp = np.minimum(r_a, r_b)
qq = np.quantile(rp, np.linspace(0,1,11)); qq[-1] += 1e-9
for i in range(10):
    m = (rp>=qq[i]) & (rp<qq[i+1])
    print(f"   decile {i+1:2d}  r [{qq[i]:6.0f},{qq[i+1]:6.0f})  n={m.sum():4d}  acc {c['hit'][m].mean():.4f}")
print(f"   overall {c['hit'].mean():.4f}")
