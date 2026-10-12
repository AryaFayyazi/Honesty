#!/bin/bash
set -euo pipefail
python scripts/27_report_selection.py stage=resample
python scripts/27_report_selection.py stage=score
python scripts/27_report_selection.py stage=select
