# eigsep_dac

Standalone repo for programming an RFSoC2x2 DAC to emit a pseudorandom waveform.
The RFSoC runs `rfsocdac.py` at boot; it loads the firmware from `firmware/`
and the waveform data from an npz under `waveforms/`.

## Entry points

| Goal                          | Command                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| Program the board             | `python scripts/program_rfsoc.py --ip <board> --npz waveforms/transmitter.npz` |
| Program both DACs (2026)      | see [Programming both DACs](#programming-both-dacs-2026-firmware) |
| Generate the default waveform | `python scripts/gen_pseudorandom_npz.py`                   |
| Search for a new seed (slow!) | `python scripts/search_pseudorandom_seed.py --start 200000 --stop 2000000` |

## Layout

```
firmware/        golden .fpg/.dtbo, loaded at boot
waveforms/       golden npz files — hot-swap by pointing --npz elsewhere
src/eigsep_dac/  importable package (waveform helpers, board programmer body)
scripts/         CLI entry points; archive/ holds sketches + preserved tools
notebooks/       rfsocdac.ipynb for bring-up; exploration/ for R&D; archive/ for preserved
rfsocdac.py      shim that forwards to eigsep_dac.program_board:main (boot entry)
```

## Install (dev machine)

```
pip install -e .[dev]
```

## npz schema

All waveform npz files produced here have two arrays:

- `data` — integer array, `N * T` samples
- `max_addr` — scalar int, `N * T / 4 − 3` (2-clk-delay-compensated DAC address)

## Boot behaviour

The RFSoC invokes `rfsocdac.py` at boot via its systemd unit. That file is
currently a two-line shim into `eigsep_dac.program_board.main`. To swap
waveforms in the field, change the `--npz` argument in the unit file and
reboot. A future rename to `scripts/program_rfsoc.py` requires updating the
unit file on the board in lockstep.

## Programming both DACs (2026 firmware)

On boot the board still runs last year's setup: `rfsocdac.py` transmits the
2025 waveform on the DAC2 output only. To transmit on **both** DAC outputs,
program the 2026 firmware after boot. Everything needed is staged on the
board in `/home/eigsep/eigsep/rfsoc_2026`; from that directory run:

```
sudo /home/eigsep/miniconda3/envs/py310/bin/python \
    /home/eigsep/eigsep/rfsoc_2026/dual_bram_mts_npz_loader.py \
    --fpg rfsocdactut_2026_2026-05-21_1047.fpg \
    --npz interweave_dac_both_x3.npz \
    --once
```

Notes:

- `--fpg` accepts a path, but the matching `.dtbo` **must sit in the same
  directory as the `.fpg`** — casperfpga looks for it next to the fpg when
  programming the PL.
- The loader hard-codes the on-board casperfpga checkout at
  `/home/eigsep/eigsep/rfsoc_2026/casperfpga` (`sys.path` insert at the top
  of the script); that checkout must stay in place. It is the one piece not
  tracked in this repo.
- `--once` loads the waveform pair once and exits. Without it, the script
  keeps polling the `wave_form` select register and reloads on change.
- The loader runs MTS on both DAC tiles and reprograms the FPGA (up to
  `--max-fpga-reloads`, default 5) until the tile latencies come back clean.
- The npz needs `data0`/`data1` keys or a 2D `data` of shape (2, N)/(N, 2);
  `waveforms/interweave_dac_both_x3.npz` and `waveforms/circular.npz` both
  qualify. The single-channel `waveforms/transmitter.npz` does not.

Every GitHub Release attaches `rfsoc_2026.tar.gz`
(built by `scripts/make_rfsoc2026_bundle.sh`): the loader script, the
2026 `.fpg`/`.dtbo` pair, and both dual-channel npz files. Unpacking it
on the board reproduces the `rfsoc_2026/` layout above (minus the
casperfpga checkout). The eigsep-field manifest pins this asset for
field deployments.

Everything in the on-board directory is tracked in this repo:

| On the board (`rfsoc_2026/`)           | In this repo                            |
| -------------------------------------- | --------------------------------------- |
| `dual_bram_mts_npz_loader.py`           | `scripts/dual_bram_mts_npz_loader.py`    |
| `rfsocdactut_2026_2026-05-21_1047.fpg`  | `firmware/` (with the matching `.dtbo`)  |
| `interweave_dac_both_x3.npz`            | `waveforms/interweave_dac_both_x3.npz`   |
| `casperfpga/` checkout                  | not tracked here (EIGSEP casperfpga fork) |

## Field operation

### Serial console (2025-07-10)

When the board is unreachable over the network, get a serial console over
USB:

1. Connect a micro-USB cable from the laptop to the RFSoC.
2. `sudo minicom -D /dev/ttyUSB1 -b 115200`
3. Hit enter after the screen opens to get a login prompt
   (`localhost login`).
4. Two prompts appear in sequence: `cuspl` first, then `eigsep`. Enter a
   **wrong password at the `cuspl` prompt** to fall through to the `eigsep`
   prompt — that is the one that actually logs you in. Get the `eigsep`
   password from the team out-of-band; it is not stored in this repo.

### Clock

Sample clock should read **250 MHz**. A reading of 245.76 MHz indicates
something is wrong (likely a reference-clock issue) and needs to be
corrected.

### Power draw (12 V supply)

Measured with three 15 V amplifiers in the chain, all supplied at 12 V:

| State      | Current |
| ---------- | ------- |
| RFSoC on   | 1.37 A  |
| RFSoC off  | 0.10 A  |
