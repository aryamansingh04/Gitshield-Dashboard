#!/usr/bin/env python3
"""
DA3 step 2 - statistical analysis of the held-out test predictions produced by step 1.

Outputs (DA3/results):
  model_ci.csv                 95 % percentile-bootstrap CIs (accuracy, macro P/R/F1, weighted F1, macro ROC-AUC)
  statistical_comparison.csv   paired comparisons: McNemar exact test, Holm-adjusted p, odds ratio, d_z,
                               paired-bootstrap CIs for accuracy / macro-F1 differences, practical-significance label
  error_analysis.csv           off-diagonal confusion cells (who is confused with whom) for every model
  class_error_summary.csv      per-class TP/FP/FN/TN, FPR, FNR (one-vs-rest) for every model

Design notes
 * All resampling is PAIRED: the same bootstrap row indices are applied to every model, so differences
   between models are evaluated on identical resampled test sets.
 * McNemar's test uses the EXACT binomial form on the discordant pairs (b, c).
 * Holm-Bonferroni correction is applied within each comparison family (family sizes are in the output).
 * Practical significance: |accuracy difference| >= 1 percentage point (SESOI, stated a priori here).
"""
import itertools, json, time
import numpy as np
import pandas as pd
from scipy.stats import binomtest, rankdata
from statsmodels.stats.multitest import multipletests
from common import CLASSES, RES, SEED

B = 2000
SESOI = 0.01                       # smallest accuracy difference regarded as practically meaningful
T0 = time.time()
log = lambda m: print(f"[{time.time() - T0:6.1f}s] {m}", flush=True)

z = np.load(RES / "cache" / "test_predictions.npz")
y = z["y_test"]; n = len(y)
comp = pd.read_csv(RES / "model_comparison.csv")
models = comp["Model"].tolist()                       # already sorted by macro-F1 (rank 1 = best)
P = {m: z[f"pred::{m}"] for m in models}
S = {m: z[f"score::{m}"] for m in models}
ref = models[0]
log(f"{len(models)} models, n_test={n}, reference (rank-1 by macro-F1) = {ref}")

# ---------------------------------------------------------------- paired bootstrap
rng = np.random.default_rng(SEED)
IDX = rng.integers(0, n, size=(B, n), dtype=np.int32)


def cm_batch(p):
    code = (y[IDX] * 3 + p[IDX]) + 9 * np.arange(B, dtype=np.int32)[:, None]
    return np.bincount(code.ravel(), minlength=9 * B).reshape(B, 3, 3)


def metrics_from_cm(cm):
    tp = np.einsum("bii->bi", cm).astype(float)
    pred_n, true_n = cm.sum(1), cm.sum(2)
    prec = np.divide(tp, pred_n, out=np.zeros_like(tp), where=pred_n > 0)
    rec = np.divide(tp, true_n, out=np.zeros_like(tp), where=true_n > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(tp), where=(prec + rec) > 0)
    return {"Accuracy": tp.sum(1) / cm.sum((1, 2)), "Precision_macro": prec.mean(1), "Recall_macro": rec.mean(1),
            "F1_macro": f1.mean(1), "F1_weighted": (f1 * true_n).sum(1) / true_n.sum(1)}


