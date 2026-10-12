#!/bin/bash
# Immutable, checksummed snapshot of all CAPE results (user request 2026-10-05: "save the good results rigorously").
# Full copy (not hardlinks: our scripts rewrite files in place, which would silently alter hardlinked snapshots) of
# results/, docs/, scripts/, src/, configs/, slurm/ and every outputs/ subdir except the regenerable activation caches
# (activations/, xm_feats/: 82 GB, recomputable from rollouts + model weights), for which only a sha256 manifest is kept.
# Each snapshot gets MANIFEST.sha256, is verified with sha256sum -c after copying, and is then made read-only.
set -euo pipefail
SRC=/home/arya/new_safety/cape; OUT=/data/models/cape_ws/archive; TS=$(date +%Y%m%d_%H%M%S); D=$OUT/$TS
mkdir -p "$D"
rsync -a --exclude '__pycache__' --exclude '.pytest_cache' "$SRC"/{results,docs,scripts,src,configs,slurm,README.md,pyproject.toml,requirements.txt} "$D/cape/"
mkdir -p "$D/outputs"
rsync -a --exclude 'activations/' --exclude 'xm_feats/' /data/models/cape_ws/outputs/ "$D/outputs/"
( cd "$D" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
( cd "$D" && sha256sum -c --quiet MANIFEST.sha256 )   # verify the copy before declaring it good
# activation caches: checksum manifest only, only for files newer than the last snapshot's manifest (incremental)
prev=$(ls -d $OUT/2*/ 2>/dev/null | grep -v "$TS" | tail -1 || true)
if [ -n "$prev" ] && [ -f "$prev/ACTIVATIONS.sha256" ]; then
  cat "$prev/ACTIVATIONS.sha256" > "$D/ACTIVATIONS.sha256"   # cat, not cp: the previous snapshot is read-only
  find /data/models/cape_ws/outputs/activations /data/models/cape_ws/outputs/xm_feats -type f -newer "$prev/ACTIVATIONS.sha256" -print0 | xargs -0 -r sha256sum >> "$D/ACTIVATIONS.sha256"
else
  find /data/models/cape_ws/outputs/activations /data/models/cape_ws/outputs/xm_feats -type f -print0 | xargs -0 -r sha256sum > "$D/ACTIVATIONS.sha256"
fi
n=$(wc -l < "$D/MANIFEST.sha256"); sz=$(du -sh "$D" | cut -f1)
chmod -R a-w "$D"
echo "$(date '+%F %T') snapshot $D: $n files, $sz, verified" | tee -a $OUT/ARCHIVE_LOG.txt
