#!/usr/bin/env python3
"""
Builds ONE consolidated report (DA1 + DA2 + DA3) from
  * the original DA1+DA2 Word report (source/GitShield_AI_DA1_DA2_Report.docx) - kept intact (text, tables, 37 figures)
  * the DA3 results (DA3/results/*.csv|json) and figures (report/figures)
Output: DA3/report/GitShield_AI_Consolidated_Report.docx
Run from the repository root:  python DA3/report/build_consolidated_report.py
"""
import copy, json, re
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
R = HERE.parent / "results"; FIG = HERE / "figures"
SRC = HERE / "source" / "GitShield_AI_DA1_DA2_Report.docx"
OUT = HERE / "GitShield_AI_Consolidated_Report.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# ------------------------------------------------------------------ results
comp = pd.read_csv(R / "model_comparison.csv"); ci = pd.read_csv(R / "model_ci.csv")
stat = pd.read_csv(R / "statistical_comparison.csv"); cls = pd.read_csv(R / "class_metrics.csv")
err = pd.read_csv(R / "error_analysis.csv"); fi = pd.read_csv(R / "feature_importance.csv")
abl = pd.read_csv(R / "leakage_ablation.csv"); bnd = pd.read_csv(R / "leakage_boundary_error.csv")
ovl = pd.read_csv(R / "leakage_formula_overlap.csv"); rep = pd.read_csv(R / "reproducibility_check_vs_DA2.csv")
rec = json.load(open(R / "leakage_reconstruction.json")); bsum = json.load(open(R / "leakage_boundary_summary.json"))
cfg = json.load(open(R / "run_config.json")); thr = json.load(open(R / "leakage_threshold_check.json"))
agree = pd.read_csv(R / "feature_importance_agreement.csv")
cv = pd.read_csv(R / "cv_comparison.csv"); cvs = pd.read_csv(R / "cv_significance.csv")
best = comp.loc[0, "Model"]; B = comp.set_index("Model"); CI = ci.set_index(["Model", "Metric"])
N_ALL, NTR, NTE = rec["n_rows"], cfg["n_train"], cfg["n_test"]
cit = lambda m, k: f"{CI.loc[(m, k), 'Estimate']:.4f} (95% CI {CI.loc[(m, k), 'CI_low']:.4f}\u2013{CI.loc[(m, k), 'CI_high']:.4f})"
pfmt = lambda p: "< 0.001" if p < 0.001 else f"{p:.3f}"
eb = err[err.Model == best]; ETOT = int(eb.Count.sum()); ADJ = eb[eb.Error_Type == "Adjacent classes"].Count.sum() / ETOT
HL = eb[(eb.Actual == "High Risk") & (eb.Predicted == "Low Risk")].iloc[0]
HM = eb[(eb.Actual == "High Risk") & (eb.Predicted == "Medium Risk")].iloc[0]
CB = cls[cls.Model == best].set_index("Class").loc[["Low Risk", "Medium Risk", "High Risk"]]

# chapter numbers (continuing the DA1/DA2 numbering 1-21)
CH = dict(overview=22, setup=23, compare=24, stats=25, errors=26, fimp=27, audit=28, dash=29, disc=30, concl=31, limit=32, future=33, refs=34)

doc = Document(SRC)
body = doc.element.body
fig_n, tbl_n = [37], [1]          # last figure / table numbers used in the DA1+DA2 text

# ------------------------------------------------------------------ low-level helpers
def pel(el): return docx_par(el)
def docx_par(el):
    from docx.text.paragraph import Paragraph
    return Paragraph(el, doc)

def set_text(p, text):
    """Replace paragraph text, keeping the first run's formatting."""
    runs = p.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]: r._r.getparent().remove(r._r)
        for pe in p._p.findall(W + "proofErr"): p._p.remove(pe)
    else:
        p.add_run(text)

def replace_in_par(p, old, new):
    full = p.text
    if old not in full: return False
    set_text(p, full.replace(old, new)); return True

def find(prefix, style_prefix=None):
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefix) and (style_prefix is None or p.style.name.startswith(style_prefix)):
            return p
    raise KeyError(prefix)

def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcol); tcPr.append(sh)

def borders(tbl):
    tblPr = tbl._tbl.tblPr; b = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:space"), "0"); e.set(qn("w:color"), "808080"); b.append(e)
    succ = [c for c in tblPr if c.tag in (W + "shd", W + "tblLayout", W + "tblCellMar", W + "tblLook", W + "tblCaption", W + "tblDescription")]
    (succ[0].addprevious(b) if succ else tblPr.append(b))      # keep schema order inside tblPr

def add_page_break_before(p): p.paragraph_format.page_break_before = True

# ------------------------------------------------------------------ DA3 content primitives (append at end of body)
def H1(t): return doc.add_heading(t, level=1)
def H2(t): return doc.add_heading(t, level=2)
def P(t="", bold=False, italic=False, center=False):
    p = doc.add_paragraph(style="Normal (Web)"); r = p.add_run(t); r.bold, r.italic = bold, italic
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    return p
def PR(parts):
    """paragraph from [(text, bold)] runs"""
    p = doc.add_paragraph(style="Normal (Web)"); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for t, b in parts: r = p.add_run(t); r.bold = b
    return p
def BL(items):
    for t in items:
        p = doc.add_paragraph(style="Normal (Web)"); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.2)
        p.add_run("\u2022  " + t)
def CAP(t):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(t); r.italic = True; r.font.size = Pt(10)
    p.paragraph_format.space_after = Pt(10); return p
