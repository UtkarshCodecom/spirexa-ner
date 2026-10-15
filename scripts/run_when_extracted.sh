#!/bin/bash
# Waits for the susceptibility extraction to finish, then trains.
# The laptop is idle overnight; this is what it does with the time.
cd /Users/utkarsh/Desktop/ml
until ! pgrep -f extract_susceptibility_features > /dev/null; do sleep 60; done
echo "=== extraction finished $(date) ===" 
wc -l data/susceptibility/features.jsonl
echo "=== training $(date) ==="
./venv/bin/python scripts/train_susceptibility.py
echo "=== done $(date) ==="
