// Builds GitShield_AI_DA3.pptx from slides_data.json + report figures (all values come from DA3/results).
// Usage (from DA3/presentation):  node build_deck.js
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/mnt/skills/public/pptx/scripts/apply_theme.js");
const fs = require("fs"), path = require("path");
const D = JSON.parse(fs.readFileSync("slides_data.json", "utf8"));
const FIG = path.join("..", "report", "figures");

const THEME = { name: "GitShield", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "1B2430", lt1: "FFFFFF", dk2: "1F3A5F", lt2: "F2F5F9", accent1: "1F3A5F", accent2: "8DA9C4", accent3: "2A9D8F", accent4: "E9C46A", accent5: "E76F51", accent6: "5C6B7A", hlink: "1F3A5F", folHlink: "5C6B7A" } };
const pres = new pptxgen(); pres.layout = "LAYOUT_16x9"; pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };
pres.title = "GitShield AI - DA3"; const C = pres.SchemeColor;
const f4 = (x) => x.toFixed(4), pct = (x) => (100 * x).toFixed(1) + "%";

pres.defineSlideMaster({ title: "DARK", background: { color: "1F3A5F" }, objects: [],
  slideNumber: { x: 9.3, y: 5.25, fontSize: 9, color: "8DA9C4" } });
pres.defineSlideMaster({ title: "CONTENT", background: { color: "FFFFFF" },
  objects: [{ rect: { x: 0, y: 0, w: 10, h: 0.85, fill: { color: "F2F5F9" } } }],
  slideNumber: { x: 9.3, y: 5.25, fontSize: 9, color: "5C6B7A" },
  placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.1, w: 9, h: 0.65, fontSize: 24, bold: true, color: "1F3A5F", margin: 0, valign: "middle" }, text: "" } });

const NAVY = "1F3A5F", STEEL = "8DA9C4", TEAL = "2A9D8F", RED = "E76F51", GREY = "5C6B7A";
function content(title, sec) { const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec }); s.addText(title, { x: 0.5, y: 0.1, w: 9, h: 0.65, fontSize: 24, bold: true, color: "1F3A5F", margin: 0, valign: "middle", isTextBox: true, objectName: "Title" }); return s; }
function foot(s, t) { s.addText(t, { x: 0.5, y: 5.2, w: 8.6, h: 0.3, fontSize: 10, color: GREY, italic: true, margin: 0, isTextBox: true }); }