def T(df, widths, caption, fs=9):
    tbl_n[0] += 1
    t = doc.add_table(rows=1, cols=len(df.columns)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; borders(t)
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(fs); r.font.color.rgb = RGBColor(255, 255, 255); shade(cell, "1F3864")
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; rr = cells[i].paragraphs[0].add_run(str(v)); rr.font.size = Pt(fs)
    t.autofit = False
    for i, w in enumerate(widths): t.columns[i].width = Inches(w)
    for row in t.rows:
        for i, w in enumerate(widths): row.cells[i].width = Inches(w)
    CAP(f"Table {tbl_n[0]}. {caption}")
def F(name, caption, w=6.0):
    fig_n[0] += 1
    doc.add_picture(str(FIG / name), width=Inches(min(w, 6.3))); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    CAP(f"Figure {fig_n[0]}. {caption}")
def SLOT(label):
    t = doc.add_table(rows=1, cols=1); borders(t); c = t.rows[0].cells[0]; shade(c, "F2F2F2"); c.text = ""
    r = c.paragraphs[0].add_run(f"[INSERT SCREENSHOT \u2014 {label}]"); r.italic = True; r.font.color.rgb = RGBColor(0x80, 0x80, 0x80); r.font.size = Pt(10)
    c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER; c.paragraphs[0].paragraph_format.space_before = c.paragraphs[0].paragraph_format.space_after = Pt(26)
    doc.add_paragraph()

def appended_since(anchor):
    out, el = [], anchor.getnext()
    while el is not None and el.tag != W + "sectPr": out.append(el); el = el.getnext()
    return out

def last_body_el(): return body[-2] if body[-1].tag == W + "sectPr" else body[-1]

# =============================================================================================
# 1. Normalise the original document's structure (headings only; text untouched)
# =============================================================================================
TRUE_H = re.compile(r"^\d+(\.\d+)?\.?\s+[A-Z]")
for p in doc.paragraphs:
    t = p.text.strip(); st = p.style.name
    if st.startswith("Heading") and not (t in ("Abstract", "Primary and Secondary Objectives") or (TRUE_H.match(t) and len(t) < 90)):
        p.style = doc.styles["Normal (Web)"] if t else doc.styles["Normal"]          # body text that had been styled as a heading
        if t: p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
for p in doc.paragraphs:
    t = p.text.strip()
    if re.match(r"^\d+\.\s+[A-Z]", t) and len(t) < 90 and p.style.name in ("Normal", "Heading 2"):   # top-level chapter headings
        p.style = doc.styles["Heading 1"]
        for r in p.runs: r.font.size = None; r.font.bold = None; r.font.color.rgb = None
# bullets that had been styled as headings
for key in ("Logarithmic transformation (log1p)", "2 new binary features", "One-hot encoding for primary_language", "Standard scaling of all numerical", "Leakage prevention: repository_risk_score"):
    p = find(key); p.style = doc.styles["Normal (Web)"]; p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.2)
    set_text(p, "\u2022  " + p.text)
# numbering clean-up
set_text(find("Primary and Secondary Objectives"), "3.1 Primary and Secondary Objectives")
set_text(find("19. ROC, Confusion Matrix"), "20. ROC, Confusion Matrix, Precision-Recall and Feature Importance")
set_text(find("13. Feature Engineering"), "13. Feature Engineering for Modelling (DA2)")
set_text(find("21. Results Discussion (DA 2)"), "21. Results Discussion (DA2)")
set_text(find("11. Initial Results and Progress (DA 1)"), "11. Initial Results and Progress (DA1)")

# =============================================================================================
# 2. Title page, abstract, report structure
# =============================================================================================
t3 = find("Digital Assignment 1 (DA1)"); set_text(t3, "Consolidated Project Report: Digital Assignments 1, 2 and 3 (DA1\u2013DA3)")
t4 = find("Dataset Understanding, Data Cleaning"); set_text(t4, "Part I (DA1): Dataset Understanding, Data Cleaning, Feature Engineering and Exploratory Data Analysis")
t5 = find("Combined with Digital Assignment 2"); set_text(t5, "Part II (DA2): Repository Risk Classification, Model Development, Database Connectivity and Comparative Analysis")
t6 = copy.deepcopy(t5._p); t5._p.addnext(t6); set_text(docx_par(t6), "Part III (DA3): Final Evaluation, Statistical Analysis, Validity Audit and Interactive Dashboard")
reg = find("Reg. No."); 
for extra in ("Course: Programming for Data Science, VIT Chennai", "Final submission: 16 October 2026"):
    c = copy.deepcopy(reg._p); reg._p.addnext(c); set_text(docx_par(c), extra); reg = docx_par(c)

abs_paras = [find("Repositories for open-source codes on Github")]
for nxt in ("In the current step, a subset", "The data was explored using descriptive", "These results provided a firm basis"):
    abs_paras.append(find(nxt))
