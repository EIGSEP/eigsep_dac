"""Pseudorandom waveform helpers lifted verbatim from notebooks/psuedo_random.ipynb.

The `np.random.seed(seed)` call uses legacy global RNG on purpose — switching to
`np.random.default_rng` would invalidate the hand-picked seed 816343 that
reproduces the golden transmitter.npz.
"""

import numpy as np


def gen_flat_spectrum_waveform(N=64, band_fraction=2, seed=0):
    """Return a waveform with hermitian spectrum, random phases, unity amplitude."""
    M = (N // (2 * band_fraction)) - 1
    d_tilda = np.zeros(N) + 1j * np.zeros(N)
    np.random.seed(seed)
    dM_tilda = np.exp(1j * np.random.uniform(0, 2 * np.pi, size=M))
    conj_dM = np.conjugate(dM_tilda)[::-1]
    d_tilda[1:M + 1] = dM_tilda
    d_tilda[-M:] = conj_dM
    d = np.fft.ifft(d_tilda)
    return d.real


def round_waveform(d, nbits=14, scale=1.0):
    d_scale = scale * d.real / np.max(np.abs(d.real)) * (2 ** (nbits - 1) - 1)
    d_int = np.round(d_scale)
    return d_int.astype(int)


def tile_waveform(d, T=16):
    return np.tile(d, T)


def max_addr_calc(N=64, T=16):
    return int((N * T / 4) - 3)
