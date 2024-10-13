#!/bin/bash
if [ ! -d '.venv' ]; then
    python -m venv .venv
fi

source .venv/bin/activate

source pip install .