set_text(abs_paras[0], "Repositories for open-source code on GitHub constitute one of the largest, fastest-growing datasets of software artefacts available for empirical analysis. The problem lies in distinguishing repositories that are healthy, sustainable and safe: star counts are a common proxy, but they show popularity, not quality. GitShield AI is a machine learning framework that derives health, growth, sustainability and security-exposure indicators from repository metadata and classifies repositories into Low, Medium and High risk. This consolidated report documents the complete project in three parts: DA1 (data preparation and exploration), DA2 (model development and comparative analysis) and DA3 (final evaluation, statistical analysis, validity audit and an interactive dashboard).")
set_text(abs_paras[1], f"In DA1, a subset of {N_ALL:,} repositories from the Kaggle GitHub Repository Metadata dataset was cleaned and explored, and sixteen features describing popularity, activity, community involvement, maintenance, growth, stability, security exposure and overall risk were engineered. Twenty-four exploratory visualisations showed highly right-skewed popularity metrics that are only weakly related to repository age, and forks and stars that move together almost one-for-one. In DA2, the data were stored in SQLite and retrieved with SQL; a three-class risk target was derived from the heuristic risk score; mutual-information selection kept 20 of 39 features; and twelve classifiers (five of them tuned) were compared on a stratified 80:20 split.")
set_text(abs_paras[2], f"In DA3, all 17 models were re-fitted and evaluated on the same {NTE:,}-repository held-out test set. The MLP Neural Network was best (accuracy {cit(best, 'Accuracy')}; macro-F1 {cit(best, 'F1_macro')}; macro ROC-AUC {cit(best, 'ROC_AUC_macro_ovr')}). Bootstrap confidence intervals and paired McNemar tests with Holm correction show that it is significantly and practically better than the next model family (HistGradientBoosting), but not distinguishable from its own tuned variant; five-fold cross-validation on the training split agrees. Error, feature-importance and leakage analyses were added, and an interactive R Shiny + Plotly dashboard was built on exported results.")
set_text(abs_paras[3], f"A validity audit qualifies these results. The risk label is an exact closed-form function of repository columns that are also model inputs (maximum reconstruction error {rec['max_abs_error']:.1e} over all {N_ALL:,} repositories), so the high scores show that the heuristic is learnable by machine learning, not that real-world repository risk or vulnerability is predicted. With every formula input removed, accuracy falls to about 0.57\u20130.59. GitShield AI is therefore presented as a transparent metadata-analytics framework, not a validated vulnerability scanner.")

# remove the blank padding paragraphs between the abstract and the introduction, then add structure overview
intro = find("1. Introduction", "Heading")
el = abs_paras[3]._p.getnext()
while el is not None and el is not intro._p:
    nxt = el.getnext()
    if el.tag == W + "p" and not docx_par(el).text.strip() and not el.findall(".//" + W + "drawing"): body.remove(el)
    el = nxt

anchor_end = last_body_el()
_sh = H2("Structure of this report"); _sh.paragraph_format.page_break_before = True
struct = pd.DataFrame([
    ["Part I \u2013 DA1", "Chapters 1\u201311", "Problem statement, objectives, dataset, literature review, feature description, preprocessing, feature engineering, exploratory data analysis (24 figures)"],
    ["Part II \u2013 DA2", "Chapters 12\u201321", "SQLite connectivity, modelling features, feature selection, target creation, 12 classifiers, hyper-parameter tuning, comparative metrics and visualisations"],
    ["Part III \u2013 DA3", f"Chapters {CH['overview']}\u2013{CH['disc']}", "Reproducible final evaluation, statistical analysis, error and importance analysis, leakage audit, interactive dashboard, consolidated discussion"],
    ["Consolidated closing", f"Chapters {CH['concl']}\u2013{CH['refs']}, Appendix A", "Conclusion, limitations, future scope, references, reproducibility instructions covering all three parts"]],
    columns=["Part", "Chapters", "Content"])
t_struct_start = last_body_el()
tt = doc.add_table(rows=1, cols=3); borders(tt); tt.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, c in enumerate(struct.columns):
    cell = tt.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(c); r.bold = True; r.font.size = Pt(10); r.font.color.rgb = RGBColor(255, 255, 255); shade(cell, "1F3864")
for _, row in struct.iterrows():
    cells = tt.add_row().cells
    for i, v in enumerate(row): cells[i].text = ""; cells[i].paragraphs[0].add_run(v).font.size = Pt(10)
tt.autofit = False
for i, w in enumerate((1.4, 1.5, 3.7)):
    tt.columns[i].width = Inches(w)
    for row in tt.rows: row.cells[i].width = Inches(w)
P("")
P("Reading note. Parts I and II are the DA1 and DA2 submissions, retained in full. Where the DA3 analysis showed that a DA2 statement needed correction or qualification, the original wording was amended in place and the change is listed in Chapter " + str(CH["disc"]) + ". Figures are numbered consecutively across all parts (Figures 1\u201337 from DA1/DA2, Figures 38 onwards from DA3).", italic=True)
for e in appended_since(anchor_end): intro._p.addprevious(e)                 # structure block sits before Chapter 1
# page break + Part banners
def banner(text, before_el):
    p = doc.add_paragraph(); pPr = p._p.get_or_add_pPr(); bd = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "8"), ("space", "4"), ("color", "1F3864")): bt.set(qn("w:" + k), v)
    bd.append(bt); pPr.append(bd)                      # pBdr first; python-docx then inserts the remaining pPr children in schema order
    p.paragraph_format.page_break_before = True; p.paragraph_format.space_after = Pt(10); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text); r.bold = True; r.font.size = Pt(15); r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    before_el.addprevious(p._p); return p
banner("PART I \u2014 PROJECT PROPOSAL AND DATA PREPARATION (DA1)", intro._p)
banner("PART II \u2014 MODEL DEVELOPMENT, DATABASE CONNECTIVITY AND COMPARATIVE ANALYSIS (DA2)", find("12. Database Connectivity")._p)

