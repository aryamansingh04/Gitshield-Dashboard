# GitShield AI — DA3 (Final Evaluation & Project Demonstration)

DA3 adds a reproducible final evaluation, statistical analysis, a label-validity audit, an interactive
**R Shiny + Plotly dashboard**, a report, slides and viva notes on top of the existing DA2 code.
DA2 files (`run_da2.py`, `outputs/`, `gitshield.db`) are **unchanged**.

> **Scope.** GitShield AI predicts a *heuristic, metadata-derived* risk class. It is not a vulnerability scanner.
> The label is an exact function of the model inputs (see `results/leakage_reconstruction.json`), so high accuracy
> shows the heuristic is learnable, not that real-world risk is predicted.

## Layout
```
DA3/
  evaluation/   01_train_and_evaluate.py  02_statistics.py  03_feature_importance.py
                03b_cv_comparison.py  04_leakage_audit.py  05_export_dashboard_data.py
                run_all_after_training.sh  common.py
  results/      consolidated CSV/JSON outputs (schema in docs/SCHEMA.md); results/cache/ is git-ignored
  dashboard/    app.R  run.R  data/ (CSV/JSON the app reads)  tests/test_server.R
  report/       make_figures.py  build_consolidated_report.py  figures/  source/ (original DA1+DA2 report)  GitShield_AI_Consolidated_Report.docx
  presentation/ GitShield_AI_DA3.pptx   viva notes
  docs/         SCHEMA.md
```

## Prerequisites
* Python 3.10+ : `pip install -r requirements.txt statsmodels matplotlib python-docx joblib`
* R 4.2+ : `install.packages(c("shiny","bslib","plotly","dplyr","readr","DT","jsonlite"))`
* Input: `gitshield.db` (table `repositories`) and `outputs/best_hyperparameters.json`, `outputs/model_comparison.csv` from DA2 (already in the repo).

## Reproduce (from the repository root)
```bash
python DA3/evaluation/01_train_and_evaluate.py     # 17 models -> results/model_comparison.csv, predictions.csv, ... (~3 min on 1 CPU)
bash   DA3/evaluation/run_all_after_training.sh    # bootstrap/McNemar, audit, importance, dashboard export, 5-fold CV (~15 min)
python DA3/report/make_figures.py                  # report figures from results/
python DA3/report/build_consolidated_report.py     # ONE consolidated DA1+DA2+DA3 Word report
```
Step 1 prints/saves a comparison with the stored DA2 numbers (`results/reproducibility_check_vs_DA2.csv`);
differences of up to ~0.001 are due to scikit-learn version tie-breaking.

## Launch the dashboard
```bash
Rscript DA3/dashboard/run.R                       # or in R: shiny::runApp("DA3/dashboard")
Rscript DA3/dashboard/tests/test_server.R         # optional server-logic tests (64 checks)
```
The app only reads `DA3/dashboard/data/*` (exported by step 05). It never retrains models.

## Known limitations
See Sections 9, 13 of the report: heuristic target; predictor/label overlap; single snapshot; star-threshold
population; non-causal importance; test set used for ranking 17 candidates; CV on six models only; DA2 tuning used
a 10,000-row subsample. Dashboard screenshots must be captured by running the app.
