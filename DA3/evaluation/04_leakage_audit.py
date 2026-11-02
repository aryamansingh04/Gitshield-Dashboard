#!/usr/bin/env python3
"""
DA3 step 4 - data-leakage and target-validity audit (a SEPARATE, supplementary analysis; the headline DA2/DA3
results are NOT changed by it).

Questions answered
 Q1  Which model inputs are components of the formula that defines the label (repository_risk_score)?
 Q2  Can the risk score be reproduced exactly from the model inputs (i.e. is the label a deterministic function of them)?
 Q3  Where do misclassifications occur relative to the class thresholds?
 Q4  How much of the performance survives when the formula components are removed (ablation)?
 Q5  Does computing the tercile cut-offs on ALL rows (as DA2 did) rather than the training rows change any test label?

Outputs (DA3/results): leakage_formula_overlap.csv, leakage_reconstruction.json, leakage_boundary_error.csv,
                       leakage_ablation.csv, leakage_threshold_check.json
"""
import json, time
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from common import CLASSES, NUMERIC, BINARY, CATEG, RES, SEED, get_scores, load_frame, prepare

T0 = time.time()
log = lambda m: print(f"[{time.time() - T0:6.1f}s] {m}", flush=True)

# ------------------------------------------------------------------ Q1: formula vs predictors
# repository_risk_score = .40*security_exposure + .25*(1-maintenance) + .20*(1-stability) + .15*(1-community)
# (DA1/Scripts/04_feature_engineering.R). Raw inputs of each sub-score:
FORMULA = {
    "has_license":            ["security_exposure"],
    "has_code_of_conduct":    ["security_exposure"],
    "days_since_update":      ["security_exposure", "maintenance", "stability"],      # via freshness
    "is_archived":            ["security_exposure", "maintenance", "stability"],
    "assignable_user_count":  ["security_exposure", "maintenance", "community"],
    "fork_ratio":             ["security_exposure"],
    "pull_requests":          ["maintenance"],
    "repository_age_years":   ["stability"],
    "issue_resolution_rate":  ["stability"],
    "forks":                  ["community", "(fork_ratio)"],
    "watchers":               ["community"],
    "topic_count":            ["community"],
    "issues":                 ["(issue_resolution_rate)"],
    "stars":                  ["(fork_ratio denominator)"],
}
license_cols = ["license"]               # license one-hot encodes the same information as has_license
rows = []
for c in NUMERIC + BINARY + CATEG:
    inf = FORMULA.get(c) or (["security_exposure (via has_license)"] if c == "license" else [])
    direct = bool(inf) and not all(s.startswith("(") for s in inf)
    rows.append({"Predictor": c, "In_label_formula": bool(inf), "Direct_component": direct,
                 "Enters_through": "; ".join(inf) if inf else "- (not used by the label)"})
ov = pd.DataFrame(rows)
ov.to_csv(RES / "leakage_formula_overlap.csv", index=False)
n_in = int(ov["In_label_formula"].sum())
log(f"Q1: {n_in}/{len(ov)} predictor columns are inputs (direct or indirect) of the label formula")

# ------------------------------------------------------------------ Q2: exact reconstruction
df, t_low, t_high = load_frame()
raw = pd.read_sql_query if False else None
import sqlite3
from common import DB_PATH
conn = sqlite3.connect(DB_PATH)
full = pd.read_sql_query("SELECT name_with_owner, forks, watchers, topic_count, assignable_user_count, pull_requests, "
                         "issues, repository_age_years, days_since_update, is_archived, fork_ratio, issue_resolution_rate, "
                         "license, code_of_conduct, repository_freshness, repository_risk_score FROM repositories", conn)
conn.close()


def mm(x):
    r = x.max() - x.min()
    return (x - x.min()) / r if r else x * 0


