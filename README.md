# ST winding adapter

A generator of **relative winding constraints** for the Herculaneum scrolls: given two
points inside a scroll volume, how many sheet crossings lie between them.

It gets that number out of the CT image itself — by integrating the lamina normal from
the **structure tensor** along the path between the two points and counting the sheets
actually crossed. It therefore makes **no fixed-pitch assumption**: no "one winding is
N micrometres" constant enters anywhere.

Output is the plain one-file adapter interface used by the public
[`constraint-gauge`](https://github.com/pscamillo/constraint-gauge) bench — a point
list, one winding number per point, one confidence per point:

```json
{"name": "...", "points_xyz": [[x, y, z], ...], "winding": [...], "conf": [...]}
```

## Why you might care

Winding constraints are a crowded corner of this project. There are several generators
already, and this one is not uniformly better than all of them. Two things may still
make it worth ten minutes:

* **It is a different signal path.** Everything else in this niche starts from a spacing
  or pitch estimate. This starts from image structure. Its errors should therefore be
  largely uncorrelated with the spacing-based estimators — which is what you want if you
  are ensembling, cross-checking, or looking for where a solver quietly goes wrong.
* **Its confidence carries information.** The confidence is cycle-consistency — how many
  winding discontinuities accumulate around closed paths through a point. On the bench it
  was monotone with accuracy, which is not true of every confidence signal (including one
  of ours, see the caveats).

If you only need a winding number and already trust your pitch, you probably do not need
this.

## Scores

Scored by the **bench author**, on his own machine, on the PHerc Paris 4 ground truth
(8156 within-collection pairs at dw 1–6), 30 July 2026. Labels follow the bench's own
convention so the numbers keep their context.

| adapter file | arm | scorable | M1 (exact on dw=1) | MAE | confidence |
|---|---|---|---|---|---|
| `S-E-improved-node.dense.json` | ST + L2 group-sync, cycle-conf | 8156 / 8156 (coverage 1.000) | **0.295** | 2.587 | monotone, 0.11 → 0.24 across deciles |
| `S-E-improved-node-radiusconf.dense.json` | same windings, radius as conf | 8156 / 8156 | 0.295 | 2.587 | **anti-calibrated, 0.29 → 0.01 — do not use** |
| `S-E-improved-radial.dense.json` | ST radial | 8156 / 8156 | 0.233 | 3.525 | flat |

Context for those numbers, in the bench author's framing:

* **M1 0.295 is roughly 2.3× the L1 baseline** (0.130) on the same pairs. That baseline
  figure is his; it is not reproducible from this repository alone.
* The score is **identical at all three matching tolerances** (τ/2, τ, 2τ), so the point
  density this submission uses introduces no selection bias — an earlier, sparser
  submission of ours was blocked by the bench's node-gap gate exactly because it could
  have.
* `cycle-conf` was, in his words, the best-calibrated confidence signal the bench had
  measured at that point, including his own estimator. That is a statement about one
  bench on one scroll at one date, and two further submissions have arrived since.

The radius-conf arm is kept in the repository deliberately as a clean negative: identical
windings, a confidence that inverts. It is what a plausible-looking confidence signal
looks like when it is wrong.

## Reproduce it yourself

The three JSON files are the whole submission; nothing of ours is needed to score them.

```sh
git clone https://github.com/pscamillo/constraint-gauge
cd constraint-gauge
python run_gauge.py --gt <paris4 ground-truth json> \
    --adapter json:/path/to/S-E-improved-node.dense.json \
    --pitch-um 187.3 --um-per-vox 2.4 --out-prefix repro
```

The runner writes `repro_pairs.csv` and `repro_summary.json`; every figure in the table
above is read out of those, none is typed by hand.

One practical note: the ground truth is the human winding annotation over the published
Paris 4 point collections, and as of our last look at the bench repository the GT file
itself was not committed there — ask the bench author which file to point `--gt` at. The
`--pitch-um` value only affects the bench's own conversions, not this adapter's output.

## Method, briefly

1. **Magnitude.** Integrate the lamina normal field (from the structure tensor of the
   volume) along the path between two points; the accumulated crossing count is the
   relative winding. No spacing constant is used.
2. **Sign within a collection.** Relative signs are resolved by L2 group synchronisation
   over the raw edge deltas — a least-squares fit over the whole graph rather than a
   spanning-tree walk, so a single bad edge does not flip a branch.
3. **Global orientation.** One bit per scroll, anchored on the umbilicus. See caveats.
4. **Confidence.** Cycle-consistency: discontinuities accumulated around closed paths.

## Honest caveats

* **One bench, one scroll, one date.** Everything above is PHerc Paris 4, July 2026.
  Nothing here has been tested against a second scroll's ground truth.
* **The global sign does not transfer.** The whole sign problem reduces to one global
  orientation bit per scroll. The umbilicus anchor is geometry-lucky on Paris 4 and is
  **not** a general GT-free resolver; on a new scroll it needs one bit of ground truth
  (two annotated points) or another anchor.
* **radius-conf is anti-calibrated.** Listed above; do not use it as a confidence.
* **M1 0.295 is not a solved problem.** Seven pairs in ten are still wrong at dw=1. This
  is a useful independent signal, not a winding solver.
* **The generator source is not in this repository** — only the three submissions, the
  method description and the numbers. If you want to run the extraction on another
  scroll, open an issue and it can be cleaned up and added.

## How this was made, and what a human checked

Stating this plainly, since it now matters on the Vesuvius Discord: **the code and this
write-up were produced by a Claude agent.** What that does and does not mean here:

* **The scores are not the model's own report of itself.** They come from an independent
  run by the bench author on his own machine, against ground truth we do not hold, with
  criteria hashed and sealed before any external generator was measured. No correction to
  this work came from the model auditing itself.
* **The scores re-run.** The three files in `adapters/` were re-scored on the public
  runner before this repository was published, and reproduce the table exactly: 0.295 /
  2.587 / coverage 1.000 for the node arm, 0.233 / 3.525 for radial, deciles 0.107 → 0.243.
* **What I did myself** (Aleksei): chose what to submit and sent the files to the bench
  author directly; read his summary and the per-pair CSV he returned; and I am the one
  publishing this, caveats included, including the negative arm that makes us look worse.
  I have not independently re-derived the structure-tensor integration by hand.

If anything here reads as overclaimed, tell me and I will correct it in place.

## Credit and licence

Author: **Aleksei Drobkov** — `alyalya1404` on the Vesuvius Challenge Discord,
[@AlexeyDrobkovStrikesBack](https://github.com/AlexeyDrobkovStrikesBack) on GitHub.

Scored on `constraint-gauge` by [@pscamillo](https://github.com/pscamillo); the bench and
the pitch atlas are his work. Winding constraint solving builds on `winding-sync`
(abundantjoe).

MIT — see `LICENSE`.
