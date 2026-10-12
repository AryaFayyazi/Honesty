#!/bin/bash
# v11 exploration: calibrate steering direction/strength on v2fresh alarm sites (selection rule fixed in prereg v11).
set -euo pipefail
python scripts/24_steer_branch.py stage=steer out=outputs/steer/calib "arms=[none,random:27,caa:13,caa:27,caa:54,dprobe:13,dprobe:27,dprobe:54]" batch_size=24
python scripts/24_steer_branch.py stage=continue out=outputs/steer/calib
python scripts/24_steer_branch.py stage=analyze out=outputs/steer/calib
