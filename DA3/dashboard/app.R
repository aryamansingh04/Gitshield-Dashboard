# =============================================================================
# GitShield AI - DA3 interactive dashboard (R Shiny + Plotly)
# Reads ONLY the pre-computed CSV/JSON files in ./data (exported by the Python
# pipeline, see DA3/README.md). Nothing is retrained here.
# Launch:  shiny::runApp("DA3/dashboard")      (or  Rscript DA3/dashboard/run.R)
# =============================================================================
suppressPackageStartupMessages({
  library(shiny); library(bslib); library(plotly)
  library(dplyr); library(readr); library(DT)
})

# ---- data loading (once, at start-up; shared by all sessions) ---------------
DATA_DIR <- if (dir.exists("data")) "data" else file.path("DA3", "dashboard", "data")
need_files <- c("model_comparison.csv", "class_metrics.csv", "confusion_matrix.csv",
                "feature_importance.csv", "statistical_comparison.csv", "model_ci.csv",
                "error_analysis.csv", "repository_explorer.csv", "overview.json",
                "leakage_formula_overlap.csv", "leakage_boundary_error.csv", "leakage_ablation.csv",
                "feature_importance_agreement.csv")
missing <- need_files[!file.exists(file.path(DATA_DIR, need_files))]
if (length(missing) > 0) {
  stop("Dashboard data files missing in '", DATA_DIR, "': ", paste(missing, collapse = ", "),
       ". Run: python DA3/evaluation/05_export_dashboard_data.py")
}
rd <- function(f) read_csv(file.path(DATA_DIR, f), show_col_types = FALSE, progress = FALSE)

comp  <- rd("model_comparison.csv")
cls   <- rd("class_metrics.csv")
cmx   <- rd("confusion_matrix.csv")
fimp  <- rd("feature_importance.csv")
stat  <- rd("statistical_comparison.csv")
ci    <- rd("model_ci.csv")
err   <- rd("error_analysis.csv")
expl  <- rd("repository_explorer.csv")
ov    <- jsonlite::fromJSON(file.path(DATA_DIR, "overview.json"))
f_ovl <- rd("leakage_formula_overlap.csv")
f_bnd <- rd("leakage_boundary_error.csv")
f_abl <- rd("leakage_ablation.csv")
f_agr <- rd("feature_importance_agreement.csv")

CLASSES <- c("Low Risk", "Medium Risk", "High Risk")
CLS_COL <- c("Low Risk" = "#2A9D8F", "Medium Risk" = "#E9C46A", "High Risk" = "#E76F51")
NAVY <- "#1F3A5F"; STEEL <- "#8DA9C4"
METRICS <- c("Accuracy" = "Accuracy", "Macro-F1" = "F1_macro", "Macro precision" = "Precision_macro",
             "Macro recall" = "Recall_macro", "Weighted F1" = "F1_weighted",
             "Macro ROC-AUC (one-vs-rest)" = "ROC_AUC_macro_ovr")
metric_label <- function(code) names(METRICS)[match(code, METRICS)]
fmt <- function(x, d = 4) formatC(x, format = "f", digits = d)

expl$heuristic_risk_class <- factor(expl$heuristic_risk_class, CLASSES)
expl$predicted_risk_class <- factor(expl$predicted_risk_class, CLASSES)
expl$outcome <- ifelse(expl$prediction_correct == 1, "Correct", "Misclassified")
NUM_AXES <- c("Stars" = "stars", "Forks" = "forks", "Watchers" = "watchers", "Issues" = "issues",
              "Pull requests" = "pull_requests", "Commits" = "commits",
              "Days since last update" = "days_since_update", "Repository age (years)" = "repository_age_years",
              "Heuristic risk score" = "heuristic_risk_score")

plot_theme <- function(p) {
  p %>% layout(font = list(family = "Inter, Segoe UI, Helvetica, Arial, sans-serif", size = 13),
               paper_bgcolor = "rgba(0,0,0,0)", plot_bgcolor = "rgba(0,0,0,0)",
               margin = list(l = 10, r = 20, t = 40, b = 40), legend = list(orientation = "h", y = -0.15)) %>%
    config(displaylogo = FALSE)
}
scales_pct <- function(x) sprintf("%.2f%%", 100 * x)
note <- function(...) tags$p(class = "text-muted small mb-2", ...)

