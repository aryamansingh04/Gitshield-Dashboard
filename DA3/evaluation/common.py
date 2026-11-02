"""
Shared DA3 utilities. Re-creates the DA2 experimental protocol EXACTLY (same SQL source table, same
tercile target, same stratified 80/20 split with random_state=42, same preprocessing, same
SelectKBest(mutual_info) fitted on the training split) so DA3 results are directly comparable
with the DA2 report.  All paths are relative to the repository root.
"""
import json, sqlite3, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import (AdaBoostClassifier, ExtraTreesClassifier, GradientBoostingClassifier,
                              HistGradientBoostingClassifier, RandomForestClassifier)
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

SEED, TEST_SIZE, K_SELECT = 42, 0.20, 20
CLASSES = ["Low Risk", "Medium Risk", "High Risk"]

DA3 = Path(__file__).resolve().parent.parent          # <repo>/DA3
ROOT = DA3.parent                                      # <repo>
DB_PATH = ROOT / "gitshield.db"
DA2_OUT = ROOT / "outputs"
RES = DA3 / "results"
RES.mkdir(parents=True, exist_ok=True)

# Same table / filter as the DA2 query. Column order differs only cosmetically: the DA2 query
# lists numeric columns before the categorical ones; the feature matrix below re-imposes the DA2
# order (NUMERIC + BINARY + CATEG), so the model inputs are identical.
QUERY = """
SELECT name_with_owner, primary_language, license, code_of_conduct,
       stars, forks, watchers, is_archived, language_count, topic_count,
       disk_usage_kb, pull_requests, issues, commits, assignable_user_count,
       repository_age_years, days_since_update, fork_ratio,
       issue_resolution_rate, repository_density, commit_activity,
       repository_risk_score
FROM repositories
WHERE repository_risk_score IS NOT NULL
"""

NUMERIC = ["stars", "forks", "watchers", "language_count", "topic_count", "disk_usage_kb",
           "pull_requests", "issues", "commits", "assignable_user_count",
           "repository_age_years", "days_since_update", "fork_ratio",
           "issue_resolution_rate", "repository_density", "commit_activity"]
BINARY = ["is_archived", "has_license", "has_code_of_conduct"]
CATEG = ["primary_language", "license"]


def load_frame():
    """SQLite -> DataFrame -> tercile risk class (identical to run_da2.py steps 1-3)."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(QUERY, conn)
    conn.close()
    df.insert(0, "row_id", np.arange(len(df)))          # stable id linking predictions <-> data
    score = df["repository_risk_score"]
    t_low = round(float(score.quantile(1 / 3)), 2)
    t_high = round(float(score.quantile(2 / 3)), 2)
    df["risk_class"] = pd.cut(score, bins=[-np.inf, t_low, t_high, np.inf], labels=CLASSES, right=False)
    for c in ("primary_language", "license", "code_of_conduct"):
        df[c] = df[c].fillna("Unknown")
    df["has_license"] = (~df["license"].isin(["Unknown", ""])).astype(int)
    df["has_code_of_conduct"] = (~df["code_of_conduct"].isin(["Unknown", "", "No Code Of Conduct"])).astype(int)
    df["is_archived"] = df["is_archived"].astype(int)
    return df, t_low, t_high


def build_preprocessor(X_train, numeric=NUMERIC, binary=BINARY, categ=CATEG):
    skew = X_train[numeric].skew()
    skewed = skew[skew.abs() > 1].index.tolist()
    not_skewed = [c for c in numeric if c not in skewed]
    log_pipe = Pipeline([("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                         ("sc", StandardScaler())])
    parts = []
    if skewed:
        parts.append(("log", log_pipe, skewed))
    if not_skewed:
        parts.append(("num", StandardScaler(), not_skewed))
    if binary:
        parts.append(("bin", "passthrough", binary))
    if categ:
        parts.append(("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", max_categories=10,
                                           sparse_output=False), categ))
    return ColumnTransformer(parts), skewed


def prepare(feature_cols=None, k=K_SELECT):
    """Split + transform. `feature_cols` (a set of raw column names) enables ablations;
    None reproduces DA2 exactly."""
    df, t_low, t_high = load_frame()
    y = df["risk_class"].map({c: i for i, c in enumerate(CLASSES)}).astype(int).values
    num = [c for c in NUMERIC if feature_cols is None or c in feature_cols]
    binr = [c for c in BINARY if feature_cols is None or c in feature_cols]
    cat = [c for c in CATEG if feature_cols is None or c in feature_cols]
    X = df[num + binr + cat]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    pre, skewed = build_preprocessor(X_train, num, binr, cat)
    Xtr_all = pre.fit_transform(X_train)
    Xte_all = pre.transform(X_test)
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    kk = min(k, len(names))
    sel = SelectKBest(lambda a, b: mutual_info_classif(a, b, random_state=SEED, n_neighbors=3), k=kk).fit(Xtr_all, y_train)
    mask = sel.get_support()
    return dict(df=df, t_low=t_low, t_high=t_high, y=y, X_train=X_train, X_test=X_test,
                y_train=y_train, y_test=y_test, Xtr=sel.transform(Xtr_all), Xte=sel.transform(Xte_all),
                all_names=names, sel_names=[n for n, m in zip(names, mask) if m],
                test_ids=df.loc[X_test.index, "row_id"].values, skewed=skewed,
                pre=pre, selector=sel)


def base_models():
    """The 12 DA2 classifiers with DA2 hyper-parameters (copied verbatim from run_da2.py)."""
    return {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=SEED),
        "KNN": KNeighborsClassifier(n_neighbors=7, n_jobs=1),
        "Decision Tree": DecisionTreeClassifier(max_depth=12, random_state=SEED),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=SEED, n_jobs=1),
        "Extra Trees": ExtraTreesClassifier(n_estimators=100, random_state=SEED, n_jobs=1),
        "Gradient Boosting": GradientBoostingClassifier(random_state=SEED),
        "AdaBoost": AdaBoostClassifier(n_estimators=100, random_state=SEED),
        "HistGradientBoosting": HistGradientBoostingClassifier(random_state=SEED),
        "Gaussian Naive Bayes": GaussianNB(),
        "Linear SVM": LinearSVC(C=1.0, max_iter=5000, random_state=SEED),
        "MLP Neural Network": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, early_stopping=True, random_state=SEED),
        "Linear Discriminant Analysis": LinearDiscriminantAnalysis(),
    }


TUNED_FACTORIES = {   # skeletons to which the DA2 best params (outputs/best_hyperparameters.json) are applied
    "Logistic Regression": lambda: LogisticRegression(max_iter=1000, random_state=SEED),
    "Random Forest": lambda: RandomForestClassifier(random_state=SEED, n_jobs=1),
    "Gradient Boosting": lambda: GradientBoostingClassifier(random_state=SEED),
    "Linear SVM": lambda: LinearSVC(max_iter=5000, random_state=SEED),
    "MLP Neural Network": lambda: MLPClassifier(max_iter=300, early_stopping=True, random_state=SEED),
}


def tuned_models():
    best = json.load(open(DA2_OUT / "best_hyperparameters.json"))
    out = {}
    for name, params in best.items():
        p = {k: (tuple(v) if isinstance(v, list) else v) for k, v in params.items()}
        out[f"{name} (Tuned)"] = TUNED_FACTORIES[name]().set_params(**p)
    return out


def get_scores(model, X):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)
    d = model.decision_function(X)
    e = np.exp(d - d.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)
