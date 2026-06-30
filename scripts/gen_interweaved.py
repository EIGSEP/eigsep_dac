"""Generate two interleaved equal-amplitude comb waveforms for RFSoC DAC loading.

The output npz contains two real-valued integer DAC waveforms:

    data[0]: spectral lines at FFT bins 0, 16, 32, 48, ...
    data[1]: spectral lines at FFT bins 8, 24, 40, 56, ...

for the default T=16. In the combined frequency grid, this gives a delta
function every 8 FFT channels, alternating between the two waveforms.
"""

from argparse import ArgumentParser

import numpy as np

from eigsep_dac.waveform import max_addr_calc


def gen_comb_waveform(
    nsamp,
    spacing,
    offset,
    seed,
    fs=1000e6,
    fmax=250e6,
    include_dc=False,
):
    """Generate a real-valued waveform with equal-amplitude comb lines."""
    rng = np.random.default_rng(seed)

    spec = np.zeros(nsamp, dtype=np.complex128)

    df = fs / nsamp
    kmax = int(np.floor(fmax / df))

    bins = np.arange(offset, kmax + 1, spacing, dtype=int)

    if not include_dc:
        bins = bins[bins != 0]

    # Avoid Nyquist bin. For real waveforms it needs special handling.
    nyquist = nsamp // 2
    bins = bins[bins < nyquist]

    if bins.size == 0:
        raise ValueError("No FFT bins selected. Check spacing, offset, fs, and fmax.")

    phases = rng.uniform(0, 2 * np.pi, size=bins.size)

    # Equal-magnitude positive-frequency lines.
    spec[bins] = np.exp(1j * phases)

    # Hermitian symmetry gives a real-valued time-domain waveform.
    spec[-bins] = np.conj(spec[bins])

    d = np.fft.ifft(spec).real

    return d, bins


def quantize_waveform_shared(d, nbits=14, scale=0.9):
    """Quantize an already normalized waveform without additional rescaling."""
    max_int = 2 ** (nbits - 1) - 1
    return np.round(scale * max_int * d).astype(np.int16)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument("--seed0", type=int, default=816343,
                   help="RNG seed for waveform 0")
    p.add_argument("--seed1", type=int, default=816344,
                   help="RNG seed for waveform 1")
    p.add_argument("--N", type=int, default=256,
                   help="Base samples per period")
    p.add_argument("--T", type=int, default=16,
                   help="Comb spacing in FFT channels")
    p.add_argument("--nbits", type=int, default=14,
                   help="Quantization bits")
    p.add_argument("--scale", type=float, default=0.9,
                   help="Amplitude scale after shared normalization")
    p.add_argument("--fs", type=float, default=1000e6,
                   help="Sample rate in Hz")
    p.add_argument("--fmax", type=float, default=250e6,
                   help="Maximum positive frequency in Hz")
    p.add_argument("--include-dc", action="store_true",
                   help="Include DC bin in waveform 0")
    p.add_argument("--out", type=str,
                   default="waveforms/transmitter_interleaved.npz",
                   help="Output npz path")
    p.add_argument("--plot", action="store_true",
                   help="Show time-domain and FFT plots")
    args = p.parse_args()

    if args.T % 2 != 0:
        raise ValueError("T must be even. For every-8-channel interleaving, use T=16.")

    nsamp = args.N * args.T

    # Waveform 0: bins 0, 16, 32, ...
    d0, bins0 = gen_comb_waveform(
        nsamp=nsamp,
        spacing=args.T,
        offset=0,
        seed=args.seed0,
        fs=args.fs,
        fmax=args.fmax,
        include_dc=args.include_dc,
    )

    # Waveform 1: bins 8, 24, 40, ...
    d1, bins1 = gen_comb_waveform(
        nsamp=nsamp,
        spacing=args.T,
        offset=args.T // 2,
        seed=args.seed1,
        fs=args.fs,
        fmax=args.fmax,
        include_dc=False,
    )

    # Normalize both waveforms with one shared scale factor.
    # This preserves equal spectral amplitude between the two combs.
    common_peak = max(np.max(np.abs(d0)), np.max(np.abs(d1)))

    if common_peak == 0:
        raise ValueError("Generated empty waveform. Check spacing, offset, fs, and fmax.")

    d0 = d0 / common_peak
    d1 = d1 / common_peak

    # Quantize without per-waveform renormalization.
    d0_int = quantize_waveform_shared(d0, nbits=args.nbits, scale=args.scale)
    d1_int = quantize_waveform_shared(d1, nbits=args.nbits, scale=args.scale)

    data = np.stack([d0_int, d1_int], axis=0)

    max_addr = max_addr_calc(N=args.N, T=args.T)

    np.savez(
        args.out,
        data=data,
        data0=d0_int,
        data1=d1_int,
        max_addr=np.array(max_addr),
        bins0=bins0,
        bins1=bins1,
        fs=np.array(args.fs),
        N=np.array(args.N),
        T=np.array(args.T),
    )

    print(f"wrote {args.out}")
    print(f"waveforms={data.shape[0]}")
    print(f"samples_per_waveform={data.shape[1]}")
    print(f"max_addr={max_addr}")
    print(f"df={args.fs / nsamp / 1e6:.6f} MHz")
    print(f"comb spacing={args.T} bins = {args.T * args.fs / nsamp / 1e6:.6f} MHz")
    print(f"interleaved spacing={args.T // 2} bins = {(args.T // 2) * args.fs / nsamp / 1e6:.6f} MHz")
    print(f"waveform 0 first bins: {bins0[:8]}")
    print(f"waveform 1 first bins: {bins1[:8]}")

    if args.plot:
        import matplotlib.pyplot as plt

        freqs = np.fft.fftfreq(nsamp, 1 / args.fs)

        fig, axs = plt.subplots(4, 1, figsize=(10, 10))

        axs[0].plot(d0_int)
        axs[0].set_title("Waveform 0 time domain")

        axs[1].plot(d1_int)
        axs[1].set_title("Waveform 1 time domain")

        for i, d_int in enumerate([d0_int, d1_int]):
            d_fft = np.fft.fft(d_int)
            mag = np.abs(d_fft)

            axs[2 + i].plot(
                np.fft.fftshift(freqs) / 1e6,
                np.fft.fftshift(mag),
            )
            axs[2 + i].set_xlim(0, args.fmax / 1e6)
            axs[2 + i].set_xlabel("MHz")
            axs[2 + i].set_ylabel("|FFT|")
            axs[2 + i].set_title(
                f"Waveform {i} spectrum, 0 to {args.fmax / 1e6:g} MHz"
            )

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