# =============================================================================================
# 3. In-place corrections / clarifications to DA1-DA2 text (each is listed in the discussion chapter)
# =============================================================================================
p = find("\u2022  Leakage prevention: repository_risk_score")
p.add_run(f" Note (DA3): the raw inputs of these composite scores (for example days_since_update, licence and code-of-conduct flags, repository_age_years, forks, watchers, pull_requests) remain among the predictors, so the label is still reproducible from the model inputs; see Chapter {CH['audit']}.")
replace_in_par(find("Selected features:"), "days_since_last_update", "days_since_update")
p = find("Per-class performance of MLP Neural Network")
full = p.text; lead = full.split(". ", 1)[0] + "."
rest = (" Low Risk: precision 0.955, recall 0.984. Medium Risk: precision 0.914, recall 0.962. High Risk: precision 0.988, recall 0.905. "
        f"Most errors occur between neighbouring classes ({ADJ*100:.1f}% in the DA3 re-computation; Figure 32), as expected for consecutive slices of a continuous score, "
        f"but not all: {int(HL.Count)} High Risk repositories were predicted as Low Risk (Chapter {CH['errors']}). [Corrected in the consolidated report: the DA2 draft stated that all errors were between neighbouring classes.]")
runs = p.runs; runs[0].text = lead
for r in runs[1:]: r._r.getparent().remove(r._r)
nr = p.add_run(rest); nr.bold = False
p = find("Twenty-four valuable visualizations")
p.add_run(f" [Consolidation note: this validation against abandoned repositories was not carried out in DA2 or DA3; it remains future work, Chapter {CH['future']}.]")

# =============================================================================================
# 4. DA3 chapters 22-30 (built at end of body, then moved before the Conclusion)
# =============================================================================================
mark = last_body_el()
banner_tmp = None
H1(f"{CH['overview']}. DA3 Overview: Scope, Objectives and Evaluation Plan")
P("DA1 prepared and explored the data; DA2 built and compared the classifiers. DA3 completes the project with a reproducible final evaluation, statistical analysis, error and importance analysis, a validity audit of the heuristic target, and an interactive dashboard. Its objectives are:")
BL(["Re-evaluate the twelve DA2 classifiers (and five tuned variants) reproducibly on a single held-out test set.",
    "Quantify uncertainty with bootstrap confidence intervals and test whether differences between models are statistically and practically meaningful.",
    "Analyse errors by class and examine which features the models rely on.",
    "Audit the validity of the heuristic target and the predictor set for leakage.",
    "Deliver an interactive R Shiny + Plotly dashboard driven by exported pipeline outputs."])
PR([("Scope statement. ", True), ("GitShield AI predicts a heuristic, metadata-derived risk category. It does not scan code, detect vulnerabilities or verify that any repository is safe.", False)])

H1(f"{CH['setup']}. Final Experimental Setup and Reproducibility Check")
BL([f"Split: stratified 80:20, random_state = 42 \u2192 {NTR:,} training and {NTE:,} test repositories (unchanged from DA2).",
    "Preprocessing and mutual-information feature selection are fitted on the training split only and applied to the test split.",
    f"Tercile cut-offs were computed on all rows in DA2. Recomputing them on training rows only gives identical cut-offs ({thr['thresholds_train_rows_only'][0]}, {thr['thresholds_train_rows_only'][1]}) and changes {thr['test_labels_that_would_change']} test labels.",
    "Hyper-parameters of the five tuned models are taken from the DA2 grid searches (not repeated); final models are re-fitted on the full training split.",
    "Metrics: accuracy, macro/weighted precision, recall and F1, per-class metrics, one-vs-rest macro ROC-AUC, confusion matrices, fit and predict time.",
    "Selection rule: highest test macro-F1 (ties broken by ROC-AUC). Because 17 candidates are ranked on the same test set, the winner's score is mildly optimistic.",
    f"Reproducibility check: all 17 re-computed accuracies, macro-F1 and ROC-AUC values agree with the stored DA2 results to within {rep[['dAcc', 'dF1', 'dAUC']].abs().max().max():.4f}; the differences are attributable to library-version tie-breaking. No DA2 number was substituted for a re-computed one. The DA2 tables in Chapters 16\u201320 are therefore retained as submitted, and the DA3 tables below show the re-computed values."])

H1(f"{CH['compare']}. Final Comparison of the Classifiers")
t = comp[["Rank_F1", "Model", "Accuracy", "Precision_macro", "Recall_macro", "F1_macro", "ROC_AUC_macro_ovr", "Fit_Time_s"]].copy()
t.columns = ["Rank", "Model", "Accuracy", "Macro P", "Macro R", "Macro F1", "ROC-AUC", "Fit (s)"]
for c in t.columns[2:7]: t[c] = t[c].map("{:.4f}".format)
t["Fit (s)"] = t["Fit (s)"].map("{:.1f}".format)
T(t, [0.4, 2.0, 0.7, 0.62, 0.62, 0.68, 0.68, 0.5], "Held-out test performance of all 17 models (12 baseline + 5 tuned), sorted by macro-F1 (re-computed in DA3).", fs=8.5)
F("fig1_model_comparison.png", "Macro-F1 with 95% bootstrap confidence intervals (2,000 paired resamples).", 5.6)
fam = comp.pivot_table(index="Family", columns="Stage", values="F1_macro").dropna()
P("Hyper-parameter tuning. " + "; ".join(f"{k}: baseline {r['Baseline']:.4f} \u2192 tuned {r['Tuned']:.4f}" for k, r in fam.iterrows()) + ". "
  "Tuning therefore produced no meaningful improvement for any of the five models: the tuned Logistic Regression selected the default C = 1, the tuned Linear SVM differs from the baseline on only two test predictions, "
  "and the tuned MLP changes 213 test predictions without changing accuracy (the two MLP variants differ by a single test repository). The grid searches used only 10,000 training rows and 3-fold CV, which limits their resolution.")

