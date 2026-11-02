#!/usr/bin/env python3
"""Generate every report/presentation figure from DA3/results/*.csv (no hard-coded values).
Run from the repository root:  python DA3/report/make_figures.py"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).resolve().parent.parent / "results"
OUT = Path(__file__).resolve().parent / "figures"; OUT.mkdir(exist_ok=True)
NAVY, STEEL, RED, TEAL, GOLD = "#1F3A5F", "#8DA9C4", "#E76F51", "#2A9D8F", "#E9C46A"
CLASSES = ["Low Risk", "Medium Risk", "High Risk"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})

comp = pd.read_csv(R / "model_comparison.csv"); ci = pd.read_csv(R / "model_ci.csv")
best = comp.loc[0, "Model"]

# 1 model comparison with CI
d = comp[["Model", "Stage"]].merge(ci[ci.Metric == "F1_macro"], on="Model").sort_values("Estimate")
fig, ax = plt.subplots(figsize=(7.5, 5.6))
ax.barh(d.Model, d.Estimate, color=[NAVY if s == "Tuned" else STEEL for s in d.Stage],
        xerr=[d.Estimate - d.CI_low, d.CI_high - d.Estimate], error_kw=dict(ecolor="#444", lw=1, capsize=2))
for y, v in enumerate(d.Estimate): ax.text(v + 0.004, y, f"{v:.4f}", va="center", fontsize=8)
ax.set_xlim(0.7, 1.0); ax.set_xlabel("Macro-F1 on held-out test set (95% bootstrap CI)")
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=STEEL), plt.Rectangle((0, 0), 1, 1, color=NAVY)], labels=["Baseline", "Tuned"], loc="lower right", frameon=False)
fig.tight_layout(); fig.savefig(OUT / "fig1_model_comparison.png"); plt.close(fig)

# 2 confusion matrix of best model
cm = pd.read_csv(R / "confusion_matrix.csv").query("Model == @best")
M = cm.pivot(index="Actual", columns="Predicted", values="Count").loc[CLASSES, CLASSES]
P = M.div(M.sum(1), axis=0)
fig, ax = plt.subplots(figsize=(5, 4.2)); ax.imshow(P.values, cmap="Blues", vmin=0, vmax=1)
for i in range(3):
    for j in range(3):
        ax.text(j, i, f"{M.values[i, j]:,}\n({P.values[i, j]*100:.1f}%)", ha="center", va="center", color="white" if P.values[i, j] > .5 else "black", fontsize=9)
ax.set_xticks(range(3), CLASSES); ax.set_yticks(range(3), CLASSES); ax.set_xlabel("Predicted"); ax.set_ylabel("Actual (heuristic label)")
ax.spines[:].set_visible(False); ax.set_title(best, fontsize=10); fig.tight_layout(); fig.savefig(OUT / "fig2_confusion_best.png"); plt.close(fig)

# 3 per-class metrics for leading models
cl = pd.read_csv(R / "class_metrics.csv")
lead = [best, "HistGradientBoosting", "Gradient Boosting (Tuned)", "Extra Trees", "Logistic Regression"]
fig, axs = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
cols = [NAVY, STEEL, TEAL, GOLD, RED]
for ax, met in zip(axs, ["Precision", "Recall", "F1"]):
    for k, m in enumerate(lead):
        v = cl[cl.Model == m].set_index("Class").loc[CLASSES, met]
        ax.bar(np.arange(3) + (k - 2) * 0.16, v, 0.16, label=m, color=cols[k])
    ax.set_xticks(range(3), [c.split()[0] for c in CLASSES]); ax.set_title(met); ax.set_ylim(0.8, 1.0)
axs[0].legend(fontsize=7, frameon=False, loc="lower left"); fig.tight_layout(); fig.savefig(OUT / "fig3_per_class.png"); plt.close(fig)

# 4 error patterns
e = pd.read_csv(R / "error_analysis.csv")
fig, ax = plt.subplots(figsize=(7, 3.6))
pats = e[e.Model == best].assign(P=lambda x: x.Actual.str.split().str[0] + "→" + x.Predicted.str.split().str[0])
order = pats.sort_values("Count").P.tolist()
left = np.zeros(len(lead))
for p, c in zip(order[::-1], [NAVY, STEEL, TEAL, GOLD, "#B9C6D6", RED]):
    v = [e[(e.Model == m)].assign(P=lambda x: x.Actual.str.split().str[0] + "→" + x.Predicted.str.split().str[0]).set_index("P").loc[p, "Share_of_all_errors"] * 100 for m in lead]
    ax.barh(lead, v, left=left, label=p, color=c); left += v
ax.invert_yaxis(); ax.set_xlabel("% of each model's errors"); ax.legend(ncol=3, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, 1.3))
fig.tight_layout(); fig.savefig(OUT / "fig4_error_patterns.png"); plt.close(fig)

# 5 paired accuracy difference vs reference
s = pd.read_csv(R / "statistical_comparison.csv"); s = s[s.Family.str.startswith("Reference")].sort_values("Acc_Diff_A_minus_B")
fig, ax = plt.subplots(figsize=(7, 5))
ax.errorbar(s.Acc_Diff_A_minus_B * 100, s.Model_B, xerr=[(s.Acc_Diff_A_minus_B - s.Acc_Diff_CI_low) * 100, (s.Acc_Diff_CI_high - s.Acc_Diff_A_minus_B) * 100],
            fmt="o", color=NAVY, ecolor=STEEL, capsize=2)
ax.axvline(0, color="#444", lw=.8); ax.axvline(1, color=RED, lw=.8, ls="--"); ax.text(1.05, 0.2, "1 pp\nmargin", color=RED, fontsize=8)
ax.set_xlabel(f"Accuracy difference, {best} minus comparator (percentage points, 95% paired-bootstrap CI)")
fig.tight_layout(); fig.savefig(OUT / "fig5_paired_differences.png"); plt.close(fig)

# 6 permutation importance, three models
fi = pd.read_csv(R / "feature_importance.csv"); fi = fi[fi.Method.str.startswith("Perm")]
ms = ["MLP Neural Network", "HistGradientBoosting", "Random Forest (Tuned)"]
top = fi[fi.Model == best].nlargest(10, "Importance").Feature.tolist()[::-1]
fig, ax = plt.subplots(figsize=(7.5, 4.6))
for k, m in enumerate(ms):
    v = fi[fi.Model == m].set_index("Feature").reindex(top)
    ax.barh(np.arange(len(top)) + (k - 1) * 0.27, v.Importance, 0.27, xerr=v.Std, label=m, color=[NAVY, STEEL, TEAL][k], error_kw=dict(lw=.8))
ax.set_yticks(range(len(top)), top); ax.set_xlabel("Permutation importance (drop in macro-F1)"); ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout(); fig.savefig(OUT / "fig6_feature_importance.png"); plt.close(fig)

# 7 boundary error
b = pd.read_csv(R / "leakage_boundary_error.csv")
fig, ax = plt.subplots(figsize=(5.8, 3.4)); ax.bar(b.distance_to_nearest_threshold, b.error_rate * 100, color=RED)
for i, (r, n) in enumerate(zip(b.error_rate, b.n_test_rows)): ax.text(i, r * 100 + .4, f"{r*100:.1f}%", ha="center", fontsize=8)
ax.set_xlabel("Distance of risk score to nearest class cut-off"); ax.set_ylabel("Error rate (%)"); fig.tight_layout(); fig.savefig(OUT / "fig7_boundary_error.png"); plt.close(fig)

# 8 ablation
a = pd.read_csv(R / "leakage_ablation.csv"); a["Set"] = a.Predictor_set.str[0]
fig, ax = plt.subplots(figsize=(6.4, 3.8)); mods = ["Dummy (class prior)", "Logistic Regression", "HistGradientBoosting", "MLP Neural Network"]
for k, m in enumerate(mods):
    v = a[a.Model == m].sort_values("Set").F1_macro
    ax.bar(np.arange(3) + (k - 1.5) * 0.2, v, 0.2, label=m, color=[ "#BBBBBB", TEAL, STEEL, NAVY][k])
ax.set_xticks(range(3), ["A: full DA2\npredictors", "B: without licence/CoC/\narchived/recency", "C: without any\nformula input"]); ax.set_ylabel("Macro-F1 (test)"); ax.set_ylim(0, 1)
ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper right"); fig.tight_layout(); fig.savefig(OUT / "fig8_ablation.png"); plt.close(fig)

# 9 CV (if available)
if (R / "cv_fold_scores.csv").exists():
    cv = pd.read_csv(R / "cv_fold_scores.csv"); order = cv.groupby("Model").F1_macro.mean().sort_values().index
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for i, m in enumerate(order):
        v = cv[cv.Model == m].F1_macro; ax.scatter(v, [i] * len(v), color=STEEL, s=18); ax.scatter(v.mean(), i, color=NAVY, marker="D", s=36)
    ax.set_yticks(range(len(order)), order); ax.set_xlabel("Macro-F1 per fold (diamond = mean), 5-fold CV on training split")
    fig.tight_layout(); fig.savefig(OUT / "fig9_cv.png"); plt.close(fig)
print("figures:", sorted(p.name for p in OUT.iterdir()))
