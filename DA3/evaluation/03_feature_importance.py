#!/usr/bin/env python3
"""
DA3 step 3 - feature importance.

* Permutation importance (drop in macro-F1 when one feature column is shuffled) on a random test subsample,
  computed for several model families so that conclusions do not rest on one model.
* Impurity-based importance for the tree ensembles (secondary; known to favour high-cardinality features).
* Feature names come from the fitted SelectKBest/ColumnTransformer pipeline (DA3/results/run_config.json),
  not from hand-typed labels.
Importance describes what a fitted model USES to reproduce the label; it is not evidence of causation.

Output: DA3/results/feature_importance.csv (long format), feature_importance_agreement.csv
"""
import time
import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.inspection import permutation_importance
from common import RES, SEED, prepare

T0 = time.time()
log = lambda m: print(f"[{time.time() - T0:6.1f}s] {m}", flush=True)

D = prepare()                                   # deterministic: identical split / transform as step 1
cache = joblib.load(RES / "cache" / "fitted_models.joblib")
models, names = cache["models"], cache["selected_features"]
assert names == D["sel_names"], "feature-name mismatch between cached models and re-built pipeline"
Xte, yte = D["Xte"], D["y_test"]

N_SUB, REPEATS = 5000, 5
idx = np.random.RandomState(SEED).choice(len(yte), size=N_SUB, replace=False)
perm_models = ["MLP Neural Network (Tuned)", "MLP Neural Network", "HistGradientBoosting",
               "Gradient Boosting (Tuned)", "Random Forest (Tuned)", "Extra Trees", "Logistic Regression"]
rows = []
for m in perm_models:
    if m not in models:
        log(f"skip {m} (not fitted)"); continue
    r = permutation_importance(models[m], Xte[idx], yte[idx], scoring="f1_macro", n_repeats=REPEATS,
                               random_state=SEED, n_jobs=1)
    for f, mu, sd in zip(names, r.importances_mean, r.importances_std):
        rows.append({"Model": m, "Method": "Permutation (drop in macro-F1)", "Feature": f,
                     "Importance": mu, "Std": sd, "N_eval_rows": N_SUB, "Repeats": REPEATS})
    log(f"permutation importance done: {m}")
for m in ["Random Forest (Tuned)", "Gradient Boosting (Tuned)", "Extra Trees", "HistGradientBoosting"]:
    if m in models and hasattr(models[m], "feature_importances_"):
        for f, v in zip(names, models[m].feature_importances_):
            rows.append({"Model": m, "Method": "Impurity (mean decrease)", "Feature": f, "Importance": v,
                         "Std": np.nan, "N_eval_rows": np.nan, "Repeats": np.nan})
fi = pd.DataFrame(rows)
fi["Rank_within_model_method"] = fi.groupby(["Model", "Method"])["Importance"].rank(ascending=False, method="min")
fi.round(6).to_csv(RES / "feature_importance.csv", index=False)

# agreement of permutation rankings across models
pv = fi[fi.Method.str.startswith("Permutation")].pivot(index="Feature", columns="Model", values="Importance")
ag = []
cols = list(pv.columns)
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        rho = spearmanr(pv[cols[i]], pv[cols[j]]).statistic
        ag.append({"Model_A": cols[i], "Model_B": cols[j], "Spearman_rho": rho})
pd.DataFrame(ag).round(4).to_csv(RES / "feature_importance_agreement.csv", index=False)
log("DONE")
print(fi[fi.Model == perm_models[0]].sort_values("Importance", ascending=False).head(8)[["Feature", "Importance"]])