H1(f"{CH['stats']}. Statistical Analysis and Confidence Intervals")
P("Method. Percentile bootstrap (B = 2,000) of the test set, with the same resampled indices used for every model so that differences are paired. Models are compared on identical observations with McNemar's exact test on the discordant pairs, Holm-adjusted within each comparison family. Effect sizes are the accuracy difference with a paired-bootstrap CI, the discordant-pair odds ratio and Cohen's d_z. A difference is called practically meaningful only if it is at least one percentage point (a threshold fixed a priori).")
k = ci[ci.Metric.isin(["Accuracy", "F1_macro", "ROC_AUC_macro_ovr"]) & ci.Model.isin(comp.Model.head(8))].pivot(index="Model", columns="Metric", values=["Estimate", "CI_low", "CI_high"])
rows = [[m] + [f"{k.loc[m, ('Estimate', x)]:.4f} [{k.loc[m, ('CI_low', x)]:.4f}, {k.loc[m, ('CI_high', x)]:.4f}]" for x in ("Accuracy", "F1_macro", "ROC_AUC_macro_ovr")] for m in comp.Model.head(8)]
T(pd.DataFrame(rows, columns=["Model", "Accuracy [95% CI]", "Macro-F1 [95% CI]", "ROC-AUC [95% CI]"]), [1.9, 1.55, 1.55, 1.55], "Bootstrap 95% confidence intervals for the eight leading models.")
s1 = stat[stat.Family.str.startswith("Reference")].copy()
t3 = s1.head(7)
t3 = pd.DataFrame({"Comparator": t3.Model_B, "Acc. diff, MLP \u2212 other (pp) [CI]": [f"{a*100:.2f} [{b*100:.2f}, {c*100:.2f}]" for a, b, c in zip(t3.Acc_Diff_A_minus_B, t3.Acc_Diff_CI_low, t3.Acc_Diff_CI_high)],
                   "MLP right / other wrong": t3.A_right_B_wrong, "MLP wrong / other right": t3.A_wrong_B_right, "Holm p": t3.Holm_p.map(pfmt), "Interpretation": t3.Interpretation.str.replace(" after Holm correction", "")})
T(t3, [1.55, 1.25, 0.7, 0.7, 0.55, 1.5], f"{best} versus the seven next-ranked models (McNemar exact test; Holm family size {int(s1.Family_Size.iloc[0])}).", fs=8)
F("fig5_paired_differences.png", "Paired accuracy differences with 95% bootstrap CIs; the dashed line marks the 1-pp practical margin.", 5.4)
mt = stat[(stat.Model_A == best) & (stat.Model_B == "MLP Neural Network (Tuned)")].iloc[0]; hg = stat[(stat.Model_A == best) & (stat.Model_B == "HistGradientBoosting")].iloc[0]
P(f"Findings. (i) The two MLP variants are statistically indistinguishable (discordant pairs {int(mt.A_right_B_wrong)} vs {int(mt.A_wrong_B_right)}, Holm p = {mt.Holm_p:.2f}); the 'best' label between them rests on a difference of about 0.00004 in macro-F1 and should not be over-interpreted. "
  f"(ii) The MLP exceeds HistGradientBoosting by {hg.Acc_Diff_A_minus_B*100:.2f} pp (95% CI {hg.Acc_Diff_CI_low*100:.2f}\u2013{hg.Acc_Diff_CI_high*100:.2f}; Holm p {pfmt(hg.Holm_p)}), which is both statistically significant and above the 1-pp margin. "
  "(iii) Several comparisons among lower-ranked models are significant but practically small. Statistical significance says only that an observed difference is unlikely under chance on this test set; it does not say the difference would persist for other repository populations.")
cvt = cv.copy()
for c in cvt.columns[1:]: cvt[c] = cvt[c].map("{:.4f}".format)
cvt.columns = ["Model", "Acc mean", "Acc SD", "F1 mean", "F1 SD"]
T(cvt, [2.5, 0.9, 0.9, 0.9, 0.9], "Five-fold stratified cross-validation on the training split (preprocessing and feature selection refitted inside each fold).")
top = cvs.iloc[0]
P(f"Cross-validated comparison. With the Nadeau\u2013Bengio corrected resampled t-test on the five fold scores (Holm-adjusted), the reference (MLP with the DA2 tuned configuration) differs from its closest comparator ({top.Comparator}) by {top.Mean_F1_diff*100:.2f} pp macro-F1 (Holm p = {pfmt(top.Holm_p)}) and from every other cross-validated model (Holm p \u2264 {cvs.Holm_p.max():.3f}). "
  "With only five folds, power is limited and the fold standard deviations are large (about 0.02), so this analysis complements rather than replaces the test-set comparison. Only six representative models were cross-validated, for computational reasons.")
F("fig9_cv.png", "Fold-level macro-F1 in five-fold cross-validation (diamond = mean).", 5.0)

H1(f"{CH['errors']}. Confusion Matrix and Class-Level Error Analysis")
F("fig2_confusion_best.png", f"Confusion matrix of the {best} on the held-out test set (DA3 re-computation).", 3.9)
T(pd.DataFrame({"Class": CB.index, "Precision": CB.Precision.map("{:.4f}".format), "Recall": CB.Recall.map("{:.4f}".format), "F1": CB.F1.map("{:.4f}".format), "Support": CB.Support, "ROC-AUC (OvR)": CB.ROC_AUC_ovr.map("{:.4f}".format)}),
  [1.3, 1.0, 1.0, 1.0, 0.8, 1.1], f"Per-class metrics, {best}.")
