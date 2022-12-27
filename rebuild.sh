#!/bin/bash
pip uninstall wfdlogger
rm dist/*
python -m build
pip install -e .

python -m twine upload dist/*
