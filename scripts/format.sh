#!/bin/bash
set -e

echo "Running black..."
black app tests

echo "Running ruff with auto-fix..."
ruff check --fix app tests

echo "Formatting complete!"