P(f"The model makes {ETOT:,} errors on {NTE:,} test repositories. {ADJ*100:.1f}% are between adjacent classes, as expected for an ordinal score cut into bands. The weakest pattern is High Risk recall ({CB.loc['High Risk', 'Recall']:.3f}) despite very high High Risk precision ({CB.loc['High Risk', 'Precision']:.3f}): the model is conservative about assigning High Risk, and High \u2192 Medium accounts for {HM.Share_of_all_errors*100:.1f}% of all errors. "
  f"Of more concern for a risk-screening use, {int(HL.Count)} High Risk repositories ({HL.Share_of_all_errors*100:.1f}% of errors) were labelled Low Risk, so the DA2 statement that all errors are between neighbouring classes does not hold. The strongest pattern is Low Risk recall ({CB.loc['Low Risk', 'Recall']:.3f}).")
F("fig3_per_class.png", "Per-class precision, recall and F1 for five leading models.", 6.3)
F("fig4_error_patterns.png", "Composition of each model's errors by (actual \u2192 predicted) pattern.", 5.6)
P(f"Errors versus distance to the class cut-off. The error rate is {bnd.error_rate.iloc[0]*100:.1f}% when the heuristic score lies within 0.005 of a cut-off, but only {bsum['share_errors_within_0.02_of_threshold']*100:.1f}% of errors lie within 0.02 of a cut-off, and the median distance to the nearest cut-off is similar for errors ({bsum['median_distance_errors']:.3f}) and correct predictions ({bsum['median_distance_correct']:.3f}). "
  "Boundary proximity therefore explains part of the errors but not all of them; the rest reflect the model's imperfect approximation of the score formula away from the cut-offs.")
F("fig7_boundary_error.png", "Test error rate of the best model by distance to the nearest class cut-off.", 4.6)

H1(f"{CH['fimp']}. Feature Importance and Interpretation")
pm = fi[(fi.Model == best) & fi.Method.str.startswith("Perm")].nlargest(6, "Importance")
P("Permutation importance (drop in macro-F1 when a feature is shuffled; 5 repeats on 5,000 test rows) was computed for seven models, and impurity importance for four tree models. Feature names come from the fitted pipeline. "
  f"For the {best} the leading features are " + ", ".join(f"{r.Feature} ({r.Importance:.3f})" for r in pm.itertuples()) + ". "
  f"Rankings agree reasonably across models (pairwise Spearman \u03c1: median {agree.Spearman_rho.median():.2f}, range {agree.Spearman_rho.min():.2f}\u2013{agree.Spearman_rho.max():.2f}).")
F("fig6_feature_importance.png", "Permutation importance of the ten leading features for three models (\u00b1 1 SD over repeats).", 6.0)
P(f"Interpretation caution. Importance describes what a fitted model relies on to reproduce the label; it does not show that a feature causes repository risk, and correlated features (for example has_license and license_Unknown) share credit. Moreover, the most important features are ingredients of the label formula (Chapter {CH['audit']}), so the ranking largely mirrors the formula's weights and normalisations rather than an independently discovered risk factor.", italic=True)

H1(f"{CH['audit']}. Data-Leakage and Target-Validity Audit")
P("This is a supplementary analysis. It does not alter the DA2 methodology or the headline results above.")
nin = int(ovl.In_label_formula.sum())
BL([f"Overlap: {nin} of {len(ovl)} predictor columns are inputs, direct or indirect, to repository_risk_score. The composite scores themselves were correctly excluded from the predictors (Chapter 13), but their raw ingredients were not.",
    f"Exact reconstruction: recomputing the score from the DA2 input columns reproduces the stored value with maximum absolute error {rec['max_abs_error']:.1e} on all {N_ALL:,} rows, and every class label ({rec['class_agreement_with_stored_label']*100:.0f}% agreement).",
    f"Minor DA1/DA2 inconsistency: {rec['da1_da2_code_of_conduct_encoding_mismatch_rows']} repositories have code-of-conduct values (the strings 'None' and 'No Code Of Conduct') that DA1 counts as present but the DA2 feature counts as absent; pandas parsed the literal 'None' as missing for {rec['rows_not_reproduced_if_pandas_NaN_treated_as_missing']} rows.",
    "Consequence: the classifiers approximate a known deterministic function from its inputs. High accuracy shows that the function is learnable; it is not evidence about real-world repository risk."])
a2 = abl.pivot_table(index="Predictor_set", columns="Model", values="Accuracy")
T(pd.DataFrame({"Predictor set": list(a2.index), **{c: a2[c].map("{:.4f}".format).values for c in ["Dummy (class prior)", "Logistic Regression", "HistGradientBoosting", "MLP Neural Network"]}}),
  [2.7, 0.9, 0.9, 0.9, 0.9], "Test accuracy under feature ablation (same split and protocol).", fs=8)
F("fig8_ablation.png", "Macro-F1 by predictor set (A = DA2 predictors; B = without licence, code-of-conduct, archived and recency; C = without any formula input).", 5.0)
P("Even with every formula input removed, models beat the class-prior baseline (about 0.34), plausibly because the remaining metadata (for example commits and repository density) is correlated with the formula inputs (not tested here); this still does not establish that a model captures risk beyond the heuristic. A methodologically corrected design would define the target from information not used as predictors, or validate against independent outcome labels (Chapter " + str(CH["future"]) + ").")

