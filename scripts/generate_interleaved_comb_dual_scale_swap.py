"""Generate two interleaved comb waveforms for RFSoC DAC loading.

This standalone version adds --swap-combs.

Default assignment:

    data[0] / data0: spectral lines at FFT bins 0, T, 2T, ...
    data[1] / data1: spectral lines at FFT bins T/2, 3T/2, 5T/2, ...

With --swap-combs:

    data[0] / data0: spectral lines at FFT bins T/2, 3T/2, 5T/2, ...
    data[1] / data1: spectral lines at FFT bins 0, T, 2T, ...

For the default T=16, this gives tones every 8 FFT channels, alternating
between the two waveforms.
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
        raise ValueError(
            "No FFT bins selected. Check spacing, offset, fs, and fmax."
        )

    phases = rng.uniform(0, 2 * np.pi, size=bins.size)

    # Equal-magnitude positive-frequency lines.
    spec[bins] = np.exp(1j * phases)

    # Hermitian symmetry gives a real-valued time-domain waveform.
    spec[-bins] = np.conj(spec[bins])

    d = np.fft.ifft(spec).real

    return d, bins


def quantize_waveform_shared(d, nbits=14, scale=0.9):
    """Quantize an already normalized waveform without additional rescaling."""
    if nbits < 1 or nbits > 16:
        raise ValueError("nbits must be between 1 and 16 for int16 output.")

    if scale < 0:
        raise ValueError("scale must be non-negative.")

    max_int = 2 ** (nbits - 1) - 1
    q = np.round(scale * max_int * d)

    # Explicit clipping protects against scale > 1 or roundoff.
    q = np.clip(q, -32768, 32767)

    return q.astype(np.int16)


def print_waveform_diagnostics(name, d_int, bins):
    """Print time-domain and selected-bin FFT diagnostics."""
    d_float = d_int.astype(float)
    D = np.fft.fft(d_float)
    tone_mags = np.abs(D[bins])

    print(f"{name} time peak        = {np.max(np.abs(d_int))}")
    print(f"{name} time rms         = {np.sqrt(np.mean(d_float**2)):.3f}")
    print(f"{name} selected tones   = {len(bins)}")
    print(f"{name} first bins       = {bins[:8]}")
    print(f"{name} median |FFT bin| = {np.median(tone_mags):.3f}")
    print(f"{name} min |FFT bin|    = {np.min(tone_mags):.3f}")
    print(f"{name} max |FFT bin|    = {np.max(tone_mags):.3f}")


def main():
    p = ArgumentParser(description=__doc__)

    p.add_argument(
        "--seed0", type=int, default=816343, help="RNG seed for waveform 0"
    )
    p.add_argument(
        "--seed1", type=int, default=816344, help="RNG seed for waveform 1"
    )
    p.add_argument(
        "--N", type=int, default=256, help="Base samples per period"
    )
    p.add_argument(
        "--T", type=int, default=16, help="Comb spacing in FFT channels"
    )

    p.add_argument(
        "--nbits",
        type=int,
        default=14,
        help="Default quantization bits for both outputs",
    )
    p.add_argument(
        "--scale",
        type=float,
        default=0.9,
        help="Default amplitude scale for both outputs",
    )

    p.add_argument(
        "--nbits0",
        type=int,
        default=None,
        help="Quantization bits for waveform 0; defaults to --nbits",
    )
    p.add_argument(
        "--nbits1",
        type=int,
        default=None,
        help="Quantization bits for waveform 1; defaults to --nbits",
    )
    p.add_argument(
        "--scale0",
        type=float,
        default=None,
        help="Amplitude scale for waveform 0; defaults to --scale",
    )
    p.add_argument(
        "--scale1",
        type=float,
        default=None,
        help="Amplitude scale for waveform 1; defaults to --scale",
    )

    p.add_argument(
        "--fs", type=float, default=1000e6, help="Sample rate in Hz"
    )
    p.add_argument(
        "--fmax",
        type=float,
        default=250e6,
        help="Maximum positive frequency in Hz",
    )
    p.add_argument(
        "--include-dc",
        action="store_true",
        help="Include DC bin in whichever waveform has offset 0",
    )

    p.add_argument(
        "--swap-combs",
        action="store_true",
        help="Swap comb assignment between waveform 0 and waveform 1",
    )

    p.add_argument(
        "--out",
        type=str,
        default="waveforms/transmitter_interleaved_swappable.npz",
        help="Output npz path",
    )
    p.add_argument(
        "--plot", action="store_true", help="Show time-domain and FFT plots"
    )

    args = p.parse_args()

    nbits0 = args.nbits if args.nbits0 is None else args.nbits0
    nbits1 = args.nbits if args.nbits1 is None else args.nbits1
    scale0 = args.scale if args.scale0 is None else args.scale0
    scale1 = args.scale if args.scale1 is None else args.scale1

    if args.T % 2 != 0:
        raise ValueError(
            "T must be even. For every-8-channel interleaving, use T=16."
        )

    nsamp = args.N * args.T

    # Default:
    #   waveform 0 gets offset 0
    #   waveform 1 gets offset T/2
    #
    # With --swap-combs:
    #   waveform 0 gets offset T/2
    #   waveform 1 gets offset 0
    if args.swap_combs:
        offset0 = args.T // 2
        offset1 = 0
    else:
        offset0 = 0
        offset1 = args.T // 2

    # Only the offset-0 waveform can include DC.
    include_dc0 = args.include_dc if offset0 == 0 else False
    include_dc1 = args.include_dc if offset1 == 0 else False

    d0, bins0 = gen_comb_waveform(
        nsamp=nsamp,
        spacing=args.T,
        offset=offset0,
        seed=args.seed0,
        fs=args.fs,
        fmax=args.fmax,
        include_dc=include_dc0,
    )

    d1, bins1 = gen_comb_waveform(
        nsamp=nsamp,
        spacing=args.T,
        offset=offset1,
        seed=args.seed1,
        fs=args.fs,
        fmax=args.fmax,
        include_dc=include_dc1,
    )

    # Normalize both waveforms with one shared scale factor.
    common_peak = max(np.max(np.abs(d0)), np.max(np.abs(d1)))

    if common_peak == 0:
        raise ValueError(
            "Generated empty waveform. Check spacing, offset, fs, and fmax."
        )

    d0 = d0 / common_peak
    d1 = d1 / common_peak

    d0_int = quantize_waveform_shared(d0, nbits=nbits0, scale=scale0)
    d1_int = quantize_waveform_shared(d1, nbits=nbits1, scale=scale1)

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
        nbits0=np.array(nbits0),
        nbits1=np.array(nbits1),
        scale0=np.array(scale0),
        scale1=np.array(scale1),
        offset0=np.array(offset0),
        offset1=np.array(offset1),
        swap_combs=np.array(args.swap_combs),
        common_peak=np.array(common_peak),
    )

    print(f"wrote {args.out}")
    print(f"waveforms={data.shape[0]}")
    print(f"samples_per_waveform={data.shape[1]}")
    print(f"max_addr={max_addr}")
    print(f"df={args.fs / nsamp / 1e6:.6f} MHz")
    print(
        f"comb spacing={args.T} bins = {args.T * args.fs / nsamp / 1e6:.6f} MHz"
    )
    print(
        f"interleaved spacing={args.T // 2} bins = {(args.T // 2) * args.fs / nsamp / 1e6:.6f} MHz"
    )
    print(f"swap_combs={args.swap_combs}")
    print(f"waveform 0 offset={offset0}")
    print(f"waveform 1 offset={offset1}")
    print(f"waveform 0 nbits={nbits0}, scale={scale0}")
    print(f"waveform 1 nbits={nbits1}, scale={scale1}")

    print_waveform_diagnostics("waveform 0", d0_int, bins0)
    print_waveform_diagnostics("waveform 1", d1_int, bins1)

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