// 1 Title
pres.addSection({ title: "Intro" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Intro" });
s.addText("GitShield AI", { x: 0.7, y: 1.4, w: 8.6, h: 0.9, fontSize: 44, bold: true, color: "FFFFFF", margin: 0, isTextBox: true });
s.addText("Final evaluation & project demonstration (DA3)", { x: 0.7, y: 2.3, w: 8.6, h: 0.5, fontSize: 22, color: "CADCFC", margin: 0, isTextBox: true });
s.addText("Heuristic repository-risk classification from GitHub metadata — what the models learn, and what they do not", { x: 0.7, y: 3.0, w: 8, h: 0.8, fontSize: 15, color: "FFFFFF", margin: 0, isTextBox: true });
s.addText("Programming for Data Science · VIT Chennai · [Name / Reg. No.]", { x: 0.7, y: 4.6, w: 8.6, h: 0.4, fontSize: 12, color: STEEL, margin: 0, isTextBox: true });
s.addNotes("Introduce the project: metadata-based risk categories, not a vulnerability scanner.");

// 2 Problem
pres.addSection({ title: "Method" });
s = content("Problem and motivation", "Method");
s.addText([{ text: "Question: ", options: { bold: true } }, { text: "can public repository metadata be summarised into an interpretable Low / Medium / High risk category?" }],
  { x: 0.5, y: 1.1, w: 9, h: 0.7, fontSize: 18, color: "1B2430", margin: 0, isTextBox: true });
[["Maintenance", "recency, pull requests, archived status"], ["Community", "forks, watchers, topics, maintainers"], ["Exposure signals", "licence, code of conduct, stale code"]].forEach((c, i) => {
  s.addShape(pres.ShapeType.roundRect, { x: 0.5 + i * 3.1, y: 2.0, w: 2.9, h: 1.5, fill: { color: "F2F5F9" }, line: { color: STEEL, width: 1 }, rectRadius: 0.1, objectName: "card" + i });
  s.addText(c[0], { x: 0.65 + i * 3.1, y: 2.1, w: 2.6, h: 0.45, fontSize: 17, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText(c[1], { x: 0.65 + i * 3.1, y: 2.6, w: 2.6, h: 0.8, fontSize: 13, color: "1B2430", margin: 0, isTextBox: true });
});
s.addShape(pres.ShapeType.roundRect, { x: 0.5, y: 3.8, w: 9, h: 1.0, fill: { color: "FDEDE8" }, line: { color: RED, width: 1 }, rectRadius: 0.1, objectName: "scope" });
s.addText("Scope: the class is a heuristic, metadata-derived label. GitShield AI does not scan code, detect vulnerabilities, or verify that a repository is safe.", { x: 0.7, y: 3.85, w: 8.6, h: 0.9, fontSize: 14, bold: true, color: "8A3B28", margin: 0, isTextBox: true, valign: "middle" });

// 3 Architecture
s = content("Architecture and methodology", "Method");
const steps = [["SQLite", "gitshield.db\n" + D.n_total.toLocaleString() + " repos"], ["Preprocess", "log1p, scale,\none-hot, top-20\nMI features"], ["17 models", "12 classifiers\n+ 5 tuned"], ["Evaluate", "bootstrap CIs,\nMcNemar + Holm,\nerror analysis"], ["R Shiny", "Plotly dashboard\nreads CSV only"]];
steps.forEach((t, i) => {
  s.addShape(pres.ShapeType.roundRect, { x: 0.4 + i * 1.88, y: 1.4, w: 1.7, h: 2.1, fill: { color: i === 4 ? NAVY : "F2F5F9" }, line: { color: STEEL, width: 1 }, rectRadius: 0.1, objectName: "step" + i });
  s.addText(t[0], { x: 0.4 + i * 1.88, y: 1.5, w: 1.7, h: 0.45, fontSize: 15, bold: true, align: "center", color: i === 4 ? "FFFFFF" : NAVY, margin: 0, isTextBox: true });
  s.addText(t[1], { x: 0.45 + i * 1.88, y: 2.0, w: 1.6, h: 1.4, fontSize: 12, align: "center", color: i === 4 ? "FFFFFF" : "1B2430", margin: 0, isTextBox: true });
  if (i < 4) s.addText("→", { x: 2.05 + i * 1.88, y: 2.2, w: 0.3, h: 0.4, fontSize: 20, color: GREY, align: "center", margin: 0, isTextBox: true });
});
s.addText("Python does all training and statistics; R reads exported CSVs. Same stratified 80:20 split (seed 42) as DA2.", { x: 0.5, y: 3.9, w: 9, h: 0.7, fontSize: 15, color: "1B2430", margin: 0, isTextBox: true });

// 4 Dataset & target
s = content("Dataset and target construction", "Method");
s.addText([
  { text: D.n_total.toLocaleString() + " GitHub repositories (snapshot)", options: { bullet: true, breakLine: true } },
  { text: "Train " + D.n_train.toLocaleString() + " / test " + D.n_test.toLocaleString() + " (stratified)", options: { bullet: true, breakLine: true } },
  { text: "Target: terciles of repository_risk_score → ~1/3 per class", options: { bullet: true, breakLine: true } },
  { text: "Score = 0.40·exposure + 0.25·(1−maintenance) + 0.20·(1−stability) + 0.15·(1−community)", options: { bullet: true } }],
  { x: 0.5, y: 1.1, w: 5.4, h: 3.0, fontSize: 15, color: "1B2430", paraSpaceAfter: 8, margin: 0, isTextBox: true, valign: "top" });
s.addShape(pres.ShapeType.roundRect, { x: 6.2, y: 1.2, w: 3.3, h: 2.6, fill: { color: "FDEDE8" }, line: { color: RED, width: 1 }, rectRadius: 0.1, objectName: "audit-card" });
s.addText("Audit finding", { x: 6.4, y: 1.3, w: 3, h: 0.4, fontSize: 15, bold: true, color: "8A3B28", margin: 0, isTextBox: true });
s.addText("The label can be recomputed exactly from DA2's input columns (max error " + D.maxerr.toExponential(1) + ", all " + D.n_total.toLocaleString() + " rows).", { x: 6.4, y: 1.75, w: 2.95, h: 2.0, fontSize: 13, color: "1B2430", margin: 0, isTextBox: true, valign: "top" });
foot(s, "Models receive the raw ingredients of the formula, not the composite scores themselves.");

// 5 Setup
s = content("Experimental setup", "Method");
s.addTable([[{ text: "Item", options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } }, { text: "Choice", options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } }],
  ["Test set", D.n_test.toLocaleString() + " held-out repositories, same for all models"], ["Tuning", "DA2 GridSearchCV (3-fold, macro-F1, 10k subsample); not repeated"],
  ["Metrics", "Accuracy, macro P/R/F1, per-class, one-vs-rest macro ROC-AUC"], ["Uncertainty", "2,000 paired bootstrap resamples → 95% CIs"],
  ["Tests", "McNemar exact, Holm correction, 1-pp practical margin; 5-fold CV (Nadeau–Bengio)"], ["Check", "Re-computed results match stored DA2 values within 0.0011"]],
  { x: 0.5, y: 1.1, w: 9, colW: [1.8, 7.2], fontSize: 13, color: "1B2430", border: { type: "solid", color: "D5DCE6", pt: 1 }, rowH: 0.5 });

// 6 Model comparison (native chart)
pres.addSection({ title: "Results" });
s = content("Model comparison: MLP leads, tuning adds nothing", "Results");
const mm = D.models.slice().reverse();
s.addChart(pres.charts.BAR, [{ name: "Macro-F1", labels: mm.map(m => m[0]), values: mm.map(m => m[1]) }],
  { x: 0.4, y: 0.95, w: 6.2, h: 4.2, barDir: "bar", chartColors: [NAVY], showLegend: false, showValue: true, dataLabelFormatCode: "0.000", dataLabelFontSize: 9, dataLabelPosition: "outEnd",
    valAxisMinVal: 0.8, valAxisMaxVal: 1.0, valAxisLabelFontSize: 9, catAxisLabelFontSize: 9, valGridLine: { color: "E3E8EF", size: 0.5 }, catGridLine: { style: "none" }, showTitle: true, title: "Top 12 of 17 models, test macro-F1", titleFontSize: 11, titleColor: GREY });
s.addText([{ text: "Best: " + D.best, options: { bold: true, breakLine: true } }, { text: "Accuracy " + f4(D.acc) + " [" + f4(D.acc_ci[0]) + ", " + f4(D.acc_ci[1]) + "]", options: { breakLine: true } },
  { text: "Macro-F1 " + f4(D.f1) + " [" + f4(D.f1_ci[0]) + ", " + f4(D.f1_ci[1]) + "]", options: { breakLine: true } }, { text: "ROC-AUC " + f4(D.auc) }],
  { x: 6.8, y: 1.2, w: 2.8, h: 1.7, fontSize: 13, color: "1B2430", margin: 0, isTextBox: true, valign: "top", paraSpaceAfter: 4 });
s.addText("Tuned and untuned MLP differ by one test repository.", { x: 6.8, y: 3.2, w: 2.7, h: 0.9, fontSize: 13, italic: true, color: GREY, margin: 0, isTextBox: true, valign: "top" });

// 7 Stats + errors
s = content("Statistical and error analysis", "Results");
s.addText([
  { text: "MLP vs HistGradientBoosting: +" + (100 * D.hg_diff).toFixed(2) + " pp (95% CI " + (100 * D.hg_lo).toFixed(2) + "–" + (100 * D.hg_hi).toFixed(2) + "), Holm p < 0.001: significant and ≥ 1 pp", options: { bullet: true, breakLine: true } },
  { text: "MLP vs tuned MLP: no significant difference (Holm p = " + D.mlp_vs_tuned_p.toFixed(2) + ")", options: { bullet: true, breakLine: true } },
  { text: pct(D.adj) + " of errors are between adjacent classes", options: { bullet: true, breakLine: true } },
  { text: "High Risk recall " + D.high_recall.toFixed(3) + " vs precision " + D.high_prec.toFixed(3) + ": model under-calls High", options: { bullet: true, breakLine: true } },
  { text: "Error rate " + pct(D.band_err) + " within 0.005 of a class cut-off", options: { bullet: true } }],
  { x: 0.5, y: 1.05, w: 5.0, h: 3.9, fontSize: 13.5, color: "1B2430", paraSpaceAfter: 8, margin: 0, isTextBox: true, valign: "top" });
s.addImage({ path: path.join(FIG, "fig2_confusion_best.png"), x: 5.7, y: 1.0, w: 3.9, h: 3.28 });
foot(s, "Statistical significance ≠ practical significance; neither implies generalisation to other populations.");

// 8 Dashboard
pres.addSection({ title: "Dashboard" });
s = content("Interactive dashboard (R Shiny + Plotly)", "Dashboard");
const tabs = [["Overview", "dataset, best model + CIs"], ["Model comparison", "6 metrics, tuned vs untuned"], ["Classification", "confusion matrix, per-class, errors"], ["Feature importance", "model + method selectors"], ["Repository explorer", "search, filters, scatter, table"], ["Statistics & validity", "CIs, tests, label audit"]];
tabs.forEach((t, i) => { const x = 0.5 + (i % 3) * 3.1, y = 1.1 + Math.floor(i / 3) * 1.45;
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 2.9, h: 1.25, fill: { color: "F2F5F9" }, line: { color: STEEL, width: 1 }, rectRadius: 0.1, objectName: "tab" + i });
  s.addText(t[0], { x: x + 0.15, y: y + 0.1, w: 2.6, h: 0.4, fontSize: 15, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText(t[1], { x: x + 0.15, y: y + 0.55, w: 2.6, h: 0.6, fontSize: 12, color: "1B2430", margin: 0, isTextBox: true, valign: "top" }); });
s.addText("Live demo: Rscript DA3/dashboard/run.R   ·   reads exported CSVs only; 64 server-logic checks pass.", { x: 0.5, y: 4.15, w: 9, h: 0.5, fontSize: 14, color: "1B2430", margin: 0, isTextBox: true });
s.addNotes("Demo order: Overview -> Model comparison (switch metric) -> Confusion matrix -> Repository explorer (filter High Risk + Misclassified) -> Statistics & validity (ablation).");

// 9 Findings
pres.addSection({ title: "Conclusions" });
s = content("Findings: what the high accuracy does and does not mean", "Conclusions");
s.addChart(pres.charts.BAR, [
  { name: "Logistic Regression", labels: ["A: full DA2 predictors", "B: no licence/CoC/archived/recency", "C: no formula input"], values: ["A|Logistic Regression", "B|Logistic Regression", "C|Logistic Regression"].map(k => D.abl[k]) },
  { name: "HistGradientBoosting", labels: ["A", "B", "C"], values: ["A|HistGradientBoosting", "B|HistGradientBoosting", "C|HistGradientBoosting"].map(k => D.abl[k]) },
  { name: "MLP", labels: ["A", "B", "C"], values: ["A|MLP Neural Network", "B|MLP Neural Network", "C|MLP Neural Network"].map(k => D.abl[k]) }],
  { x: 0.4, y: 0.95, w: 5.6, h: 4.1, barDir: "col", barGrouping: "clustered", chartColors: [TEAL, STEEL, NAVY], showLegend: true, legendPos: "b", legendFontSize: 9, showValue: true, dataLabelFormatCode: "0.00", dataLabelFontSize: 8,
    valAxisMinVal: 0, valAxisMaxVal: 1, valAxisLabelFontSize: 9, catAxisLabelFontSize: 9, valGridLine: { color: "E3E8EF", size: 0.5 }, catGridLine: { style: "none" }, showTitle: true, title: "Test accuracy under feature ablation (class-prior baseline ≈ 0.34)", titleFontSize: 10, titleColor: GREY });
s.addText([
  { text: "The models learn the heuristic formula from its inputs.", options: { bold: true, breakLine: true } },
  { text: "Top features (days since update, licence, age) are formula ingredients.", options: { bullet: true, breakLine: true } },
  { text: "Importance ≠ causation.", options: { bullet: true, breakLine: true } },
  { text: "Without formula inputs accuracy drops to ~0.57–0.59.", options: { bullet: true } }],
  { x: 6.2, y: 1.2, w: 3.4, h: 3.2, fontSize: 13, color: "1B2430", paraSpaceAfter: 8, margin: 0, isTextBox: true, valign: "top" });

// 10 Limitations / future / conclusion
s = content("Limitations, future scope and conclusion", "Conclusions");
s.addText("Limitations", { x: 0.5, y: 1.0, w: 4.3, h: 0.35, fontSize: 15, bold: true, color: NAVY, margin: 0, isTextBox: true });
s.addText([{ text: "Heuristic, tercile-based labels", options: { bullet: true, breakLine: true } }, { text: "Predictors overlap the label formula", options: { bullet: true, breakLine: true } }, { text: "Single snapshot, ≥ ~5-star repositories", options: { bullet: true, breakLine: true } }, { text: "Test set used to rank 17 models", options: { bullet: true } }],
  { x: 0.5, y: 1.4, w: 4.3, h: 1.8, fontSize: 13, color: "1B2430", paraSpaceAfter: 5, margin: 0, isTextBox: true, valign: "top" });
s.addText("Future scope (proposed)", { x: 5.1, y: 1.0, w: 4.4, h: 0.35, fontSize: 15, bold: true, color: NAVY, margin: 0, isTextBox: true });
s.addText([{ text: "Validate on independent vulnerability labels", options: { bullet: true, breakLine: true } }, { text: "Vulnerability DB / dependency scanning", options: { bullet: true, breakLine: true } }, { text: "Temporal validation, calibration", options: { bullet: true, breakLine: true } }, { text: "Target that excludes its own inputs", options: { bullet: true } }],
  { x: 5.1, y: 1.4, w: 4.4, h: 1.8, fontSize: 13, color: "1B2430", paraSpaceAfter: 5, margin: 0, isTextBox: true, valign: "top" });
s.addShape(pres.ShapeType.roundRect, { x: 0.5, y: 3.5, w: 9, h: 1.4, fill: { color: NAVY }, rectRadius: 0.1, objectName: "conclusion" });
s.addText("The MLP is the best-supported model (macro-F1 " + f4(D.f1) + "), but the project shows a heuristic is reproducible by ML — not that GitShield AI detects insecure repositories.", { x: 0.75, y: 3.55, w: 8.5, h: 1.3, fontSize: 16, bold: true, color: "FFFFFF", margin: 0, isTextBox: true, valign: "middle" });

(async () => { await pres.writeFile({ fileName: "GitShield_AI_DA3.pptx" }); await applyTheme("GitShield_AI_DA3.pptx", THEME); console.log("deck written"); })();
