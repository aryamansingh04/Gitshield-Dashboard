#!/usr/bin/env bash
# Runs steps 2-5 sequentially (step 1 must have been run first). From the repository root:  bash DA3/evaluation/run_all_after_training.sh
set -e
cd "$(dirname "$0")"
python 02_statistics.py          | tee ../results/run_02.log
python 04_leakage_audit.py       | tee ../results/run_04.log
python 03_feature_importance.py  | tee ../results/run_03.log
python 05_export_dashboard_data.py | tee ../results/run_05.log
python 03b_cv_comparison.py      | tee ../results/run_03b.log
