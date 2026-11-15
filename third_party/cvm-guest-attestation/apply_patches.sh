#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Apply patches/*.patch, in order, onto the upstream submodule. Safe to re-run.
set -e
cd "$(dirname "$0")"
SUB="upstream"
[ -n "$(ls -A "$SUB" 2>/dev/null)" ] || { echo "submodule $SUB is empty: run 'git submodule update --init third_party/cvm-guest-attestation/upstream'" >&2; exit 1; }
PATCHES=( "$PWD"/patches/*.patch )
if git -C "$SUB" diff --quiet HEAD; then
  for p in "${PATCHES[@]}"; do git -C "$SUB" apply --whitespace=nowarn "$p"; echo "applied: ${p##*/}"; done
  exit 0
fi
# Submodule already modified: build the expected result in a scratch index and compare.
TMPIDX="$(mktemp -u)"; trap 'rm -f "$TMPIDX"' EXIT
export GIT_INDEX_FILE="$TMPIDX"
git -C "$SUB" read-tree HEAD
for p in "${PATCHES[@]}"; do git -C "$SUB" apply --cached --whitespace=nowarn "$p"; done
if git -C "$SUB" diff --quiet; then
  echo "already applied (${#PATCHES[@]} patches)"
else
  echo "$SUB has local changes that differ from the patch series; reset it with: git -C $SUB checkout -- ." >&2
  exit 1
fi