s_fresh = mm(1 / (1 + full["days_since_update"].clip(lower=0) / 365.25))
s_age = mm(full["repository_age_years"])
s_assign = mm(np.log1p(full["assignable_user_count"]))
s_prs = mm(np.log1p(full["pull_requests"]))
s_forks = mm(np.log1p(full["forks"]))
s_watch = mm(np.log1p(full["watchers"]))
s_topics = mm(full["topic_count"])
arch = full["is_archived"].astype(int)
lic = (~(full["license"].isna() | full["license"].isin(["Unknown", ""]))).astype(int)
# DA1 (R) treats every value other than "Unknown"/"" as "has a code of conduct". The DA1 CSV contains the literal
# string "None" for 9 repositories, which pandas parses as missing (NaN) when DA2 re-loaded the file; restore it here.
n_nan_coc = int(full["code_of_conduct"].isna().sum())
n_no_coc_str = int((full["code_of_conduct"] == "No Code Of Conduct").sum())
coc_da1 = (~(full["code_of_conduct"].fillna("None").isin(["Unknown", ""]))).astype(int)
coc_naive = (~(full["code_of_conduct"].isna() | full["code_of_conduct"].isin(["Unknown", ""]))).astype(int)
coc = coc_da1
sec = (0.25 * (1 - lic) + 0.20 * (1 - coc) + 0.20 * (1 - s_fresh) + 0.15 * arch + 0.10 * (1 - s_assign)
       + 0.10 * mm(full["fork_ratio"]))
maint = 0.45 * s_fresh + 0.25 * s_prs + 0.15 * s_assign + 0.15 * (1 - arch)
stab = 0.35 * s_age + 0.25 * (1 - arch) + 0.20 * s_fresh + 0.20 * mm(full["issue_resolution_rate"])
comm = 0.35 * s_forks + 0.25 * s_watch + 0.20 * s_assign + 0.20 * s_topics
rec = 0.40 * sec + 0.25 * (1 - maint) + 0.20 * (1 - stab) + 0.15 * (1 - comm)
err = (rec - full["repository_risk_score"]).abs()
def _rec(coc_):
    sec_ = 0.25 * (1 - lic) + 0.20 * (1 - coc_) + 0.20 * (1 - s_fresh) + 0.15 * arch + 0.10 * (1 - s_assign) + 0.10 * mm(full["fork_ratio"])
    return 0.40 * sec_ + 0.25 * (1 - maint) + 0.20 * (1 - stab) + 0.15 * (1 - comm)
err_naive = (_rec(coc_naive) - full["repository_risk_score"]).abs()
recon = {"n_rows": int(len(full)), "max_abs_error": float(err.max()),
         "rows_not_reproduced_if_pandas_NaN_treated_as_missing": int((err_naive > 1e-6).sum()),
         "da1_da2_code_of_conduct_encoding_mismatch_rows": n_nan_coc + n_no_coc_str,
         "da1_da2_code_of_conduct_note": "DA1 counts the strings 'None' (9 rows, parsed as NaN by pandas) and 'No Code Of Conduct' (5 rows) as 'has code of conduct'; DA2 feature has_code_of_conduct counts them as absent.", "mean_abs_error": float(err.mean()),
         "share_within_1e-6": float((err < 1e-6).mean()),
         "class_agreement_with_stored_label": float((pd.cut(rec, [-np.inf, t_low, t_high, np.inf], labels=CLASSES, right=False)
                                                     == df["risk_class"]).mean()),
         "interpretation": "label is a deterministic, closed-form function of raw columns that are also DA2 model inputs "
                           "(the models never see the composite scores themselves, but they see their ingredients)"}
json.dump(recon, open(RES / "leakage_reconstruction.json", "w"), indent=2)
log(f"Q2: reconstruction max|err|={recon['max_abs_error']:.2e}, share<1e-6={recon['share_within_1e-6']:.4f}, "
    f"label agreement={recon['class_agreement_with_stored_label']:.4f}")

