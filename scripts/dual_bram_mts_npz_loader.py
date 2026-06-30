#!/home/eigsep/miniconda3/envs/py310/bin/python

import sys
import os
import time
import struct
import argparse
import numpy as np

sys.path.insert(0, "/home/eigsep/eigsep/rfsoc_2026/casperfpga")

import casperfpga


FIXED_LEN = 34


def print_line(name, value):
    print("%s: %s" % (name.ljust(FIXED_LEN), value), flush=True)


def to_bytes_int16_be(data):
    data = np.asarray(data)
    data = np.clip(np.round(data), -32768, 32767).astype(np.int16)
    return struct.pack(">%dh" % len(data), *data)


def compute_max_addr(nsamp):
    bytes_per_axis = 8
    bytes_per_sample = 2
    return int(nsamp * bytes_per_sample / bytes_per_axis - 3)


def generate_sine(freq_mhz, fs_mhz, nsamp, scale=8192, phase=0.0):
    bin_num = int(round(freq_mhz / fs_mhz * nsamp))
    actual_freq_mhz = bin_num * fs_mhz / nsamp

    n = np.arange(nsamp)
    data = scale * np.sin(2 * np.pi * actual_freq_mhz / fs_mhz * n + phase)

    return data, actual_freq_mhz, bin_num


def make_sine_pair(name, freq0, freq1, args):
    data0, actual0, bin0 = generate_sine(
        freq_mhz=freq0,
        fs_mhz=args.dac_fs,
        nsamp=args.dac_len,
        scale=args.scale0,
        phase=args.phase0,
    )

    data1, actual1, bin1 = generate_sine(
        freq_mhz=freq1,
        fs_mhz=args.dac_fs,
        nsamp=args.dac_len,
        scale=args.scale1,
        phase=args.phase1,
    )

    return {
        "name": name,
        "source": "generated sine",
        "freq0": freq0,
        "freq1": freq1,
        "actual0": actual0,
        "actual1": actual1,
        "bin0": bin0,
        "bin1": bin1,
        "data0": data0,
        "data1": data1,
        "buf0": to_bytes_int16_be(data0),
        "buf1": to_bytes_int16_be(data1),
        "peak0": np.max(np.abs(data0)),
        "peak1": np.max(np.abs(data1)),
        "max_addr": compute_max_addr(len(data0)),
    }


def load_npz_pair(npz_path):
    print("*******************************************", flush=True)
    print("Loading waveform pair from npz...", flush=True)
    print_line("NPZ file", npz_path)

    f = np.load(npz_path)

    if "data0" in f and "data1" in f:
        data0 = np.asarray(f["data0"]).squeeze()
        data1 = np.asarray(f["data1"]).squeeze()

    elif "data" in f:
        data = np.asarray(f["data"])

        if data.ndim == 1:
            raise ValueError(
                "NPZ key 'data' is 1D. For two DACs, use data0/data1 or data shape (2, N)/(N, 2)."
            )

        if data.ndim != 2:
            raise ValueError("NPZ key 'data' must be 2D for two-channel loading.")

        if data.shape[0] == 2:
            data0 = data[0, :]
            data1 = data[1, :]
        elif data.shape[1] == 2:
            data0 = data[:, 0]
            data1 = data[:, 1]
        else:
            raise ValueError(
                "NPZ key 'data' must have shape (2, N) or (N, 2). Got %s." % (data.shape,)
            )

    else:
        raise ValueError("NPZ must contain either data0/data1 or data.")

    data0 = np.asarray(data0).real
    data1 = np.asarray(data1).real

    if len(data0) != len(data1):
        raise ValueError("data0 and data1 must have same length.")

    if "max_addr" in f:
        max_addr = int(np.asarray(f["max_addr"]).item())
    else:
        max_addr = compute_max_addr(len(data0))

    return {
        "name": "NPZ",
        "source": npz_path,
        "freq0": None,
        "freq1": None,
        "actual0": None,
        "actual1": None,
        "bin0": None,
        "bin1": None,
        "data0": data0,
        "data1": data1,
        "buf0": to_bytes_int16_be(data0),
        "buf1": to_bytes_int16_be(data1),
        "peak0": np.max(np.abs(data0)),
        "peak1": np.max(np.abs(data1)),
        "max_addr": max_addr,
    }


def pulse_reset(rfsoc, rst_reg="rst", delay=0.01):
    rfsoc.write_int(rst_reg, 1)
    time.sleep(delay)
    rfsoc.write_int(rst_reg, 0)
    time.sleep(delay)


def read_select(rfsoc, select_reg="wave_form", samples=5, delay=0.01):
    vals = []
    for _ in range(samples):
        vals.append(rfsoc.read_uint(select_reg) & 0x1)
        time.sleep(delay)
    return 1 if sum(vals) > len(vals) // 2 else 0