H1(f"{CH['dash']}. Interactive Dashboard (R Shiny + Plotly)")
P("The dashboard is an R Shiny application using Plotly, DT, dplyr and readr. It reads only pre-computed CSV/JSON files exported by the Python pipeline (DA3/dashboard/data); no model is retrained in R, and the data are loaded once at start-up and shared by all sessions.")
T(pd.DataFrame([["Overview", "Dataset size, models evaluated, best model with CIs, class distribution, scope statement"],
                ["Model comparison", "Metric selector (6 metrics), bar chart with CIs, baseline vs tuned, ranking table"],
                ["Classification performance", "Interactive confusion matrix (counts / row %), per-class metrics, error patterns, FP/FN table"],
                ["Feature importance", "Method and model selectors, top-N bar chart, cross-model agreement"],
                ["Repository explorer", "Search; language, class, recency, age and star filters; scatter plot; searchable table with heuristic and predicted classes shown separately"],
                ["Statistics & validity", "CI forest plot, significance tests, label-reconstruction facts, boundary-error and ablation charts"]], columns=["Tab", "Content"]),
  [1.8, 4.8], "Dashboard tabs.", fs=9)
P("Testing. A server-logic test suite (DA3/dashboard/tests/test_server.R) renders every output across all metric, model, method and filter settings, including empty-result cases (64 checks), and the application was launched and served over HTTP. Browser screenshots must be inserted in the slots below by running the dashboard.")
for lab in ("Overview tab", "Model comparison tab", "Classification performance tab (confusion matrix)", "Feature importance tab", "Repository explorer tab", "Statistics & validity tab"): SLOT(lab)

H1(f"{CH['disc']}. Consolidated Results Discussion (DA1\u2013DA3)")
P(f"Modelling. On the DA2 protocol the MLP is the best-supported model (macro-F1 {cit(best, 'F1_macro')}), followed by HistGradientBoosting, tuned Gradient Boosting, Extra Trees and Random Forest. Simple linear models (Logistic Regression {B.loc['Logistic Regression', 'F1_macro']:.3f}) are already strong, which is consistent with a label produced by a smooth weighted formula; AdaBoost ({B.loc['AdaBoost', 'F1_macro']:.3f}) and Gaussian Naive Bayes ({B.loc['Gaussian Naive Bayes', 'F1_macro']:.3f}) do worst. The MLP's advantage is plausibly explained by its ability to approximate this continuous function, and the ablation shows that all of it depends on access to the formula's inputs.")
P("Metrics. Macro-F1 is the selection metric because the three classes matter equally and it penalises poor performance on any one class; accuracy is almost identical here only because the classes are near-balanced. Macro ROC-AUC (one-vs-rest) complements it by measuring ranking quality independent of the decision threshold.")
P("From exploration to modelling. The DA1 findings (heavy right skew, weak popularity\u2013age relation) motivated the log transform and scaling used in DA2, and the DA1 recency, licence and age indicators turn out to be the features the models rely on most (Chapter 27). That continuity is also the source of the validity concern: the engineered indicators that define the label are the same information the classifiers receive.")
PR([("Corrections and clarifications to the DA1/DA2 text, made in place in this consolidated report:", True)])
BL([f"Chapter 21 (per-class performance): the draft said all errors occur between neighbouring classes; the re-computed confusion matrix shows {ADJ*100:.1f}% do, and {int(HL.Count)} High Risk repositories were predicted Low Risk. The figure reference was also corrected from Figure 8 to Figure 32.",
    "Chapter 13 (leakage prevention): the statement that composite scores were excluded is correct, but is now qualified: their raw inputs remain predictors and the label is exactly reproducible (Chapter " + str(CH["audit"]) + ").",
    "Chapter 14: the selected-feature name days_since_last_update was corrected to days_since_update, the name used in the data and code.",
    "Chapter 11: the DA1 plan to validate the indices against abandoned repositories was not carried out; this is recorded as future work.",
    "Chapters 16\u201320 report the DA2 numbers as submitted; DA3 re-computed values differ by at most " + f"{rep[['dAcc', 'dF1', 'dAUC']].abs().max().max():.4f}" + " (library-version tie-breaking). Heading numbering and styles were also normalised (for example, two chapters numbered 19 and no chapter 20 became 19 and 20)."])
P("")
new_da3 = appended_since(mark)
concl = find("22. Conclusion", "Heading")
for e in new_da3: concl._p.addprevious(e)
banner("PART III \u2014 FINAL EVALUATION, STATISTICAL ANALYSIS AND INTERACTIVE DASHBOARD (DA3)", new_da3[0])
# the Part III banner must precede the first DA3 chapter heading (it was inserted before new_da3[0]); fine.

