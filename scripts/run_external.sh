#!/bin/bash
# Pass one, then pass two, for the two external inventories (Zenodo eastern
# Himalaya + Sikkim multitemporal). Retraining with them is a separate call:
# they add 243 real positives inside Indian state polygons, 108 of them in
# Arunachal, which the GSI inventory does not cover at all.
cd /Users/utkarsh/Desktop/ml
until ! pgrep -f extract_external_features.py > /dev/null; do sleep 20; done
echo "=== pass one done $(date): $(wc -l < data/susceptibility/features_external.jsonl) rows ==="
./venv/bin/python scripts/extract_external_features2.py
echo "=== pass two done $(date): $(wc -l < data/susceptibility/features2_external.jsonl) rows ==="