def get_dac_mts_latencies(rfdc):
    lat0 = rfdc.get_mts_latency("dac", 0)
    lat1 = rfdc.get_mts_latency("dac", 1)

    print_line("DAC tile 0 latency", lat0)
    print_line("DAC tile 1 latency", lat1)

    return lat0, lat1


def mts_latencies_are_clean(lat0, lat1):
    lat0_val = int(lat0["Latency"])
    lat1_val = int(lat1["Latency"])
    off0_val = int(lat0["DelayOffset"])
    off1_val = int(lat1["DelayOffset"])

    return lat0_val == lat1_val and off0_val == 0 and off1_val == 0


def configure_once(args, attempt):
    print("*******************************************", flush=True)
    print("FPGA/RFDC configuration attempt %d" % attempt, flush=True)
    print("*******************************************", flush=True)

    print_line("Connecting to", args.ip)
    rfsoc = casperfpga.CasperFpga(
        args.ip,
        transport=casperfpga.KatcpTransport,
    )

    print_line("Programming FPGA", args.fpg)
    rfsoc.upload_to_ram_and_program(args.fpg)

    rfdc = rfsoc.adcs["rfdc"]

    print("*******************************************", flush=True)
    print("Initializing RFDC and programming PLLs...", flush=True)

    ok = rfdc.init()
    print_line("RFDC init", ok)

    clk_files = rfdc.show_clk_files()
    for i, fname in enumerate(clk_files):
        print("[%d] %s" % (i, fname), flush=True)

    print_line("LMK file", clk_files[args.lmk_index])
    print_line("LMX file", clk_files[args.lmx_index])

    ok_lmk = rfdc.progpll("lmk", clk_files[args.lmk_index])
    ok_lmx = rfdc.progpll("lmx", clk_files[args.lmx_index])

    print_line("LMK programming", ok_lmk)
    print_line("LMX programming", ok_lmx)

    time.sleep(args.clock_settle_sec)

    print("*******************************************", flush=True)
    print("Running DAC MTS...", flush=True)

    mts_ok = rfdc.run_mts(
        "dac",
        args.dac_mts_mask,
        args.dac_mts_target_latency,
    )

    print_line("DAC MTS result", mts_ok)

    if not mts_ok:
        raise RuntimeError("DAC MTS returned False")

    print("*******************************************", flush=True)
    print("DAC MTS debug info...", flush=True)
    rfdc.mts_debug_info("dac")

    print("*******************************************", flush=True)
    print("DAC MTS latency check...", flush=True)
    lat0, lat1 = get_dac_mts_latencies(rfdc)

    if not mts_latencies_are_clean(lat0, lat1):
        raise RuntimeError(
            "DAC MTS not clean: tile0=%s tile1=%s"
            % (lat0, lat1)
        )

    print_line("DAC MTS latency check", "passed")
    time.sleep(0.5)

    return rfsoc


def configure_with_reloads(args):
    last_error = None

    for attempt in range(1, args.max_fpga_reloads + 1):
        try:
            return configure_once(args, attempt)
        except Exception as e:
            last_error = e
            print("*******************************************", flush=True)
            print("Configuration attempt %d failed:" % attempt, flush=True)
            print(e, flush=True)

            if attempt < args.max_fpga_reloads:
                print("Reloading FPGA and trying again...", flush=True)
                time.sleep(args.reload_delay_sec)

    raise RuntimeError(
        "Failed to get clean DAC MTS after %d FPGA reloads. Last error: %s"
        % (args.max_fpga_reloads, last_error)
    )


def print_pair_info(pair):
    print_line("Pair", pair["name"])
    print_line("Source", pair["source"])
    print_line("Samples", len(pair["data0"]))
    print_line("Shared max addr", pair["max_addr"])
    print_line("DAC0 peak", pair["peak0"])
    print_line("DAC1 peak", pair["peak1"])

    if pair["freq0"] is not None:
        print_line("DAC0 requested MHz", pair["freq0"])
        print_line("DAC0 actual MHz", pair["actual0"])
        print_line("DAC0 bin", pair["bin0"])
        print_line("DAC1 requested MHz", pair["freq1"])
        print_line("DAC1 actual MHz", pair["actual1"])
        print_line("DAC1 bin", pair["bin1"])


