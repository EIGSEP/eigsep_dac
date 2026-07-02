"""Generate two equal-amplitude quadrature comb waveforms for RFSoC DAC loading.

The output npz contains two real-valued integer DAC waveforms:

    data[0]: comb waveform
    data[1]: same comb, shifted by +/- 90 degrees at every positive-frequency tone

This is suitable for driving two orthogonal antenna feeds for circular polarization,
assuming the analog chains and antenna feeds are amplitude/phase matched.
"""

from argparse import ArgumentParser

import numpy as np

from eigsep_dac.waveform import max_addr_calc


def gen_quadrature_comb_waveforms(
    nsamp,
    spacing,
    seed,
    fs=1000e6,
    fmax=250e6,
    include_dc=False,
    phase_sign=1,
):
    """Generate two real-valued comb waveforms in quadrature.

    phase_sign = +1 gives waveform 1 = +90 degrees on positive-frequency tones.
    phase_sign = -1 gives waveform 1 = -90 degrees on positive-frequency tones.

    DC is excluded by default because a DC component cannot be phase-shifted by 90 degrees
    in the usual sinusoidal sense.
    """
    if phase_sign not in (+1, -1):
        raise ValueError("phase_sign must be +1 or -1.")

    rng = np.random.default_rng(seed)

    spec0 = np.zeros(nsamp, dtype=np.complex128)
    spec1 = np.zeros(nsamp, dtype=np.complex128)

    df = fs / nsamp
    kmax = int(np.floor(fmax / df))

    bins = np.arange(0, kmax + 1, spacing, dtype=int)

    if not include_dc:
        bins = bins[bins != 0]

    # Avoid Nyquist bin. For real waveforms it needs special handling.
    nyquist = nsamp // 2
    bins = bins[bins < nyquist]

    if bins.size == 0:
        raise ValueError("No FFT bins selected. Check spacing, fs, and fmax.")

    phases = rng.uniform(0, 2 * np.pi, size=bins.size)

    # Equal-magnitude positive-frequency comb for waveform 0.
    spec0[bins] = np.exp(1j * phases)

    # Same bins, same amplitudes, shifted by +/- 90 degrees.
    spec1[bins] = spec0[bins] * np.exp(phase_sign * 1j * np.pi / 2)

    # Hermitian symmetry gives real-valued time-domain waveforms.
    spec0[-bins] = np.conj(spec0[bins])
    spec1[-bins] = np.conj(spec1[bins])

    d0 = np.fft.ifft(spec0).real
    d1 = np.fft.ifft(spec1).real

    return d0, d1, bins


def quantize_waveform_shared(d, nbits=14, scale=0.9):
    """Quantize an already normalized waveform without additional rescaling."""
    max_int = 2 ** (nbits - 1) - 1
    return np.round(scale * max_int * d).astype(np.int16)


def main():
    p = ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=816343, help="RNG seed")
    p.add_argument(
        "--N", type=int, default=256, help="Base samples per period"
    )
    p.add_argument(
        "--T", type=int, default=16, help="Comb spacing in FFT channels"
    )
    p.add_argument("--nbits", type=int, default=14, help="Quantization bits")
    p.add_argument(
        "--scale",
        type=float,
        default=0.9,
        help="Amplitude scale after shared normalization",
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
        help="Include DC bin in waveform 0. Not recommended for quadrature.",
    )
    p.add_argument(
        "--phase-sign",
        type=int,
        choices=[-1, 1],
        default=1,
        help="+1 for +90 degrees, -1 for -90 degrees",
    )
    p.add_argument(
        "--out",
        type=str,
        default="waveforms/transmitter_quadrature.npz",
        help="Output npz path",
    )
    p.add_argument(
        "--plot",
        action="store_true",
        help="Show time-domain, FFT, and phase-difference plots",
    )
    args = p.parse_args()

    nsamp = args.N * args.T

    d0, d1, bins = gen_quadrature_comb_waveforms(
        nsamp=nsamp,
        spacing=args.T,
        seed=args.seed,
        fs=args.fs,
        fmax=args.fmax,
        include_dc=args.include_dc,
        phase_sign=args.phase_sign,
    )

    # Shared normalization preserves equal spectral amplitude between channels.
    common_peak = max(np.max(np.abs(d0)), np.max(np.abs(d1)))

    if common_peak == 0:
        raise ValueError(
            "Generated empty waveform. Check spacing, fs, and fmax."
        )

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
        bins=bins,
        fs=np.array(args.fs),
        N=np.array(args.N),
        T=np.array(args.T),
        phase_shift_degrees=np.array(90 * args.phase_sign),
    )

    print(f"wrote {args.out}")
    print(f"waveforms={data.shape[0]}")
    print(f"samples_per_waveform={data.shape[1]}")
    print(f"max_addr={max_addr}")
    print(f"df={args.fs / nsamp / 1e6:.6f} MHz")
    print(
        f"comb spacing={args.T} bins = {args.T * args.fs / nsamp / 1e6:.6f} MHz"
    )
    print(f"phase shift={90 * args.phase_sign:+d} degrees")
    print(f"first comb bins: {bins[:8]}")
    print(f"last comb bins: {bins[-8:]}")

    if args.plot:
        import matplotlib.pyplot as plt

        freqs = np.fft.fftfreq(nsamp, 1 / args.fs)

        fft0 = np.fft.fft(d0_int)
        fft1 = np.fft.fft(d1_int)

        mag0 = np.abs(fft0)
        mag1 = np.abs(fft1)

        phase_diff = np.angle(fft1[bins] / fft0[bins], deg=True)

        fig, axs = plt.subplots(5, 1, figsize=(10, 12))

        axs[0].plot(d0_int)
        axs[0].set_title("Waveform 0 time domain")

        axs[1].plot(d1_int)
        axs[1].set_title("Waveform 1 time domain")

        axs[2].plot(
            np.fft.fftshift(freqs) / 1e6,
            np.fft.fftshift(mag0),
            label="waveform 0",
        )
        axs[2].plot(
            np.fft.fftshift(freqs) / 1e6,
            np.fft.fftshift(mag1),
            label="waveform 1",
            alpha=0.7,
        )
        axs[2].set_xlim(0, args.fmax / 1e6)
        axs[2].set_xlabel("MHz")
        axs[2].set_ylabel("|FFT|")
        axs[2].set_title("Spectra")
        axs[2].legend()

        axs[3].plot(freqs[bins] / 1e6, mag1[bins] / mag0[bins], ".")
        axs[3].set_xlabel("MHz")
        axs[3].set_ylabel("|FFT1| / |FFT0|")
        axs[3].set_title("Comb amplitude ratio at occupied bins")

        axs[4].plot(freqs[bins] / 1e6, phase_diff, ".")
        axs[4].axhline(90 * args.phase_sign, linestyle="--")
        axs[4].set_xlabel("MHz")
        axs[4].set_ylabel("degrees")
        axs[4].set_title("Phase difference at occupied bins")

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
