#!/usr/bin/env python3
"""
DA3 step 1 - reproducible final model comparison.

* Re-fits the 12 DA2 classifiers (DA2 hyper-parameters) and the 5 tuned variants
  (hyper-parameters read from outputs/best_hyperparameters.json - the DA2 grid searches are NOT repeated).
* All metrics are computed on the SAME held-out 20 % test split (stratified, random_state=42).
* Saves consolidated CSVs and a prediction cache for the statistical-analysis step.
* Compares every re-computed headline metric with the value stored in the DA2 outputs
  (outputs/model_comparison.csv) and flags discrepancies instead of silently replacing them.

Run from the repository root:  python DA3/evaluation/01_train_and_evaluate.py
"""
import json, time
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support, roc_auc_score)
from common import (CLASSES, DA2_OUT, RES, base_models, get_scores, prepare, tuned_models, SEED)

T0 = time.time()
log = lambda m: print(f"[{time.time() - T0:7.1f}s] {m}", flush=True)

D = prepare()
Xtr, Xte, ytr, yte = D["Xtr"], D["Xte"], D["y_train"], D["y_test"]
log(f"train={len(ytr)} test={len(yte)} selected_features={len(D['sel_names'])}")

models = {**{k: (v, "Baseline") for k, v in base_models().items()},
          **{k: (v, "Tuned") for k, v in tuned_models().items()}}

rows, class_rows, cm_rows, preds, scores, failures, fitted = [], [], [], {}, {}, [], {}
ybin = np.eye(3)[yte]
for name, (mdl, stage) in models.items():
    try:
        t = time.time(); mdl.fit(Xtr, ytr); fit_t = time.time() - t
        t = time.time(); p = mdl.predict(Xte); pred_t = time.time() - t
        s = get_scores(mdl, Xte)
        pr, rc, f1, sup = precision_recall_fscore_support(yte, p, labels=[0, 1, 2], zero_division=0)
        row = {
            "Model": name, "Family": name.replace(" (Tuned)", ""), "Stage": stage,
            "Accuracy": accuracy_score(yte, p),
            "Precision_macro": pr.mean(), "Recall_macro": rc.mean(), "F1_macro": f1.mean(),
            "Precision_weighted": precision_recall_fscore_support(yte, p, average="weighted", zero_division=0)[0],
            "Recall_weighted": precision_recall_fscore_support(yte, p, average="weighted", zero_division=0)[1],
            "F1_weighted": f1_score(yte, p, average="weighted", zero_division=0),
            "ROC_AUC_macro_ovr": roc_auc_score(yte, s, multi_class="ovr", average="macro"),
            "Avg_Precision_macro": average_precision_score(ybin, s, average="macro"),
            "Train_Accuracy": accuracy_score(ytr, mdl.predict(Xtr)),
            "Fit_Time_s": fit_t, "Predict_Time_s": pred_t,
        }
        for i, c in enumerate(CLASSES):
            k = c.split()[0]
            row[f"Precision_{k}"], row[f"Recall_{k}"], row[f"F1_{k}"] = pr[i], rc[i], f1[i]
            row[f"ROC_AUC_{k}"] = roc_auc_score(yte == i, s[:, i])
            class_rows.append({"Model": name, "Class": c, "Precision": pr[i], "Recall": rc[i], "F1": f1[i],
                               "Support": int(sup[i]), "ROC_AUC_ovr": row[f"ROC_AUC_{k}"]})
        cm = confusion_matrix(yte, p, labels=[0, 1, 2])
        for a in range(3):
            for b in range(3):
                cm_rows.append({"Model": name, "Actual": CLASSES[a], "Predicted": CLASSES[b],
                                "Count": int(cm[a, b]), "Row_Pct": cm[a, b] / cm[a].sum()})
        rows.append(row); preds[name] = p; scores[name] = s; fitted[name] = mdl
        log(f"{name:32s} acc={row['Accuracy']:.4f} f1={row['F1_macro']:.4f} auc={row['ROC_AUC_macro_ovr']:.4f} fit={fit_t:.1f}s")
    except Exception as e:                       # never silently substitute DA2 numbers
        failures.append({"Model": name, "Error": str(e)})
        log(f"!! {name} FAILED: {e}")

comp = pd.DataFrame(rows).sort_values("F1_macro", ascending=False).reset_index(drop=True)
comp.insert(0, "Rank_F1", np.arange(1, len(comp) + 1))

# ---- verification against stored DA2 results ------------------------------------------------
da2 = pd.read_csv(DA2_OUT / "model_comparison.csv").set_index("Model")
chk = comp.set_index("Model")[["Accuracy", "F1_macro", "ROC_AUC_macro_ovr"]].join(
    da2[["Accuracy", "F1", "ROC_AUC"]].rename(columns=lambda c: "DA2_" + c))
chk["dAcc"] = chk["Accuracy"] - chk["DA2_Accuracy"]
chk["dF1"] = chk["F1_macro"] - chk["DA2_F1"]
chk["dAUC"] = chk["ROC_AUC_macro_ovr"] - chk["DA2_ROC_AUC"]
chk.round(5).to_csv(RES / "reproducibility_check_vs_DA2.csv")
comp = comp.merge(da2[["F1"]].rename(columns={"F1": "DA2_Reported_F1"}), left_on="Model", right_index=True, how="left")
comp["Matches_DA2_within_0.002"] = (comp["F1_macro"] - comp["DA2_Reported_F1"]).abs() <= 0.002
log(f"max |dAcc|={chk['dAcc'].abs().max():.5f}  max |dF1|={chk['dF1'].abs().max():.5f}  max |dAUC|={chk['dAUC'].abs().max():.5f}")

comp.round(6).to_csv(RES / "model_comparison.csv", index=False)
pd.DataFrame(class_rows).round(6).to_csv(RES / "class_metrics.csv", index=False)
pd.DataFrame(cm_rows).round(6).to_csv(RES / "confusion_matrix.csv", index=False)
if failures:
    pd.DataFrame(failures).to_csv(RES / "model_failures.csv", index=False)

# wide label table (compact) keyed by row_id; probabilities are cached separately
lab = {i: c for i, c in enumerate(CLASSES)}
pred_df = pd.DataFrame({"row_id": D["test_ids"],
                        "name_with_owner": D["df"].set_index("row_id").loc[D["test_ids"], "name_with_owner"].values,
                        "actual_class": [lab[i] for i in yte]})
for n in comp["Model"]:
    pred_df[n] = [lab[i] for i in preds[n]]
pred_df.to_csv(RES / "predictions.csv", index=False)

cache = RES / "cache"; cache.mkdir(exist_ok=True)
np.savez_compressed(cache / "test_predictions.npz", y_test=yte, test_ids=D["test_ids"],
                    **{f"pred::{k}": v for k, v in preds.items()},
                    **{f"score::{k}": v for k, v in scores.items()})
joblib.dump({"models": fitted, "selected_features": D["sel_names"]}, cache / "fitted_models.joblib", compress=3)
json.dump({"selected_features": D["sel_names"], "n_train": int(len(ytr)), "n_test": int(len(yte)),
           "thresholds": {"low_below": D["t_low"], "high_from": D["t_high"]}, "seed": SEED,
           "log1p_columns": D["skewed"]}, open(RES / "run_config.json", "w"), indent=2)
log(f"DONE; wrote {len(comp)} model rows; failures={len(failures)}")
print(comp[["Rank_F1", "Model", "Accuracy", "F1_macro", "ROC_AUC_macro_ovr", "Fit_Time_s"]].round(4).to_string(index=False))
