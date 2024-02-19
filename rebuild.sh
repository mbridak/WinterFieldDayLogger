#!/bin/bash
pip uninstall -y wfdlogger
rm dist/*
python3 -m build
pip install -e .
