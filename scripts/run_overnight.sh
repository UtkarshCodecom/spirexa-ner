#!/bin/bash
# Pass one, then pass two, then train. The laptop is idle; this is the queue.
cd /Users/utkarsh/Desktop/ml
echo "=== waiting for pass one $(date) ==="
until ! pgrep -f extract_susceptibility_features.py > /dev/null; do sleep 60; done
echo "=== pass one done $(date): $(wc -l < data/susceptibility/features.jsonl) rows ==="

echo "=== pass two $(date) ==="
./venv/bin/python scripts/extract_susceptibility_features2.py
echo "=== pass two done $(date): $(wc -l < data/susceptibility/features2.jsonl) rows ==="

echo "=== training $(date) ==="
./venv/bin/python scripts/train_susceptibility.py
echo "=== finished $(date) ==="
