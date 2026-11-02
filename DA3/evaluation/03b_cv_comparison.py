#!/usr/bin/env python3
"""
DA3 step 3b - test-free model comparison by stratified 5-fold cross-validation on the TRAINING split only.

* Preprocessing (skew detection, log1p, scaling, one-hot) and mutual-information feature selection are
  re-fitted INSIDE every fold, so no information flows from a validation fold into its own preprocessing.
* The same folds are used for every model (paired design).
* Fold scores are compared with the Nadeau-Bengio corrected resampled t-test (variance inflated by
  1/k + n_test/n_train because fold training sets overlap), Holm-adjusted across comparisons.
* Only six representative models are cross-validated to keep runtime practical on a single CPU core
  (the Gradient Boosting (Tuned) / Random Forest (Tuned) variants are excluded for cost; their untuned
  counterparts represent the families).  The held-out test comparison (steps 1-2) covers all 17 models.

Output: DA3/results/cv_fold_scores.csv, cv_comparison.csv
"""
import time
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neural_network import MLPClassifier
from statsmodels.stats.multitest import multipletests
from common import K_SELECT, RES, SEED, build_preprocessor, prepare, tuned_models

T0 = time.time()
log = lambda m: print(f"[{time.time() - T0:6.1f}s] {m}", flush=True)
K = 5

D = prepare()
Xtr_raw, ytr = D["X_train"].reset_index(drop=True), D["y_train"]
mlp_tuned = tuned_models()["MLP Neural Network (Tuned)"]
MODELS = {
    "MLP Neural Network (Tuned config)": lambda: MLPClassifier(**mlp_tuned.get_params()),
    "HistGradientBoosting": lambda: HistGradientBoostingClassifier(random_state=SEED),
    "Gradient Boosting": lambda: GradientBoostingClassifier(random_state=SEED),
    "Extra Trees": lambda: ExtraTreesClassifier(n_estimators=100, random_state=SEED, n_jobs=1),
    "Random Forest": lambda: RandomForestClassifier(n_estimators=100, random_state=SEED, n_jobs=1),
    "Logistic Regression": lambda: LogisticRegression(max_iter=1000, random_state=SEED),
}
skf = StratifiedKFold(n_splits=K, shuffle=True, random_state=SEED)
rows = []
for fold, (tr, va) in enumerate(skf.split(Xtr_raw, ytr), 1):
    pre, _ = build_preprocessor(Xtr_raw.iloc[tr])
    A = pre.fit_transform(Xtr_raw.iloc[tr]); V = pre.transform(Xtr_raw.iloc[va])
    sel = SelectKBest(lambda a, b: mutual_info_classif(a, b, random_state=SEED, n_neighbors=3), k=K_SELECT).fit(A, ytr[tr])
    A, V = sel.transform(A), sel.transform(V)
    for name, mk in MODELS.items():
        m = mk().fit(A, ytr[tr]); p = m.predict(V)
        rows.append({"Model": name, "Fold": fold, "Accuracy": accuracy_score(ytr[va], p),
                     "F1_macro": f1_score(ytr[va], p, average="macro")})
    log(f"fold {fold}/{K} done")
fs = pd.DataFrame(rows)
fs.round(6).to_csv(RES / "cv_fold_scores.csv", index=False)

n_tr = len(tr); n_va = len(va); corr = 1 / K + n_va / n_tr
summ = fs.groupby("Model").agg(Acc_mean=("Accuracy", "mean"), Acc_sd=("Accuracy", "std"),
                               F1_mean=("F1_macro", "mean"), F1_sd=("F1_macro", "std")).sort_values("F1_mean", ascending=False)
ref = summ.index[0]
piv = fs.pivot(index="Fold", columns="Model", values="F1_macro")
out = []
for m in summ.index[1:]:
    d = piv[ref] - piv[m]
    t = d.mean() / np.sqrt(corr * d.var(ddof=1)) if d.var(ddof=1) > 0 else np.inf
    p = 2 * stats.t.sf(abs(t), K - 1)
    out.append({"Reference": ref, "Comparator": m, "Mean_F1_diff": d.mean(), "NB_corrected_t": t, "df": K - 1, "p_value": p,
                "Uncorrected_paired_t_p": stats.ttest_rel(piv[ref], piv[m]).pvalue})
cmp_ = pd.DataFrame(out)
cmp_["Holm_p"] = multipletests(cmp_["p_value"], method="holm")[1]
summ = summ.reset_index()
summ.round(6).to_csv(RES / "cv_comparison.csv", index=False)
cmp_.round(8).to_csv(RES / "cv_significance.csv", index=False)
log("DONE")
print(summ.round(4).to_string(index=False)); print(cmp_.round(5).to_string(index=False))
