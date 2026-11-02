# Smoke tests for the dashboard server logic (no browser needed).
# Run from the repository root:  Rscript DA3/dashboard/tests/test_server.R
setwd(file.path("DA3", "dashboard"))
suppressPackageStartupMessages(library(shiny))
app <- shinyAppDir(".")
suppressPackageStartupMessages({library(dplyr); library(readr)})
rd <- function(f) read_csv(file.path("data", f), show_col_types = FALSE, progress = FALSE)
fimp <- rd("feature_importance.csv"); stat <- rd("statistical_comparison.csv"); expl <- rd("repository_explorer.csv")
CLASSES <- c("Low Risk", "Medium Risk", "High Risk")
ok <- 0; fail <- 0
chk <- function(label, expr) {
  r <- tryCatch({ force(expr); TRUE }, error = function(e) { cat("FAIL:", label, "->", conditionMessage(e), "\n"); FALSE })
  if (r) { ok <<- ok + 1; cat("ok  :", label, "\n") } else fail <<- fail + 1
}
testServer(app, {
  # Overview
  chk("overview distribution", output$ov_dist)
  # Model comparison, every metric
  for (m in c("Accuracy", "F1_macro", "Precision_macro", "Recall_macro", "F1_weighted", "ROC_AUC_macro_ovr")) {
    session$setInputs(metric = m, stages = c("Baseline", "Tuned"))
    chk(paste("cmp_plot", m), output$cmp_plot); chk(paste("tune_plot", m), output$tune_plot); chk(paste("rank_tbl", m), output$rank_tbl)
  }
  session$setInputs(metric = "F1_macro", stages = character(0))
  chk("cmp_plot handles empty stage selection (validate -> silent)", tryCatch(output$cmp_plot, shiny.silent.error = function(e) "silent"))
  # Classification performance
  for (mdl in c("MLP Neural Network", "Gaussian Naive Bayes", "Linear SVM (Tuned)")) {
    session$setInputs(cm_model = mdl, cm_mode = "n", pc_models = c(mdl, "KNN"), pc_metric = "Recall")
    chk(paste("cm_plot counts", mdl), output$cm_plot); chk(paste("err_plot", mdl), output$err_plot)
    chk(paste("err_text", mdl), output$err_text); chk(paste("fpfn_tbl", mdl), output$fpfn_tbl); chk(paste("pc_plot", mdl), output$pc_plot)
    session$setInputs(cm_mode = "pct"); chk(paste("cm_plot pct", mdl), output$cm_plot)
  }
  # Feature importance (both methods)
  for (meth in sort(unique(fimp$Method))) {
    session$setInputs(fi_method = meth); ch <- unique(fimp$Model[fimp$Method == meth])
    for (mdl in ch) { session$setInputs(fi_model = mdl, fi_top = 12); chk(paste("fi_plot", meth, mdl), output$fi_plot) }
  }
  chk("fi_agree", output$fi_agree)
  # Explorer: default, filtered, and empty
  D <- max(expl$days_since_update); A <- max(expl$repository_age_years)
  base <- list(ex_q = "", ex_lang = character(0), ex_hclass = CLASSES, ex_pclass = CLASSES, ex_out = "All",
               ex_days = c(0, ceiling(D)), ex_age = c(0, ceiling(A)), ex_stars = 0, ex_x = "days_since_update",
               ex_y = "repository_age_years", ex_col = "heuristic_risk_class", ex_log = character(0))
  do.call(session$setInputs, base)
  chk("explorer default plot", output$ex_plot); chk("explorer default table", output$ex_tbl); chk("explorer summary", output$ex_summary)
  stopifnot(nrow(filt()) == nrow(expl))
  session$setInputs(ex_lang = "Python", ex_hclass = "High Risk", ex_out = "Misclassified", ex_log = c("x", "y"), ex_col = "outcome")
  chk("explorer filtered plot (log axes)", output$ex_plot); chk("explorer filtered table", output$ex_tbl)
  cat("     filtered rows:", nrow(filt()), "\n")
  session$setInputs(ex_q = "zzzz-no-such-repo-zzzz")
  stopifnot(nrow(filt()) == 0)
  chk("explorer empty-result summary", { h <- as.character(output$ex_summary$html); stopifnot(grepl("No repositories match", h)) })
  chk("explorer empty plot -> validate message", tryCatch(output$ex_plot, shiny.silent.error = function(e) "silent"))
  session$setInputs(ex_q = "react", ex_lang = character(0), ex_hclass = CLASSES, ex_out = "All", ex_log = character(0))
  cat("     search 'react' matches:", nrow(filt()), "\n")
  # Statistics & validity
  for (m in c("Accuracy", "F1_macro", "ROC_AUC_macro_ovr")) { session$setInputs(ci_metric = m); chk(paste("ci_plot", m), output$ci_plot) }
  for (f in unique(stat$Family)) { session$setInputs(st_family = f); chk(paste("st_tbl", substr(f, 1, 30)), output$st_tbl) }
  chk("ovl_tbl", output$ovl_tbl); chk("bnd_plot", output$bnd_plot); chk("abl_plot", output$abl_plot)
})
cat(sprintf("\n%d checks passed, %d failed\n", ok, fail)); if (fail > 0) quit(status = 1)
