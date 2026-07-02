#!/usr/bin/env bash
# Build rfsoc_2026.tar.gz — the field bundle for programming both DACs
# with the 2026 firmware. Unpacking it on the RFSoC reproduces the
# /home/eigsep/eigsep/rfsoc_2026 layout the loader expects: the .dtbo
# lands next to the .fpg (casperfpga requires that pairing when
# programming the PL). The on-board casperfpga checkout is the one
# piece not bundled — it stays on the board.
#
# Called by .github/workflows/release-please.yml to attach the bundle
# to every GitHub Release (stable asset name, per-release provenance
# via the eigsep-field manifest's sha256 pin). Runnable locally too:
#
#   ./scripts/make_rfsoc2026_bundle.sh [out.tar.gz]
set -euo pipefail

OUT=${1:-rfsoc_2026.tar.gz}
# Resolve OUT relative to the caller's cwd before cd'ing to the repo
# root, so `./make_rfsoc2026_bundle.sh /tmp/x.tar.gz` and relative
# paths both do what they look like they do.
case "$OUT" in
    /*) ;;
    *) OUT=$(pwd)/$OUT ;;
esac
cd "$(dirname "$0")/.."

fpgs=(firmware/rfsocdactut_2026_*.fpg)
if [[ ${#fpgs[@]} -ne 1 || ! -f ${fpgs[0]} ]]; then
    echo "expected exactly one 2026 .fpg in firmware/, found: ${fpgs[*]}" >&2
    exit 1
fi
fpg=${fpgs[0]}
dtbo=${fpg%.fpg}.dtbo
if [[ ! -f $dtbo ]]; then
    echo "matching .dtbo missing: $dtbo (must pair with $fpg)" >&2
    exit 1
fi

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/rfsoc_2026"
# interweave_dac_both_x3.npz is the tested default the loader is run
# with in the field; circular.npz is the dual-channel alternative an
# operator can hot-swap to via --npz.
cp scripts/dual_bram_mts_npz_loader.py \
    "$fpg" "$dtbo" \
    waveforms/interweave_dac_both_x3.npz \
    waveforms/circular.npz \
    "$stage/rfsoc_2026/"

tar -C "$stage" -czf "$OUT" rfsoc_2026
echo "wrote $OUT:"
tar -tzf "$OUT"
