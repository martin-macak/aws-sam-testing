#!/bin/bash

mkdir -p /app
cp -rf /app-src/aws_sam_testing /app/
cp -rf /app-src/tests /app/
cp -rf /app-src/test-stacks /app/
cp -f /app-src/.* /app/ 2>/dev/null || true
cp -f /app-src/* /app/ 2>/dev/null || true


echo "Running make init"
cd /app
ls -l
uv venv --seed
source .venv/bin/activate
git init
make init
make
make test