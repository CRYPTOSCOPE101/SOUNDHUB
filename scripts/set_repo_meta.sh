#!/usr/bin/env bash
# Set the GitHub repository metadata: description, homepage, topics.
#
# Requires the GitHub CLI (gh) and a login:  gh auth login
# Usage: bash scripts/set_repo_meta.sh
set -euo pipefail

REPO="${1:-soundXlab/SoundHub}"

gh repo edit "$REPO" \
  --description "SoundHub — a tokenized marketplace for finished sounds (presets, loops, stems, packs). Buy, don't generate. 🎛" \
  --homepage "https://github.com/soundXlab/SoundHub" \
  --add-topic music \
  --add-topic marketplace \
  --add-topic ableton-live \
  --add-topic max-for-live \
  --add-topic daw \
  --add-topic web3 \
  --add-topic ethereum \
  --add-topic base \
  --add-topic nft \
  --add-topic fastapi \
  --add-topic react \
  --add-topic solidity \
  --add-topic hardhat

echo "Done: description, homepage and topics set on $REPO"