# =============================================================================================
# 5. Consolidated conclusion, limitations, future scope, references, appendix
# =============================================================================================
set_text(concl, f"{CH['concl']}. Conclusion")
cp = find("The end-to-end pipeline has been accomplished in DA2")
set_text(cp, f"The project delivers a complete, reproducible workflow for repository-level analytics. DA1 produced a cleaned, feature-engineered dataset of {N_ALL:,} GitHub repositories and an exploratory analysis; DA2 stored it in SQLite, derived a three-class risk target, selected 20 of 39 features and compared 12 classifiers (5 tuned); and DA3 re-evaluated all models reproducibly, quantified uncertainty, tested differences statistically, analysed errors and feature importance, audited the target for leakage, and built an interactive R Shiny + Plotly dashboard.")
conc_extra = [
    f"The {best} is the best-supported final model (accuracy {cit(best, 'Accuracy')}; macro-F1 {cit(best, 'F1_macro')}; macro ROC-AUC {cit(best, 'ROC_AUC_macro_ovr')}). It is significantly and practically better than the next family, HistGradientBoosting (+{hg.Acc_Diff_A_minus_B*100:.2f} pp, Holm p {pfmt(hg.Holm_p)}), is indistinguishable from its tuned variant, and the ranking is confirmed by cross-validation. Hyper-parameter tuning added no measurable benefit.",
    "Repository-level metadata analytics is a practical and transparent way to summarise maintenance, community and governance signals, and the dashboard makes the comparisons, uncertainty, errors and individual repositories explorable.",
    f"The validity audit sets the limit on what can be claimed. Because the label is an exact function of columns that are also model inputs, the project demonstrates that a heuristic risk score is reproducible by machine learning, not that GitShield AI detects insecure repositories. No claim of validated vulnerability detection is made. With the formula inputs removed, accuracy falls to about 0.57\u20130.59. The project is complete (100%) against the DA1\u2013DA3 deliverables."]
prev = cp._p
for txt in conc_extra:
    e = copy.deepcopy(cp._p); prev.addnext(e); set_text(docx_par(e), txt); prev = e

# limitations + future scope: build, then place after the conclusion, before References
refs_h = find("23. References", "Heading")
mark2 = last_body_el()
H1(f"{CH['limit']}. Limitations")
BL(["Labels are tercile bands of a heuristic score; the models learn to reproduce them, not verified vulnerabilities, and the DA1 plan to validate the indices against abandoned repositories was not carried out.",
    f"Label construction and predictors overlap (Chapter {CH['audit']}); ablated accuracy is much lower.",
    "The dataset is a single snapshot; repository metadata change over time, and test performance does not guarantee generalisation to other repository populations or later snapshots.",
    "The dataset was selected from repositories with at least five stars (six cleaned rows have four), so low-visibility repositories are not represented.",
    "Feature importance is not causal; correlated features share importance.",
    "Missing metadata and class-definition choices (terciles, formula weights) affect results; DA1 and DA2 encode the code-of-conduct field differently for 14 rows.",
    "The test set is used both to rank 17 candidates and to report performance; tuning used a 10,000-row subsample with 3-fold CV.",
    "Cross-validation covers six models only, and the tuned Random Forest and Gradient Boosting configurations were not re-searched in DA3."])
H1(f"{CH['future']}. Future Scope")
PR([("Completed in this project: ", True), ("reproducible evaluation, statistical analysis, error and importance analysis, leakage audit and interactive dashboard.", False)])
PR([("Proposed (not done):", True)])
BL(["Evaluate against independently verified vulnerability or incident labels, and against abandoned-repository outcomes.",
    "Integrate vulnerability databases and dependency scanning.",
    "Temporal validation using later repository snapshots.",
    "Probability calibration and uncertainty estimation.",
    "Repository-level explanations (for example SHAP-style) and a redesigned target that excludes its own inputs.",
    "Periodic dataset refreshes."])
for e in appended_since(mark2): refs_h._p.addprevious(e)

set_text(refs_h, f"{CH['refs']}. References")
ref_ps = []
el = refs_h._p.getnext()
while el is not None and el.tag != W + "sectPr":
    if el.tag == W + "p" and docx_par(el).text.strip(): ref_ps.append(el)
    el = el.getnext()
new_refs = ["Breiman, L. (2001). Random forests. Machine Learning, 45, 5\u201332.",
            "Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. Neural Computation, 10(7), 1895\u20131923.",
            "Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap. Chapman & Hall.",
            "Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65\u201370.",
            "McNemar, Q. (1947). Note on the sampling error of the difference between correlated proportions or percentages. Psychometrika, 12(2), 153\u2013157.",
            "Nadeau, C., & Bengio, Y. (2003). Inference for the generalization error. Machine Learning, 52, 239\u2013281.",
            "Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825\u20132830.",
            "Sievert, C. (2020). Interactive web-based data visualization with R, plotly, and shiny. Chapman & Hall/CRC."]
tmpl = ref_ps[-1]
for txt in new_refs:
    e = copy.deepcopy(tmpl); tmpl.addnext(e); set_text(docx_par(e), txt); ref_ps.append(e)
ref_ps = sorted(ref_ps, key=lambda e: docx_par(e).text.strip().lower())
for e in ref_ps: body.remove(e)
cur = refs_h._p
for e in ref_ps: cur.addnext(e); cur = e

# Appendix A (appended after the references)
H1("Appendix A. Reproducibility and Execution Instructions")
P("Full instructions are in DA3/README.md. In brief, from the repository root:")
BL(["DA2 (unchanged): run_da2.py with gitshield.db, outputs/ and requirements.txt.",
    "pip install -r requirements.txt statsmodels matplotlib python-docx joblib; Rscript -e 'install.packages(c(\"shiny\",\"bslib\",\"plotly\",\"dplyr\",\"readr\",\"DT\",\"jsonlite\"))'",
    "python DA3/evaluation/01_train_and_evaluate.py   (17 models, metrics, predictions)",
    "bash DA3/evaluation/run_all_after_training.sh   (statistics, audit, importance, dashboard export, cross-validation)",
    "python DA3/report/make_figures.py; python DA3/report/build_consolidated_report.py   (figures and this report)",
    "Rscript DA3/dashboard/run.R   (dashboard); Rscript DA3/dashboard/tests/test_server.R   (tests)"])

doc.core_properties.title = "GitShield AI - Consolidated Project Report (DA1-DA3)"
doc.save(OUT); print("saved", OUT)
