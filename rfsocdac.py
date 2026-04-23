"""Shim kept so the RFSoC's boot invocation (`python rfsocdac.py ...`) keeps working.

Real implementation lives in `eigsep_dac.program_board`. Once the board's boot
unit is updated to invoke `scripts/program_rfsoc.py`, this file can be removed.
"""

from eigsep_dac.program_board import main

if __name__ == "__main__":
    main()