# ----------------------------------------------------------------------------- UI
ui <- page_navbar(
  title = "GitShield AI \u2014 DA3 Dashboard",
  theme = bs_theme(version = 5, bootswatch = "flatly", primary = NAVY, "font-size-base" = "0.95rem"),
  fillable = FALSE,
  header = tags$style(HTML(".card-header{font-weight:600}.value-box .value-box-value{font-size:1.5rem}
                            .small-note{font-size:.85rem}")),

  # ---- 1. Overview -----------------------------------------------------------
  nav_panel("Overview",
    layout_columns(col_widths = c(3, 3, 3, 3),
      value_box("Repositories analysed", format(ov$n_repositories, big.mark = ","), theme = "primary",
                p(class = "small-note mb-0", sprintf("%s train / %s held-out test",
                  format(ov$n_train, big.mark = ","), format(ov$n_test, big.mark = ",")))),
      value_box("Models evaluated", ov$n_models_evaluated, theme = "secondary",
                p(class = "small-note mb-0", sprintf("%d baseline + %d tuned variants", ov$n_baseline_models, ov$n_tuned_models))),
      value_box("Best model (macro-F1)", ov$best_model, theme = "success",
                p(class = "small-note mb-0", "Rule: highest test macro-F1")),
      value_box("Test accuracy", fmt(ov$best_accuracy), theme = "info",
                p(class = "small-note mb-0", sprintf("95%% CI %s\u2013%s", fmt(ov$best_accuracy_ci[1]), fmt(ov$best_accuracy_ci[2]))))
    ),
    layout_columns(col_widths = c(3, 3, 6),
      value_box("Macro-F1", fmt(ov$best_f1_macro), theme = "light",
                p(class = "small-note mb-0", sprintf("95%% CI %s\u2013%s", fmt(ov$best_f1_ci[1]), fmt(ov$best_f1_ci[2])))),
      value_box("Macro ROC-AUC", fmt(ov$best_roc_auc), theme = "light",
                p(class = "small-note mb-0", sprintf("95%% CI %s\u2013%s", fmt(ov$best_auc_ci[1]), fmt(ov$best_auc_ci[2])))),
      card(card_header("What does GitShield AI predict?"),
           p("GitShield AI classifies a GitHub repository into ", tags$b("Low / Medium / High risk"),
             " from public repository metadata (maintenance activity, community engagement, licensing, age, size)."),
           p(class = "mb-0", "The class is a ", tags$b("heuristic, metadata-based label"),
             " (tercile of a composite ", tags$code("repository_risk_score"),
             "). It is ", tags$b("not"), " a vulnerability scan and does not verify that a repository is safe or unsafe."))
    ),
    layout_columns(col_widths = c(6, 6),
      card(card_header("Risk-class distribution (heuristic label, all repositories)"), plotlyOutput("ov_dist", height = 300),
           card_footer(class = "small-note", sprintf("Cut-offs on repository_risk_score: Low < %.2f \u2264 Medium < %.2f \u2264 High.",
                                                    ov$thresholds$low_below, ov$thresholds$high_from))),
      card(card_header("How to read the headline numbers"),
           tags$ul(
             tags$li(tags$b("Selection rule: "), ov$selection_rule),
             tags$li(tags$b("Validity warning: "), sprintf(
               "the label is an exact closed-form function of inputs that are also model features (reconstruction error %.1e). High scores therefore show that the formula is learnable, not that real-world risk is predicted. See the 'Statistics & validity' tab.",
               ov$reconstruction$max_abs_error)),
             tags$li(tags$b("Uncertainty: "), "95% confidence intervals come from 2,000 paired bootstrap resamples of the test set.")
           ))
    )
  ),

  # ---- 2. Model comparison ----------------------------------------------------
  nav_panel("Model comparison",
    layout_sidebar(
      sidebar = sidebar(width = 270,
        selectInput("metric", "Metric", choices = METRICS, selected = "F1_macro"),
        checkboxGroupInput("stages", "Model variants", choices = c("Baseline", "Tuned"), selected = c("Baseline", "Tuned")),
        note("Bars show the held-out test value; whiskers are 95% bootstrap confidence intervals. The x-axis is truncated for readability.")
      ),
      card(card_header("All models, ranked by selected metric"), plotlyOutput("cmp_plot", height = 560)),
      layout_columns(col_widths = c(6, 6),
        card(card_header("Tuned vs untuned (5 tuned families)"), plotlyOutput("tune_plot", height = 320),
             card_footer(class = "small-note", "Tuning: GridSearchCV, 3-fold, macro-F1, on a 10,000-row subsample of the training split; final model refit on the full training split. Where the tuned value equals the baseline, tuning did not change the selected configuration's test result.")),
        card(card_header("Ranking table"), DTOutput("rank_tbl"))
      )
    )
  ),

  # ---- 3. Classification performance -------------------------------------------
  nav_panel("Classification performance",
    layout_sidebar(
      sidebar = sidebar(width = 270,
        selectInput("cm_model", "Model (confusion matrix)", choices = comp$Model, selected = ov$best_model),
        radioButtons("cm_mode", "Show", c("Counts" = "n", "Row % (recall view)" = "pct"), inline = TRUE),
        hr(),
        selectizeInput("pc_models", "Models (per-class comparison)", choices = comp$Model, multiple = TRUE,
                       selected = unique(c(ov$best_model, "HistGradientBoosting", "Logistic Regression"))),
        selectInput("pc_metric", "Per-class metric", c("Precision", "Recall", "F1"), selected = "Recall")
      ),
      layout_columns(col_widths = c(6, 6),
        card(card_header("Confusion matrix (held-out test set)"), plotlyOutput("cm_plot", height = 400)),
        card(card_header("Per-class comparison"), plotlyOutput("pc_plot", height = 400))
      ),
      layout_columns(col_widths = c(7, 5),
        card(card_header("Common misclassification patterns"), plotlyOutput("err_plot", height = 330)),
        card(card_header("Reading the errors"), uiOutput("err_text"), DTOutput("fpfn_tbl"))
      )
    )
  ),

  # ---- 4. Feature importance ---------------------------------------------------
  nav_panel("Feature importance",
    layout_sidebar(
      sidebar = sidebar(width = 270,
        radioButtons("fi_method", "Method", choices = sort(unique(fimp$Method)), selected = sort(unique(fimp$Method))[2]),
        selectInput("fi_model", "Model", choices = NULL),
        sliderInput("fi_top", "Features shown", min = 5, max = 20, value = 15, step = 1),
        note("Permutation importance = drop in macro-F1 when the feature is shuffled (5 repeats, 5,000 test rows; whiskers = \u00b11 SD). Impurity importance is available for tree models only.")
      ),
      card(card_header("Leading features"), plotlyOutput("fi_plot", height = 520)),
      layout_columns(col_widths = c(7, 5),
        card(card_header("Agreement between models (Spearman \u03c1 of permutation importances)"), DTOutput("fi_agree")),
        card(card_header("Interpretation caution"),
             p("Importance measures how much a ", tags$i("fitted model relies"), " on a feature to reproduce the heuristic label. ",
               tags$b("It does not establish causation"), ", and correlated features share credit."),
             p(class = "mb-0", "Many top features (e.g. days since update, licence flags, age) are ingredients of the label formula, so their importance partly reflects how the label was constructed."))
      )
    )
  ),

  # ---- 5. Repository risk explorer ----------------------------------------------
  nav_panel("Repository explorer",
    layout_sidebar(
      sidebar = sidebar(width = 300,
        textInput("ex_q", "Search repository (owner/name)", placeholder = "e.g. facebook/react"),
        selectizeInput("ex_lang", "Primary language", choices = sort(unique(expl$primary_language)), multiple = TRUE,
                       options = list(placeholder = "All languages")),
        checkboxGroupInput("ex_hclass", "Heuristic risk class (label)", CLASSES, selected = CLASSES),
        checkboxGroupInput("ex_pclass", "Predicted risk class (model)", CLASSES, selected = CLASSES),
        radioButtons("ex_out", "Prediction outcome", c("All", "Correct", "Misclassified"), inline = TRUE),
        sliderInput("ex_days", "Days since last update", 0, ceiling(max(expl$days_since_update, na.rm = TRUE)),
                    value = c(0, ceiling(max(expl$days_since_update, na.rm = TRUE))), step = 30),
        sliderInput("ex_age", "Repository age (years)", 0, ceiling(max(expl$repository_age_years, na.rm = TRUE)),
                    value = c(0, ceiling(max(expl$repository_age_years, na.rm = TRUE))), step = 0.5),
        numericInput("ex_stars", "Minimum stars", value = 0, min = 0, step = 10),
        note(sprintf("Explorer shows the %s held-out test repositories - the only rows with out-of-sample predictions (model: %s).",
                     format(nrow(expl), big.mark = ","), ov$best_model))
      ),
      uiOutput("ex_summary"),
      layout_columns(col_widths = c(12),
        card(card_header("Interactive scatter plot"),
             layout_columns(col_widths = c(3, 3, 3, 3),
               selectInput("ex_x", "X axis", NUM_AXES, selected = "days_since_update"),
               selectInput("ex_y", "Y axis", NUM_AXES, selected = "repository_age_years"),
               selectInput("ex_col", "Colour by", c("Heuristic class (label)" = "heuristic_risk_class",
                                                    "Predicted class (model)" = "predicted_risk_class",
                                                    "Prediction outcome" = "outcome")),
               checkboxGroupInput("ex_log", "Log scale (zeros omitted)", c("X" = "x", "Y" = "y"), inline = TRUE)),
             plotlyOutput("ex_plot", height = 460)),
        card(card_header("Repository table"), DTOutput("ex_tbl"),
             card_footer(class = "small-note", tags$b("Heuristic"), " columns are the training label derived from metadata; ",
                         tags$b("Predicted"), " columns are the model's out-of-sample output. Neither indicates a verified vulnerability or the safety of a repository."))
      )
    )
  ),

  # ---- 6. Statistics & validity ---------------------------------------------------
  nav_panel("Statistics & validity",
    navset_card_tab(
      nav_panel("Confidence intervals",
        layout_sidebar(sidebar = sidebar(width = 250, selectInput("ci_metric", "Metric", METRICS, selected = "F1_macro")),
          plotlyOutput("ci_plot", height = 560))),
      nav_panel("Significance tests",
        note("Paired McNemar exact test on identical test observations; p-values Holm-adjusted within each family. 'Practically meaningful' means an accuracy difference of at least 1 percentage point (threshold fixed a priori)."),
        selectInput("st_family", "Comparison family", choices = unique(stat$Family), width = "100%"),
        DTOutput("st_tbl")),
      nav_panel("Label-validity audit",
        layout_columns(col_widths = c(6, 6),
          card(card_header("Is the label a function of the model inputs?"),
               tags$ul(
                 tags$li(sprintf("Recomputing repository_risk_score from DA2 input columns gives max |error| = %.1e (%s of rows within 1e-6).",
                                 ov$reconstruction$max_abs_error, scales_pct(ov$reconstruction$`share_within_1e-6`))),
                 tags$li(sprintf("Class labels reproduced exactly for %s of repositories.", scales_pct(ov$reconstruction$class_agreement_with_stored_label))),
                 tags$li(sprintf("Best-model errors are most frequent right at the cut-offs (%.1f%% error rate within 0.005 of a cut-off) but are not confined to them: only %.1f%% of errors lie within 0.02 of a cut-off, and the median distance to the nearest cut-off is similar for errors (%.3f) and correct predictions (%.3f).",
                                 100 * f_bnd$error_rate[1], 100 * ov$boundary_summary$`share_errors_within_0.02_of_threshold`,
                                 ov$boundary_summary$median_distance_errors, ov$boundary_summary$median_distance_correct))),
               DTOutput("ovl_tbl")),
          card(card_header("Error rate vs distance to nearest class cut-off"), plotlyOutput("bnd_plot", height = 330))),
        card(card_header("Ablation: performance when label-formula inputs are removed"), plotlyOutput("abl_plot", height = 380),
             card_footer(class = "small-note", "Set A = DA2 predictors; B = without licence/code-of-conduct/archived/days-since-update; C = without any column that enters the label formula. The dummy bar is the class-prior baseline."))
      )
    )
  )
)

# ----------------------------------------------------------------------------- server
server <- function(input, output, session) {

  # ---- Overview
  output$ov_dist <- renderPlotly({
    d <- data.frame(Class = factor(names(ov$class_counts), CLASSES), n = unlist(ov$class_counts))
    plot_ly(d, x = ~Class, y = ~n, type = "bar", marker = list(color = unname(CLS_COL[as.character(d$Class)])),
            text = ~format(n, big.mark = ","), textposition = "outside",
            hovertemplate = "%{x}<br>%{y:,} repositories<extra></extra>") %>%
      layout(yaxis = list(title = "Repositories", rangemode = "tozero"), xaxis = list(title = "")) %>% plot_theme()
  })

  # ---- Model comparison
  output$cmp_plot <- renderPlotly({
    m <- input$metric
    validate(need(length(input$stages) > 0, "Select at least one model variant."))
    d <- comp %>% filter(Stage %in% input$stages) %>% transmute(Model, Stage, value = .data[[m]]) %>%
      left_join(ci %>% filter(Metric == m) %>% select(Model, CI_low, CI_high), by = "Model") %>% arrange(value)
    d$Model <- factor(d$Model, levels = d$Model)
    d$tip <- sprintf("<b>%s</b> (%s)<br>%s: %s<br>95%% CI: %s \u2013 %s", d$Model, d$Stage, metric_label(m),
                     fmt(d$value), fmt(d$CI_low), fmt(d$CI_high))
    lo <- max(0, min(d$CI_low, d$value, na.rm = TRUE) - 0.03)
    plot_ly(d, x = ~value, y = ~Model, color = ~Stage, colors = c(Baseline = STEEL, Tuned = NAVY),
            type = "bar", orientation = "h", hovertext = ~tip, hoverinfo = "text",
            error_x = list(type = "data", symmetric = FALSE, array = ~(CI_high - value), arrayminus = ~(value - CI_low),
                           color = "#555", thickness = 1)) %>%
      layout(xaxis = list(title = metric_label(m), range = c(lo, 1.0)), yaxis = list(title = ""), barmode = "group") %>% plot_theme()
  })

  output$tune_plot <- renderPlotly({
    m <- input$metric
    tuned <- comp %>% filter(Stage == "Tuned") %>% pull(Family)
    d <- comp %>% filter(Family %in% tuned) %>% transmute(Family, Stage, value = .data[[m]])
    d$tip <- sprintf("%s (%s)<br>%s: %s", d$Family, d$Stage, metric_label(m), fmt(d$value))
    plot_ly(d, x = ~Family, y = ~value, color = ~Stage, colors = c(Baseline = STEEL, Tuned = NAVY), type = "bar",
            hovertext = ~tip, hoverinfo = "text") %>%
      layout(barmode = "group", yaxis = list(title = metric_label(m), range = c(max(0, min(d$value) - 0.05), 1)),
             xaxis = list(title = "")) %>% plot_theme()
  })

  output$rank_tbl <- renderDT({
    m <- input$metric
    d <- comp %>% filter(Stage %in% input$stages) %>% arrange(desc(.data[[m]])) %>%
      transmute(Rank = row_number(), Model, Variant = Stage, Value = round(.data[[m]], 4),
                `Fit time (s)` = round(Fit_Time_s, 1))
    datatable(d, rownames = FALSE, options = list(pageLength = 8, dom = "tp"), class = "compact stripe")
  })

  # ---- Classification performance
  output$cm_plot <- renderPlotly({
    d <- cmx %>% filter(Model == input$cm_model)
    validate(need(nrow(d) > 0, "No confusion-matrix data for this model."))
    d$Actual <- factor(d$Actual, CLASSES); d$Predicted <- factor(d$Predicted, CLASSES)
    d <- d %>% arrange(Actual, Predicted)
    zmat <- matrix(if (input$cm_mode == "n") d$Count else d$Row_Pct * 100, 3, 3, byrow = TRUE)
    lab <- matrix(if (input$cm_mode == "n") format(d$Count, big.mark = ",") else sprintf("%.1f%%", d$Row_Pct * 100), 3, 3, byrow = TRUE)
    plot_ly(x = CLASSES, y = CLASSES, z = zmat, type = "heatmap", colorscale = list(c(0, "#F4F7FB"), c(1, NAVY)),
            showscale = FALSE, text = lab, texttemplate = "%{text}", textfont = list(size = 15),
            hovertemplate = "Actual: %{y}<br>Predicted: %{x}<br>%{text}<extra></extra>") %>%
      layout(xaxis = list(title = "Predicted class", side = "bottom"),
             yaxis = list(title = "Actual (heuristic) class", autorange = "reversed")) %>% plot_theme()
  })

  output$pc_plot <- renderPlotly({
    validate(need(length(input$pc_models) > 0, "Select at least one model."))
    d <- cls %>% filter(Model %in% input$pc_models) %>% transmute(Model, Class = factor(Class, CLASSES), value = .data[[input$pc_metric]])
    d$tip <- sprintf("%s<br>%s \u2013 %s: %s", d$Model, d$Class, input$pc_metric, fmt(d$value))
    plot_ly(d, x = ~Class, y = ~value, color = ~Model, type = "bar", hovertext = ~tip, hoverinfo = "text") %>%
      layout(barmode = "group", yaxis = list(title = input$pc_metric, range = c(max(0, min(d$value) - 0.05), 1)), xaxis = list(title = "")) %>% plot_theme()
  })

  err_m <- reactive(err %>% filter(Model == input$cm_model))
  output$err_plot <- renderPlotly({
    d <- err_m() %>% mutate(Pattern = paste0(Actual, " \u2192 ", Predicted)) %>% arrange(Count)
    validate(need(nrow(d) > 0, "No error data for this model."))
    d$Pattern <- factor(d$Pattern, levels = d$Pattern)
    d$tip <- sprintf("%s<br>%s misclassified<br>%.1f%% of this model's errors", d$Pattern, format(d$Count, big.mark = ","), 100 * d$Share_of_all_errors)
    plot_ly(d, x = ~Count, y = ~Pattern, color = ~Error_Type, colors = c("Adjacent classes" = NAVY, "Low<->High (non-adjacent)" = "#E76F51"),
            type = "bar", orientation = "h", hovertext = ~tip, hoverinfo = "text") %>%
      layout(xaxis = list(title = "Test repositories"), yaxis = list(title = "(actual \u2192 predicted)")) %>% plot_theme()
  })
  output$err_text <- renderUI({
    d <- err_m(); tot <- sum(d$Count)
    if (tot == 0) return(p("This model made no errors on the test set."))
    adj <- sum(d$Count[d$Error_Type == "Adjacent classes"]); top <- d[which.max(d$Count), ]
    tagList(p(sprintf("%s test errors in total. %.1f%% are between adjacent classes (Low\u2194Medium or Medium\u2194High); %.1f%% are Low\u2194High confusions.",
                      format(tot, big.mark = ","), 100 * adj / tot, 100 * (1 - adj / tot))),
            p(sprintf("Most frequent pattern: %s \u2192 %s (%.1f%% of errors).", top$Actual, top$Predicted, 100 * top$Count / tot)))
  })
  output$fpfn_tbl <- renderDT({
    d <- rd("class_error_summary.csv") %>% filter(Model == input$cm_model) %>%
      transmute(Class, TP, FP, FN, `FP rate` = round(FPR, 4), `FN rate` = round(FNR, 4))
    datatable(d, rownames = FALSE, options = list(dom = "t"), class = "compact")
  })

  # ---- Feature importance
  observeEvent(input$fi_method, {
    ch <- fimp %>% filter(Method == input$fi_method) %>% pull(Model) %>% unique()
    sel <- if (ov$best_model %in% ch) ov$best_model else ch[1]
    updateSelectInput(session, "fi_model", choices = ch, selected = sel)
  }, ignoreInit = FALSE)
  output$fi_plot <- renderPlotly({
    req(input$fi_model)
    d <- fimp %>% filter(Method == input$fi_method, Model == input$fi_model) %>% arrange(desc(Importance)) %>% head(input$fi_top)
    validate(need(nrow(d) > 0, "No importance values for this model/method."))
    d <- d %>% arrange(Importance); d$Feature <- factor(d$Feature, levels = d$Feature)
    d$tip <- sprintf("<b>%s</b><br>importance: %s%s<br>rank: %d", d$Feature, formatC(d$Importance, format = "f", digits = 4),
                     ifelse(is.na(d$Std), "", sprintf(" (\u00b1%s)", formatC(d$Std, format = "f", digits = 4))), as.integer(d$Rank_within_model_method))
    p <- plot_ly(d, x = ~Importance, y = ~Feature, type = "bar", orientation = "h", marker = list(color = NAVY),
                 hovertext = ~tip, hoverinfo = "text")
    if (!all(is.na(d$Std))) p <- p %>% add_trace(error_x = list(type = "data", array = ~Std, color = "#555"), showlegend = FALSE)
    p %>% layout(xaxis = list(title = if (grepl("Permutation", input$fi_method)) "Mean drop in macro-F1" else "Mean decrease in impurity"),
                 yaxis = list(title = ""), showlegend = FALSE) %>% plot_theme()
  })
  output$fi_agree <- renderDT({
    datatable(f_agr %>% arrange(desc(Spearman_rho)), rownames = FALSE, options = list(pageLength = 6, dom = "tp"), class = "compact stripe")
  })

  # ---- Explorer
  filt <- reactive({
    d <- expl
    q <- trimws(tolower(input$ex_q))
    if (nzchar(q)) d <- d[grepl(q, tolower(d$name_with_owner), fixed = TRUE), ]
    if (length(input$ex_lang) > 0) d <- d[d$primary_language %in% input$ex_lang, ]
    d <- d[d$heuristic_risk_class %in% input$ex_hclass & d$predicted_risk_class %in% input$ex_pclass, ]
    if (input$ex_out != "All") d <- d[d$outcome == input$ex_out, ]
    d <- d[!is.na(d$days_since_update) & d$days_since_update >= input$ex_days[1] & d$days_since_update <= input$ex_days[2], ]
    d <- d[!is.na(d$repository_age_years) & d$repository_age_years >= input$ex_age[1] & d$repository_age_years <= input$ex_age[2], ]
    d[!is.na(d$stars) & d$stars >= (if (is.na(input$ex_stars)) 0 else input$ex_stars), ]
  })
  output$ex_summary <- renderUI({
    d <- filt()
    if (nrow(d) == 0) return(div(class = "alert alert-warning", "No repositories match the current filters. Relax a filter to see results."))
    div(class = "alert alert-light border small-note mb-2",
        sprintf("%s repositories match. Agreement between heuristic class and model prediction in this selection: %.1f%%.",
                format(nrow(d), big.mark = ","), 100 * mean(d$prediction_correct)))
  })
  output$ex_plot <- renderPlotly({
    d <- filt(); validate(need(nrow(d) > 0, "No repositories match the current filters."))
    cap <- 5000; n_all <- nrow(d)
    if (n_all > cap) { set.seed(42); d <- d[sample.int(n_all, cap), ] }
    xv <- d[[input$ex_x]]; yv <- d[[input$ex_y]]
    cc <- input$ex_col
    cols <- if (cc == "outcome") c(Correct = "#2A9D8F", Misclassified = "#E76F51") else CLS_COL
    d$tip <- sprintf("<b>%s</b><br>%s | stars %s<br>days since update %s | age %s y<br>heuristic: %s (%.3f)<br>predicted: %s",
                     d$name_with_owner, d$primary_language, format(d$stars, big.mark = ","), d$days_since_update,
                     d$repository_age_years, d$heuristic_risk_class, d$heuristic_risk_score, d$predicted_risk_class)
    plot_ly(d, x = xv, y = yv, color = d[[cc]], colors = cols, type = "scattergl", mode = "markers",
            marker = list(size = 6, opacity = 0.6), hovertext = d$tip, hoverinfo = "text") %>%
      layout(xaxis = list(title = names(NUM_AXES)[match(input$ex_x, NUM_AXES)], type = if ("x" %in% input$ex_log) "log" else "linear"),
             yaxis = list(title = names(NUM_AXES)[match(input$ex_y, NUM_AXES)], type = if ("y" %in% input$ex_log) "log" else "linear"),
             title = list(text = if (n_all > cap) sprintf("Random sample of %s of %s matching repositories", format(cap, big.mark = ","), format(n_all, big.mark = ",")) else "",
                          font = list(size = 12))) %>% plot_theme()
  })
  output$ex_tbl <- renderDT({
    d <- filt()
    validate(need(nrow(d) > 0, "No repositories match the current filters."))
    d <- d %>% transmute(Repository = name_with_owner, Language = primary_language, License = license, Stars = stars, Forks = forks,
                         `Days since update` = days_since_update, `Age (yrs)` = repository_age_years,
                         `Heuristic score` = heuristic_risk_score, `Heuristic class (label)` = as.character(heuristic_risk_class),
                         `Predicted class (model)` = as.character(predicted_risk_class), `P(High)` = prob_high)
    datatable(d, rownames = FALSE, filter = "none", class = "compact stripe hover", options = list(pageLength = 10, scrollX = TRUE, deferRender = TRUE)) %>%
      formatStyle(c("Heuristic class (label)", "Predicted class (model)"),
                  backgroundColor = styleEqual(CLASSES, c("#D5EFEC", "#FBF1CF", "#FADBD3")))
  })

  # ---- Statistics & validity
  output$ci_plot <- renderPlotly({
    m <- input$ci_metric
    d <- ci %>% filter(Metric == m) %>% arrange(Estimate); d$Model <- factor(d$Model, levels = d$Model)
    d$tip <- sprintf("<b>%s</b><br>%s = %s<br>95%% CI: %s \u2013 %s", d$Model, metric_label(m), fmt(d$Estimate), fmt(d$CI_low), fmt(d$CI_high))
    plot_ly(d, x = ~Estimate, y = ~Model, type = "scatter", mode = "markers", marker = list(color = NAVY, size = 8),
            error_x = list(type = "data", symmetric = FALSE, array = ~(CI_high - Estimate), arrayminus = ~(Estimate - CI_low), color = NAVY),
            hovertext = ~tip, hoverinfo = "text") %>%
      layout(xaxis = list(title = paste(metric_label(m), "(95% bootstrap CI)")), yaxis = list(title = "")) %>% plot_theme()
  })
  output$st_tbl <- renderDT({
    d <- stat %>% filter(Family == input$st_family) %>% arrange(Holm_p) %>%
      transmute(`Model A` = Model_A, `Model B` = Model_B, `Acc. diff (A-B)` = round(Acc_Diff_A_minus_B, 4),
                `95% CI` = sprintf("[%.4f, %.4f]", Acc_Diff_CI_low, Acc_Diff_CI_high),
                `A right / B wrong` = A_right_B_wrong, `A wrong / B right` = A_wrong_B_right,
                `McNemar p` = signif(McNemar_exact_p, 3), `Holm p` = signif(Holm_p, 3),
                `Cohen d_z` = round(Cohen_dz, 3), Interpretation)
    datatable(d, rownames = FALSE, class = "compact stripe", options = list(pageLength = 10, scrollX = TRUE))
  })
  output$ovl_tbl <- renderDT({
    datatable(f_ovl %>% transmute(Predictor, `In label formula` = In_label_formula, `Enters through` = Enters_through),
              rownames = FALSE, class = "compact", options = list(pageLength = 6, dom = "tp"))
  })
  output$bnd_plot <- renderPlotly({
    d <- f_bnd; d$bin <- factor(d$distance_to_nearest_threshold, levels = d$distance_to_nearest_threshold)
    d$tip <- sprintf("distance %s<br>%s test rows, %s errors<br>error rate %.1f%%", d$bin, format(d$n_test_rows, big.mark = ","), format(d$n_errors, big.mark = ","), 100 * d$error_rate)
    plot_ly(d, x = ~bin, y = ~error_rate, type = "bar", marker = list(color = "#E76F51"), hovertext = ~tip, hoverinfo = "text") %>%
      layout(xaxis = list(title = "Distance of risk score to nearest class cut-off"), yaxis = list(title = "Error rate", tickformat = ".0%")) %>% plot_theme()
  })
  output$abl_plot <- renderPlotly({
    d <- f_abl %>% mutate(Set = substr(Predictor_set, 1, 1))
    d$tip <- sprintf("Set %s | %s<br>accuracy %s<br>macro-F1 %s", d$Set, d$Model, fmt(d$Accuracy), fmt(d$F1_macro))
    plot_ly(d, x = ~Model, y = ~F1_macro, color = ~Predictor_set, type = "bar", hovertext = ~tip, hoverinfo = "text") %>%
      layout(barmode = "group", yaxis = list(title = "Macro-F1 (test)", range = c(0, 1)), xaxis = list(title = ""),
             legend = list(orientation = "h", y = -0.3)) %>% plot_theme()
  })
}

shinyApp(ui, server)
