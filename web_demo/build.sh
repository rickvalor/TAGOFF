#!/usr/bin/env bash
# Stage the built WASM binary and the shared tracker-list data files into
# web_demo/, so it's a fully self-contained static directory ready for
# GitHub Pages (or any static host) -- no server, no build step at serve
# time. Run this after any change to rust_core or the data/ lists, before
# publishing; it is NOT run automatically by anything.
set -euo pipefail
cd "$(dirname "$0")"

cargo +stable-x86_64-pc-windows-gnu build --manifest-path ../wasm_demo/Cargo.toml \
    --target wasm32-unknown-unknown --release

mkdir -p data
cp ../data/tracking_params.txt data/
cp ../data/tracking_domains.txt data/
cp ../wasm_demo/target/wasm32-unknown-unknown/release/tagoff_wasm.wasm .

echo "Staged: web_demo/tagoff_wasm.wasm, web_demo/data/*.txt"