# ------------------------------------------------------------------ Q3: errors vs distance to threshold
z = np.load(RES / "cache" / "test_predictions.npz")
comp = pd.read_csv(RES / "model_comparison.csv")
best = comp.loc[0, "Model"]
ids, yte = z["test_ids"], z["y_test"]
sc = df.set_index("row_id").loc[ids, "repository_risk_score"].values
dist = np.minimum(np.abs(sc - t_low), np.abs(sc - t_high))
wrong = z[f"pred::{best}"] != yte
bins = [0, 0.005, 0.01, 0.02, 0.04, 0.08, 1.0]
b = pd.cut(dist, bins, include_lowest=True)
tab = pd.DataFrame({"bin": b, "wrong": wrong}).groupby("bin", observed=True)["wrong"].agg(["size", "sum", "mean"])
tab.columns = ["n_test_rows", "n_errors", "error_rate"]
tab.insert(0, "Model", best)
tab.index = [f"{iv.left:g}-{iv.right:g}" for iv in tab.index]
tab.index.name = "distance_to_nearest_threshold"
tab.round(5).to_csv(RES / "leakage_boundary_error.csv")
log("Q3: error rate by distance to threshold:\n" + tab.round(4).to_string())
tab2 = {"best_model": best, "median_distance_correct": float(np.median(dist[~wrong])),
        "median_distance_errors": float(np.median(dist[wrong])),
        "share_errors_within_0.02_of_threshold": float((dist[wrong] < 0.02).mean())}
json.dump(tab2, open(RES / "leakage_boundary_summary.json", "w"), indent=2)

# ------------------------------------------------------------------ Q5: thresholds from train rows only
tr_idx = set(df["row_id"]) - set(ids)
sc_tr = df.set_index("row_id").loc[sorted(tr_idx), "repository_risk_score"]
t_low_tr, t_high_tr = round(float(sc_tr.quantile(1 / 3)), 2), round(float(sc_tr.quantile(2 / 3)), 2)
lab_alt = pd.cut(pd.Series(sc), [-np.inf, t_low_tr, t_high_tr, np.inf], labels=False, right=False).values
json.dump({"thresholds_all_rows_(DA2)": [t_low, t_high], "thresholds_train_rows_only": [t_low_tr, t_high_tr],
           "test_labels_that_would_change": int((lab_alt != yte).sum()), "n_test": int(len(yte))},
          open(RES / "leakage_threshold_check.json", "w"), indent=2)
log(f"Q5: thresholds all={t_low, t_high} train-only={t_low_tr, t_high_tr}; changed test labels={(lab_alt != yte).sum()}")

# ------------------------------------------------------------------ Q4: ablation
SEC_FLAGS = {"has_license", "has_code_of_conduct", "license", "is_archived", "days_since_update"}
FORMULA_COLS = {c for c in FORMULA} | {"license"}
ALL = set(NUMERIC + BINARY + CATEG)
SETS = {
    "A. Full DA2 predictor set (as reported)": ALL,
    "B. Without direct security flags (license, code of conduct, archived, days since update)": ALL - SEC_FLAGS,
    "C. Without ANY label-formula input": ALL - FORMULA_COLS,
}
res = []
for sname, cols in SETS.items():
    D = prepare(feature_cols=cols)
    log(f"Q4: {sname}: {len(cols)} raw columns -> {len(D['sel_names'])} selected features")
    mods = {"Dummy (class prior)": DummyClassifier(strategy="prior"),
            "Logistic Regression": LogisticRegression(max_iter=1000, random_state=SEED),
            "HistGradientBoosting": HistGradientBoostingClassifier(random_state=SEED),
            "MLP Neural Network": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, early_stopping=True, random_state=SEED)}
    for mn, m in mods.items():
        m.fit(D["Xtr"], D["y_train"]); p = m.predict(D["Xte"]); s = get_scores(m, D["Xte"])
        res.append({"Predictor_set": sname, "N_raw_columns": len(cols), "Model": mn,
                    "Accuracy": accuracy_score(D["y_test"], p), "F1_macro": f1_score(D["y_test"], p, average="macro"),
                    "ROC_AUC_macro_ovr": roc_auc_score(D["y_test"], s, multi_class="ovr", average="macro"),
                    "Features_used": ", ".join(D["sel_names"])})
        log(f"    {mn:24s} acc={res[-1]['Accuracy']:.4f} f1={res[-1]['F1_macro']:.4f}")
pd.DataFrame(res).round(6).to_csv(RES / "leakage_ablation.csv", index=False)
log("DONE")
