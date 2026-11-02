#!/usr/bin/env python3
"""
DA3 step 5 - assemble the (small) set of CSV/JSON files that the R Shiny dashboard reads.
The dashboard never retrains anything: it only reads DA3/dashboard/data/*.

repository_explorer.csv contains the 16,098 HELD-OUT TEST repositories (the only rows for which an
out-of-sample prediction exists), their metadata, the heuristic risk score / class (the training label) and
the predicted class + class probabilities of the best model. Heuristic and predicted values are kept in
separate, clearly named columns.
"""
import json, shutil
import numpy as np
import pandas as pd
from common import CLASSES, RES, DA3, DA2_OUT, load_frame

OUT = DA3 / "dashboard" / "data"
OUT.mkdir(parents=True, exist_ok=True)

comp = pd.read_csv(RES / "model_comparison.csv")
comp = comp.sort_values(["F1_macro", "ROC_AUC_macro_ovr"], ascending=False).reset_index(drop=True)
comp["Rank_F1"] = np.arange(1, len(comp) + 1)
best = comp.loc[0, "Model"]
comp.to_csv(RES / "model_comparison.csv", index=False)       # keep results/ and dashboard consistent

z = np.load(RES / "cache" / "test_predictions.npz")
df, t_low, t_high = load_frame()
ids = z["test_ids"]
ex = df.set_index("row_id").loc[ids].reset_index()
sc = z[f"score::{best}"]
ex_out = pd.DataFrame({
    "row_id": ex["row_id"], "name_with_owner": ex["name_with_owner"],
    "primary_language": ex["primary_language"], "license": ex["license"],
    "stars": ex["stars"], "forks": ex["forks"], "watchers": ex["watchers"], "issues": ex["issues"],
    "pull_requests": ex["pull_requests"], "commits": ex["commits"],
    "repository_age_years": ex["repository_age_years"].round(2), "days_since_update": ex["days_since_update"].round(0),
    "is_archived": ex["is_archived"], "has_license": ex["has_license"], "has_code_of_conduct": ex["has_code_of_conduct"],
    "heuristic_risk_score": ex["repository_risk_score"].round(4),
    "heuristic_risk_class": ex["risk_class"].astype(str),
    "predicted_risk_class": [CLASSES[i] for i in z[f"pred::{best}"]],
    "prob_low": sc[:, 0].round(4), "prob_medium": sc[:, 1].round(4), "prob_high": sc[:, 2].round(4),
})
ex_out["prediction_correct"] = (ex_out["heuristic_risk_class"] == ex_out["predicted_risk_class"]).astype(int)
ex_out["predicting_model"] = best
ex_out.to_csv(OUT / "repository_explorer.csv", index=False)

for f in ["model_comparison", "class_metrics", "confusion_matrix", "feature_importance", "statistical_comparison",
          "model_ci", "error_analysis", "class_error_summary", "feature_importance_agreement",
          "leakage_formula_overlap", "leakage_boundary_error", "leakage_ablation"]:
    shutil.copy(RES / f"{f}.csv", OUT / f"{f}.csv")

ci = pd.read_csv(RES / "model_ci.csv").set_index(["Model", "Metric"])
b = comp.loc[0]
cls_counts = df["risk_class"].value_counts().reindex(CLASSES)
cfg = json.load(open(RES / "run_config.json"))
overview = {
    "n_repositories": int(len(df)), "n_train": cfg["n_train"], "n_test": cfg["n_test"],
    "n_models_evaluated": int(len(comp)), "n_baseline_models": int((comp.Stage == "Baseline").sum()),
    "n_tuned_models": int((comp.Stage == "Tuned").sum()),
    "best_model": best,
    "selection_rule": "Highest macro-F1 on the held-out test set (ties broken by macro ROC-AUC). "
                      "Note: the test set is also used to rank 17 candidates, so the winner's score is slightly optimistic.",
    "best_accuracy": float(b.Accuracy), "best_f1_macro": float(b.F1_macro), "best_roc_auc": float(b.ROC_AUC_macro_ovr),
    "best_accuracy_ci": [float(ci.loc[(best, "Accuracy"), "CI_low"]), float(ci.loc[(best, "Accuracy"), "CI_high"])],
    "best_f1_ci": [float(ci.loc[(best, "F1_macro"), "CI_low"]), float(ci.loc[(best, "F1_macro"), "CI_high"])],
    "best_auc_ci": [float(ci.loc[(best, "ROC_AUC_macro_ovr"), "CI_low"]), float(ci.loc[(best, "ROC_AUC_macro_ovr"), "CI_high"])],
    "class_counts": {k: int(v) for k, v in cls_counts.items()},
    "thresholds": {"low_below": t_low, "high_from": t_high},
    "reconstruction": json.load(open(RES / "leakage_reconstruction.json")),
    "boundary_summary": json.load(open(RES / "leakage_boundary_summary.json")),
}
json.dump(overview, open(OUT / "overview.json", "w"), indent=2)
print("exported:", sorted(p.name for p in OUT.iterdir()))
print("best model:", best, "| explorer rows:", len(ex_out))
