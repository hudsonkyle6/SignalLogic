#!/usr/bin/env bash

cd "/c/Users/SignalADmin/Signal Archive/SignalLogic" || exit 1

# Force UTF-8 for ALL Python processes (including subprocesses)
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

PYTHONPATH=. python -u apps/run_cycle_once.py | tee -a logs/signal.log
