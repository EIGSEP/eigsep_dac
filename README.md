# eigsep_dac

Standalone repo for programming an RFSoC2x2 DAC to emit a pseudorandom waveform.
The RFSoC runs `rfsocdac.py` at boot; it loads the firmware from `firmware/`
and the waveform data from an npz under `waveforms/`.

## Entry points

| Goal                          | Command                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| Program the board             | `python scripts/program_rfsoc.py --ip <board> --npz waveforms/transmitter.npz` |
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
