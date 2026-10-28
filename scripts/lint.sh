#!/bin/bash
set -e

echo "Running ruff..."
ruff check app tests

echo "Running black..."
black --check app tests

echo "Running mypy..."
mypy app

echo "All lint checks passed!"