def auc_fast(yb, sb):
    r = rankdata(sb)
    npos = yb.sum(); nneg = len(yb) - npos
    return (r[yb == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)


boot = {}
for m in models:
    d = metrics_from_cm(cm_batch(P[m]))
    aucs = np.empty(B)
    for b in range(B):
        ib = IDX[b]; yb = y[ib]
        aucs[b] = np.mean([auc_fast((yb == c).astype(int), S[m][ib, c]) for c in range(3)])
    d["ROC_AUC_macro_ovr"] = aucs
    boot[m] = d
    log(f"bootstrap done: {m}")

point = comp.set_index("Model")
col_map = {"Accuracy": "Accuracy", "Precision_macro": "Precision_macro", "Recall_macro": "Recall_macro",
           "F1_macro": "F1_macro", "F1_weighted": "F1_weighted", "ROC_AUC_macro_ovr": "ROC_AUC_macro_ovr"}
ci_rows = []
for m in models:
    for k, c in col_map.items():
        lo, hi = np.percentile(boot[m][k], [2.5, 97.5])
        ci_rows.append({"Model": m, "Metric": k, "Estimate": point.loc[m, c], "CI_low": lo, "CI_high": hi,
                        "Boot_SE": boot[m][k].std(ddof=1), "B": B})
pd.DataFrame(ci_rows).round(6).to_csv(RES / "model_ci.csv", index=False)

# ---------------------------------------------------------------- paired tests
def compare(a, b_, family):
    ca, cb = (P[a] == y), (P[b_] == y)
    n10, n01 = int((ca & ~cb).sum()), int((~ca & cb).sum())     # A right/B wrong, A wrong/B right
    p_exact = binomtest(n10, n10 + n01, 0.5).pvalue if (n10 + n01) > 0 else 1.0
    diff = ca.astype(float) - cb.astype(float)
    dacc = diff.mean()
    dz = dacc / diff.std(ddof=1) if diff.std(ddof=1) > 0 else 0.0
    ba, bb = boot[a], boot[b_]
    da = ba["Accuracy"] - bb["Accuracy"]; df1 = ba["F1_macro"] - bb["F1_macro"]
    return {"Family": family, "Model_A": a, "Model_B": b_,
            "Acc_A": point.loc[a, "Accuracy"], "Acc_B": point.loc[b_, "Accuracy"], "Acc_Diff_A_minus_B": dacc,
            "Acc_Diff_CI_low": np.percentile(da, 2.5), "Acc_Diff_CI_high": np.percentile(da, 97.5),
            "F1_Diff_A_minus_B": point.loc[a, "F1_macro"] - point.loc[b_, "F1_macro"],
            "F1_Diff_CI_low": np.percentile(df1, 2.5), "F1_Diff_CI_high": np.percentile(df1, 97.5),
            "A_right_B_wrong": n10, "A_wrong_B_right": n01,
            "Odds_Ratio_b_over_c": (n10 / n01) if n01 > 0 else np.inf,
            "Cohen_dz": dz, "McNemar_exact_p": p_exact}


rows = [compare(ref, m, f"Reference ({ref}) vs every other model") for m in models[1:]]
leaders = []                                     # leading distinct model families: best entry per family, top 6
for m in models:
    f = point.loc[m, "Family"]
    if f not in [point.loc[x, "Family"] for x in leaders]:
        leaders.append(m)
leaders = leaders[:6]
rows += [compare(a, b_, "Pairwise among leading model families (best variant of each)")
         for a, b_ in itertools.combinations(leaders, 2)]
res = pd.DataFrame(rows)
res["Holm_p"] = np.nan
for fam, g in res.groupby("Family"):
    res.loc[g.index, "Holm_p"] = multipletests(g["McNemar_exact_p"], method="holm")[1]
    res.loc[g.index, "Family_Size"] = len(g)


def label(r):
    sig = r["Holm_p"] < 0.05
    big = abs(r["Acc_Diff_A_minus_B"]) >= SESOI
    if not sig:
        return "No significant difference after Holm correction"
    return ("Significant and practically meaningful (>= 1 pp)" if big
            else "Statistically significant but practically small (< 1 pp)")


res["Interpretation"] = res.apply(label, axis=1)
res.round(8).to_csv(RES / "statistical_comparison.csv", index=False)
log("statistical_comparison.csv written")

# ---------------------------------------------------------------- error analysis
err_rows, cls_rows = [], []
for m in models:
    cm = np.zeros((3, 3), int)
    np.add.at(cm, (y, P[m]), 1)
    n_err = cm.sum() - np.trace(cm)
    for a in range(3):
        for b in range(3):
            if a != b:
                err_rows.append({"Model": m, "Actual": CLASSES[a], "Predicted": CLASSES[b], "Count": int(cm[a, b]),
                                 "Share_of_all_errors": cm[a, b] / n_err if n_err else 0,
                                 "Error_Type": "Adjacent classes" if abs(a - b) == 1 else "Low<->High (non-adjacent)"})
    for c in range(3):
        tp = cm[c, c]; fn = cm[c].sum() - tp; fp = cm[:, c].sum() - tp; tn = cm.sum() - tp - fn - fp
        cls_rows.append({"Model": m, "Class": CLASSES[c], "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn),
                         "FPR": fp / (fp + tn), "FNR": fn / (fn + tp), "Precision": tp / (tp + fp) if tp + fp else 0,
                         "Recall": tp / (tp + fn)})
pd.DataFrame(err_rows).round(6).to_csv(RES / "error_analysis.csv", index=False)
pd.DataFrame(cls_rows).round(6).to_csv(RES / "class_error_summary.csv", index=False)

e = pd.DataFrame(err_rows)
adj = e.groupby(["Model", "Error_Type"])["Count"].sum().unstack(fill_value=0)
adj["Adjacent_share"] = adj["Adjacent classes"] / adj.sum(axis=1)
log("share of errors between ADJACENT classes (reference model): "
    f"{adj.loc[ref, 'Adjacent_share']:.4f}")
log("DONE")
print(pd.read_csv(RES / "model_ci.csv").query("Metric in ['Accuracy','F1_macro','ROC_AUC_macro_ovr']")
      .pivot(index="Model", columns="Metric", values="CI_low").round(4).head(5))