def load_pair(rfsoc, pair, args):
    print("*******************************************", flush=True)
    print("Loading waveform pair %s..." % pair["name"], flush=True)
    print_pair_info(pair)

    rfsoc.write_int(args.wf_en_reg, 0)
    time.sleep(args.ctrl_delay)

    pulse_reset(rfsoc, args.rst_reg, delay=args.ctrl_delay)

    rfsoc.write(args.bram0, pair["buf0"])
    rfsoc.write(args.bram1, pair["buf1"])

    rfsoc.write_int(args.addr_max_reg, pair["max_addr"])

    pulse_reset(rfsoc, args.rst_reg, delay=args.ctrl_delay)

    rfsoc.write_int(args.wf_en_reg, 1)
    time.sleep(args.ctrl_delay)

    print("Loaded pair %s and enabled playback." % pair["name"], flush=True)

    try:
        print_line(args.wf_en_reg, rfsoc.read_uint(args.wf_en_reg))
        print_line(args.addr_max_reg, rfsoc.read_uint(args.addr_max_reg))
    except Exception as e:
        print("Readback warning: %s" % e, flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="RFSoC2x2 dual-BRAM sine/NPZ loader with clean DAC MTS reload loop."
    )

    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--fpg", required=True)

    parser.add_argument("--npz", default=None,
                        help="Optional NPZ waveform file. Use data0/data1 or data shape (2,N)/(N,2).")

    parser.add_argument("--dac-fs", type=float, default=1000.0)
    parser.add_argument("--dac-len", type=int, default=32768)

    parser.add_argument("--a-freq0", type=float, default=100.0)
    parser.add_argument("--a-freq1", type=float, default=150.0)
    parser.add_argument("--b-freq0", type=float, default=200.0)
    parser.add_argument("--b-freq1", type=float, default=250.0)

    parser.add_argument("--scale0", type=float, default=8192)
    parser.add_argument("--scale1", type=float, default=8192)
    parser.add_argument("--phase0", type=float, default=0.0)
    parser.add_argument("--phase1", type=float, default=0.0)

    parser.add_argument("--bram0", default="wf_bram_0")
    parser.add_argument("--bram1", default="wf_bram_1")
    parser.add_argument("--addr-max-reg", default="addr_max")
    parser.add_argument("--wf-en-reg", default="wf_en")
    parser.add_argument("--rst-reg", default="rst")
    parser.add_argument("--select-reg", default="wave_form")

    parser.add_argument("--lmk-index", type=int, default=1)
    parser.add_argument("--lmx-index", type=int, default=3)

    parser.add_argument("--dac-mts-mask", type=lambda x: int(x, 0), default=0x3)
    parser.add_argument("--dac-mts-target-latency", type=int, default=-1)
    parser.add_argument("--max-fpga-reloads", type=int, default=5)

    parser.add_argument("--clock-settle-sec", type=float, default=2.0)
    parser.add_argument("--reload-delay-sec", type=float, default=1.0)
    parser.add_argument("--poll-sec", type=float, default=0.25)
    parser.add_argument("--ctrl-delay", type=float, default=0.01)

    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force-state", choices=["0", "1", "none"], default="none")

    args = parser.parse_args()

    print("*******************************************", flush=True)
    print("RFSoC2x2 dual-BRAM sine/NPZ MTS loader", flush=True)
    print_line("casperfpga", casperfpga.__file__)
    print_line("FPG", args.fpg)

    rfsoc = configure_with_reloads(args)

    if args.npz is not None:
        pair_npz = load_npz_pair(args.npz)
        pair_a = pair_npz
        pair_b = pair_npz
        print("*******************************************", flush=True)
        print("NPZ mode: both select states load the same NPZ pair.", flush=True)
    else:
        pair_a = make_sine_pair(
            name="A",
            freq0=args.a_freq0,
            freq1=args.a_freq1,
            args=args,
        )

        pair_b = make_sine_pair(
            name="B",
            freq0=args.b_freq0,
            freq1=args.b_freq1,
            args=args,
        )

    print("*******************************************", flush=True)
    print("Expected FPGA structure:", flush=True)
    print("  shared address counter -> wf_bram_0 address", flush=True)
    print("                         -> wf_bram_1 address", flush=True)
    print("  wf_bram_0 -> DAC0 path", flush=True)
    print("  wf_bram_1 -> DAC1 path", flush=True)

    last_state = None

    while True:
        if args.force_state != "none":
            state = int(args.force_state)
        else:
            try:
                state = read_select(rfsoc, args.select_reg)
            except Exception as e:
                print("Error reading %s: %s" % (args.select_reg, e), flush=True)
                time.sleep(args.poll_sec)
                continue

        if state != last_state:
            print("*******************************************", flush=True)
            print("Detected %s = %d" % (args.select_reg, state), flush=True)

            if state == 1:
                load_pair(rfsoc, pair_a, args)
            else:
                load_pair(rfsoc, pair_b, args)

            last_state = state

            if args.once:
                print("Loaded once; exiting.", flush=True)
                break

        time.sleep(args.poll_sec)


if __name__ == "__main__":
    try:
        main()
    finally:
        os._exit(0)
