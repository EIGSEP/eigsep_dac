"""
gen_comb_waveforms.py
---------------------
Generate a pair of pseudorandom waveforms whose power spectra form a Dirac comb
every 16th spectrometer channel, with 90° mutual phase offset for circular
polarization injection.

Spectrometer assumptions
------------------------
  Real-input FFT spectrometer
  Channels  : 1024  (0 – 250 MHz)
  Sample rate: 500 MHz  (Nyquist for 0–250 MHz)
  FFT length : 2 × 1024 = 2048 points  →  1024 unique positive-freq bins

One DAC waveform period = 2048 samples = 4.096 µs at 500 MHz.
The waveform is designed to be output as a repeating loop.

Comb construction
-----------------
  Tone positions : bins  16, 32, 48, …, 1008  (every 16th, DC excluded)
  Amplitudes     : uniform (all 1 before normalisation)
  Phases (pol 1) : pseudorandom, drawn from U[0, 2π)  with a fixed seed

Quadrature polarisation
-----------------------
  Pol 2 = discrete Hilbert transform of Pol 1.
  Implemented in the frequency domain:
      X2[k] = -j · X1[k]   for k = 1 … N/2-1  (positive frequencies)
      X2[k] = +j · X1[k]   for k = N/2+1 … N-1 (negative frequencies)
      X2[0] = X2[N/2] = 0  (DC and Nyquist remain zero)
  Each tone gains exactly -90°, so pol1 ∝ cos(ωt+φ) and pol2 ∝ sin(ωt+φ),
  forming a right-hand circularly polarised signal when fed to orthogonal feeds.

Output
------
  comb_waveforms.npz  –  keys:
      pol1         float64 waveform, length N_FFT, range [-1, +1]
      pol2         float64 waveform, length N_FFT, range [-1, +1]
      pol1_i16     int16   version (DAC-ready, FS = 32767)
      pol2_i16     int16   version (DAC-ready, FS = 32767)
      metadata     dict    (stored as object array for npz compatibility)
      fs           sample rate in Hz
      comb_bins    1-D array of active bin indices
"""

import numpy as np


# ── Parameters ────────────────────────────────────────────────────────────────

N_CHANNELS   = 1024          # spectrometer channels  (0 – 250 MHz)
N_FFT        = 2 * N_CHANNELS  # real-input FFT length  (2048 samples / period)
COMB_SPACING = 16            # Dirac comb tooth spacing [channels]
FS           = 500e6         # DAC sample rate [Hz]
SEED         = 42            # RNG seed for reproducibility


# ── Build comb spectrum ────────────────────────────────────────────────────────

rng = np.random.default_rng(seed=SEED)

# Active bins: 16, 32, …, 1008  (skip DC so Hilbert transform is exact)
comb_bins = np.arange(COMB_SPACING, N_CHANNELS, COMB_SPACING, dtype=int)
n_tones   = len(comb_bins)
print(f"Comb tones : {n_tones}  (bins {comb_bins[0]} – {comb_bins[-1]})")
print(f"Tone freqs : {comb_bins[0]*FS/N_FFT/1e6:.3f} – "
      f"{comb_bins[-1]*FS/N_FFT/1e6:.3f} MHz  "
      f"(spacing {COMB_SPACING*FS/N_FFT/1e6:.3f} MHz)")

# Random phases for pol 1
phases = rng.uniform(0.0, 2 * np.pi, n_tones)

# Hermitian-symmetric spectrum → real IFFT output
X1 = np.zeros(N_FFT, dtype=complex)
for k, phi in zip(comb_bins, phases):
    X1[k]          =  np.exp( 1j * phi)   # positive frequency
    X1[N_FFT - k]  =  np.exp(-1j * phi)   # conjugate mirror (negative freq)

# DC (bin 0) and Nyquist (bin N_CHANNELS) remain zero.


# ── Pol 1: IFFT ───────────────────────────────────────────────────────────────

pol1_raw = np.fft.ifft(X1).real   # imaginary residual is numerical noise only


# ── Pol 2: 90° phase shift via discrete Hilbert transform ─────────────────────
#
#  H{x}[n] = IFFT( -j·sign(k) · X[k] )
#
#  Positive-frequency bins (1 … N/2-1)  → multiply by -j   (shift by -90°)
#  Negative-frequency bins (N/2+1 … N-1) → multiply by +j  (shift by +90°)
#  DC (k=0) and Nyquist (k=N/2) → already 0, no action needed.

X2 = X1.copy()
X2[1          : N_CHANNELS]  *= -1j   # positive freqs (bins 1 … 1023)
X2[N_CHANNELS + 1 :]         *=  1j   # negative freqs (bins 1025 … 2047)
# bin N_CHANNELS (1024, Nyquist) is zero; no special handling required.

