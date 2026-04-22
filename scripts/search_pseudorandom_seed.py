"""Slow brute-force search for a seed whose spectrum best matches a Dirac comb.

Minimises MSE between the tiled-waveform power spectrum and a unit comb with a
tooth at every `T`-th bin. Prints each improving seed to stdout. Pipe the
best seed into `gen_pseudorandom_npz.py --seed`.

No defaults for --start/--stop on purpose: invocation must be explicit.
"""

from argparse import ArgumentParser

import numpy as np

from eigsep_dac.waveform import (
    gen_flat_spectrum_waveform,
    round_waveform,
    tile_waveform,
)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument("--start", type=int, required=True, help="First seed to try")
    p.add_argument("--stop", type=int, required=True, help="Last seed (exclusive)")
    p.add_argument("--N", type=int, default=256)
    p.add_argument("--T", type=int, default=16)
    p.add_argument("--nbits", type=int, default=14)
    p.add_argument("--scale", type=float, default=0.9)
    p.add_argument("--progress-every", type=int, default=10000,
                   help="Print a heartbeat every N seeds")
    args = p.parse_args()

    N, T = args.N, args.T
    goal_spec = np.zeros(N * T)
    goal_spec[T::T] = 1
    goal_spec[N * T // 2] = 0

    best_seed = None
    best = np.inf
    for seed in range(args.start, args.stop):
        d = gen_flat_spectrum_waveform(N, seed=seed)
        d_int = round_waveform(d, nbits=args.nbits, scale=args.scale)
        d_repeat = tile_waveform(d_int, T)
        repeat_fft = np.fft.fft(d_repeat)
        p_spec = np.abs(repeat_fft) ** 2
        peak = np.mean(p_spec[T:12 * T:T])
        p_spec /= peak
        score = float(np.mean(np.abs(p_spec - goal_spec) ** 2))
        if score < best:
            print(f"improve seed={seed} score={score:.6e}", flush=True)
            best = score
            best_seed = seed
        if args.progress_every and (seed - args.start) % args.progress_every == 0:
            print(f"... seed={seed} best_so_far={best_seed} score={best:.6e}",
                  flush=True)

    print(f"\nbest_seed={best_seed} score={best:.6e}")


if __name__ == "__main__":
    main()
