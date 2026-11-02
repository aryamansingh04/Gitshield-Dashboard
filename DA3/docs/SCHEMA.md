# DA3 output schema (CSV files in DA3/results and DA3/dashboard/data)
Class labels are always `Low Risk`, `Medium Risk`, `High Risk`. Test-set rows are identified by `row_id` (0-based position in the `repositories` query result).

| File | Grain | Key columns |
|---|---|---|
| model_comparison.csv | 1 row / model (17) | Rank_F1, Model, Family, Stage (Baseline/Tuned), Accuracy, Precision_/Recall_/F1_macro, *_weighted, ROC_AUC_macro_ovr, Avg_Precision_macro, per-class Precision_/Recall_/F1_/ROC_AUC_{Low,Medium,High}, Train_Accuracy, Fit_Time_s, Predict_Time_s, DA2_Reported_F1 |
| class_metrics.csv | model × class | Precision, Recall, F1, Support, ROC_AUC_ovr |
| confusion_matrix.csv | model × actual × predicted | Count, Row_Pct |
| predictions.csv | 1 row / test repository | row_id, name_with_owner, actual_class, one column of predicted labels per model |
| model_ci.csv | model × metric | Estimate, CI_low, CI_high, Boot_SE, B (2,000 paired bootstrap resamples) |
| statistical_comparison.csv | model pair | Family, Acc_Diff_A_minus_B (+CI), F1_Diff (+CI), A_right_B_wrong, A_wrong_B_right, Odds_Ratio_b_over_c, Cohen_dz, McNemar_exact_p, Holm_p, Interpretation |
| error_analysis.csv / class_error_summary.csv | model × (actual,predicted) / model × class | Count, Share_of_all_errors, Error_Type / TP, FP, FN, TN, FPR, FNR |
| feature_importance.csv | model × method × feature | Importance, Std, Rank_within_model_method |
| feature_importance_agreement.csv | model pair | Spearman_rho |
| cv_fold_scores.csv, cv_comparison.csv, cv_significance.csv | CV folds / models / pairs | Nadeau–Bengio corrected t-test, Holm_p |
| leakage_*.csv / .json | audit | formula overlap, exact-reconstruction error, error vs distance to cut-off, ablation, threshold check |
| dashboard/data/repository_explorer.csv | 1 row / test repository | metadata, heuristic_risk_score, heuristic_risk_class, predicted_risk_class (best model), prob_*, prediction_correct |