pol2_raw = np.fft.ifft(X2).real


# ── Normalise to ±1 ───────────────────────────────────────────────────────────
#
#  Peak normalise jointly so both pols share the same full-scale definition.
#  (Individual peaks differ by up to ~10 % due to random-phase statistics;
#   joint normalisation keeps them at the same power level.)

peak = max(np.max(np.abs(pol1_raw)), np.max(np.abs(pol2_raw)))
pol1 = pol1_raw / peak
pol2 = pol2_raw / peak

print(f"\nPol 1  peak = {np.max(np.abs(pol1)):.6f}  "
      f"rms = {np.sqrt(np.mean(pol1**2)):.6f}")
print(f"Pol 2  peak = {np.max(np.abs(pol2)):.6f}  "
      f"rms = {np.sqrt(np.mean(pol2**2)):.6f}")


# ── 16-bit integer versions (DAC-ready) ───────────────────────────────────────

INT16_FS = 32767
pol1_i16 = np.round(pol1 * INT16_FS).astype(np.int16)
pol2_i16 = np.round(pol2 * INT16_FS).astype(np.int16)


# ── Save ──────────────────────────────────────────────────────────────────────

out_path = "comb_waveforms.npz"
np.savez(
    out_path,
    pol1       = pol1,
    pol2       = pol2,
    pol1_i16   = pol1_i16,
    pol2_i16   = pol2_i16,
    comb_bins  = comb_bins,
    fs         = np.float64(FS),
)
print(f"\nSaved → {out_path}")
print(f"  Waveform length : {N_FFT} samples")
print(f"  Period          : {N_FFT / FS * 1e6:.4f} µs  at {FS/1e6:.0f} MHz sample rate")


# ── Verification ──────────────────────────────────────────────────────────────

def verify_comb(label, waveform, bins, n_fft, tol_db=40.0):
    """
    Check that all comb bins are present and no off-comb leakage exceeds
    (peak_comb - tol_db) dB.
    """
    X   = np.fft.rfft(waveform)
    pwr = np.abs(X)**2

    on_peak  = np.min(pwr[bins])
    off_mask = np.ones(len(pwr), dtype=bool)
    off_mask[bins] = False
    off_mask[0]    = False   # ignore DC
    off_peak = np.max(pwr[off_mask])

    isolation_db = 10 * np.log10(on_peak / off_peak) if off_peak > 0 else np.inf
    status = "PASS" if isolation_db >= tol_db else "FAIL"
    print(f"  [{status}] {label}  isolation = {isolation_db:.1f} dB  "
          f"(threshold {tol_db} dB)")
    return isolation_db


print("\nVerification (rfft of float waveforms):")
verify_comb("pol1", pol1, comb_bins, N_FFT)
verify_comb("pol2", pol2, comb_bins, N_FFT)


# Phase-offset check: each comb tooth in pol2 should lag pol1 by 90°.
X1v = np.fft.rfft(pol1)
X2v = np.fft.rfft(pol2)
phase_diffs = np.angle(X2v[comb_bins]) - np.angle(X1v[comb_bins])
phase_diffs = (np.degrees(phase_diffs) + 180) % 360 - 180   # wrap to ±180°
print(f"\nPhase offset pol2 − pol1 at comb tones:")
print(f"  mean  = {np.mean(phase_diffs):+.4f}°  (expect −90.0°)")
print(f"  std   = {np.std(phase_diffs):.2e}°  (expect ~0)")


# ── Optional: quick diagnostic plot ───────────────────────────────────────────
#
#  Uncomment the block below to display a matplotlib figure showing the
#  power spectrum of both polarisations.

# import matplotlib.pyplot as plt
#
# freqs  = np.fft.rfftfreq(N_FFT, d=1/FS) / 1e6   # MHz
# pwr1   = 20 * np.log10(np.abs(np.fft.rfft(pol1)) + 1e-12)
# pwr2   = 20 * np.log10(np.abs(np.fft.rfft(pol2)) + 1e-12)
#
# fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True, sharey=True)
# for ax, pwr, label, color in zip(
#         axes, [pwr1, pwr2], ["Pol 1 (0°)", "Pol 2 (−90°)"], ["C0", "C1"]):
#     ax.plot(freqs, pwr, lw=0.6, color=color)
#     ax.axhline(np.max(pwr[comb_bins[comb_bins < len(freqs)]]) - 3,
#                ls="--", lw=0.5, color="gray")
#     ax.set_ylabel("Power [dBFS]")
#     ax.set_title(label)
#     ax.grid(True, lw=0.3)
# axes[-1].set_xlabel("Frequency [MHz]")
# plt.tight_layout()
# plt.savefig("comb_spectrum.png", dpi=150)
# plt.show()
