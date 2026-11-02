# GitShield AI — DA3 viva preparation (numbers from DA3/results; re-check after any re-run)

**1. Why was the MLP selected?**
It had the highest held-out macro-F1 (0.9504; accuracy 0.9504 [0.9473, 0.9538]; macro ROC-AUC 0.9880). It beats the next family
(HistGradientBoosting) by 1.25 pp accuracy (paired CI 1.02–1.49, Holm p < 0.001). It is *not* distinguishable from the tuned MLP
(Holm p = 1.0), so "best" between those two rests on a ~0.00004 macro-F1 difference. The MLP's edge is plausible because the label is a smooth
weighted function that a neural net can approximate — and it depends on having the formula's inputs (see Q8).

**2. Why macro-F1?**
Three classes matter equally; macro-F1 averages per-class F1 so poor performance on one class cannot hide. Classes are near-balanced,
so accuracy and macro-F1 are almost equal here; macro-F1 is still the safer selection metric.

**3. Why ROC-AUC?**
It measures how well predicted probabilities *rank* a class above the others, independent of the decision threshold. I use one-vs-rest, macro-averaged.
It complements F1; it says nothing about calibration.

**4. How was train–test leakage prevented?**
Stratified 80:20 split (seed 42) before preprocessing; scalers, encoders, skew detection and mutual-information feature selection are fitted on the training split only.
Tuning used cross-validation inside the training split. Honest caveats: tercile cut-offs were computed on all rows in DA2 (recomputing on training rows gives identical cut-offs, 0 labels change);
the test set also ranks 17 models, so the best score is mildly optimistic. **Separate and more serious: target–predictor overlap** (Q8).

**5. Why does statistical significance matter?**
Differences of a few tenths of a point may be noise on a 16,098-row test set. Bootstrap CIs show uncertainty; paired McNemar tests ask whether two models' errors differ on the *same* repositories;
Holm correction controls false positives over many comparisons. Significance is not importance: I also require ≥ 1 pp for "practically meaningful", and neither says the result generalises to other repositories.

**6. How was feature importance calculated?**
Permutation importance: shuffle one feature in the test data and measure the drop in macro-F1 (5 repeats, 5,000 rows), for seven models; impurity importance for tree models. Top MLP features: days_since_update (0.44), license_Unknown, has_license, repository_age_years.
It shows what the model uses, not what causes risk; correlated features share credit.

**7. How were the risk categories created?**
`repository_risk_score` = 0.40·security exposure + 0.25·(1−maintenance) + 0.20·(1−stability) + 0.15·(1−community), each sub-score a weighted mix of normalised metadata. The score is cut at its 33rd/67th percentiles (0.54, 0.65) → ~equal classes. Classes are *relative*, not absolute.

**8. Why do heuristic labels limit security claims? (Key question — answer proactively)**
The label is an exact function of columns that are also model inputs: I recomputed it for all 80,489 rows with max error 2.2e-16 and 100% label agreement. So the models learn a known formula; accuracy shows it is learnable, not that real risk or vulnerabilities are predicted.
Evidence: removing licence/CoC/archived/recency drops accuracy from 0.95 to ~0.63–0.65; removing every formula input leaves ~0.57–0.59 (class-prior baseline 0.34). No vulnerability labels were ever used, so no security claim is made.
A proper fix would be an independently defined target (e.g., known advisories) or a target whose inputs are excluded from predictors.

**9. How does the dashboard obtain its data?**
Python writes CSV/JSON files (`DA3/dashboard/data`); the R Shiny app reads them once at start-up. Nothing is retrained in R. The explorer shows the 16,098 test repositories (the only ones with out-of-sample predictions); heuristic class and predicted class are separate columns.

**10. How can the results be reproduced?**
`python DA3/evaluation/01_train_and_evaluate.py`, then `bash DA3/evaluation/run_all_after_training.sh`, `python DA3/report/make_figures.py`, `python DA3/report/build_consolidated_report.py`, `Rscript DA3/dashboard/run.R`. Seeds fixed (42); relative paths; my re-run matched stored DA2 numbers within 0.0011 (library-version tie-breaking).

## Likely follow-ups
* **Which errors worry you most?** 85 High Risk repos predicted Low (10.7% of errors); High Risk recall 0.905 vs precision 0.988 — the model is conservative about "High".
* **Did tuning help?** No: tuned vs baseline within noise for all five (LR picked default C=1; SVM differs on 2 predictions; MLP 213 predictions change, accuracy same). Grid used a 10k subsample and 3 folds.
* **Are errors only near class boundaries?** No: error rate is 20.7% within 0.005 of a cut-off, but only ~29% of errors lie within 0.02 of one.
* **Would you deploy this?** Only as a transparent metadata summary, not as a security assessment.
