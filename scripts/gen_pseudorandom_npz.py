"""Generate the pseudorandom waveform npz that the RFSoC DAC loads.

Defaults reproduce the golden `waveforms/transmitter.npz` (seed 816343).
"""

from argparse import ArgumentParser

import numpy as np

from eigsep_dac.waveform import (
    gen_flat_spectrum_waveform,
    max_addr_calc,
    round_waveform,
    tile_waveform,
)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=816343,
                   help="RNG seed (default reproduces transmitter.npz)")
    p.add_argument("--N", type=int, default=256, help="Samples per period")
    p.add_argument("--T", type=int, default=16, help="Tile count")
    p.add_argument("--nbits", type=int, default=14, help="Quantization bits")
    p.add_argument("--scale", type=float, default=0.9, help="Amplitude scale")
    p.add_argument("--out", type=str, default="waveforms/transmitter.npz",
                   help="Output npz path")
    p.add_argument("--plot", action="store_true", help="Show time + FFT plots")
    args = p.parse_args()

    d = gen_flat_spectrum_waveform(N=args.N, seed=args.seed)
    d_int = round_waveform(d, nbits=args.nbits, scale=args.scale)
    d_repeat = tile_waveform(d_int, T=args.T)
    max_addr = max_addr_calc(N=args.N, T=args.T)

    np.savez(args.out, data=d_repeat, max_addr=np.array(max_addr))
    print(f"wrote {args.out}  samples={d_repeat.size}  max_addr={max_addr}")

    if args.plot:
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
        ax1.plot(d_repeat)
        ax1.set_title("Waveform (time)")
        d_fft = np.fft.fft(d_repeat)
        freqs = np.fft.fftfreq(d_fft.size, 1 / 1000e6)
        ax2.plot(np.fft.fftshift(freqs) / 1e6, np.fft.fftshift(np.abs(d_fft)))
        ax2.set_xlabel("MHz")
        ax2.set_title("Spectrum")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
