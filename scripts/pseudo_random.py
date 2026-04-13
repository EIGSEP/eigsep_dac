import numpy as np
import casperfpga 
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

parser = ArgumentParser(description = 'Red Pitaya Configure', formatter_class = ArgumentDefaultsHelpFormatter)

parser.add_argument('-f', dest = 'file_number_', type = str, default = 'd_int.npy', help = 'File destination of data to load into RP')

parser.add_argument('-i', dest = 'ip_number_', type = str, default = '10.10.10.11', help = 'IP of RP')

parser.add_argument('-b', dest = 'bitstream_number_', type = str, default = 'pseudo_random_test.fpg', help = 'fpg file to upload to RP')

parser.add_argument('-a', dest = 'amp_number_', type = int, default = '1', help = 'Number to multiply the data to change the amplitude, max of 4')

dest_data = '/home/dominiv/simulink/dac/notebooks/'
dest_bit = '/home/dominiv/simulink/dac/bitstream/'

args = parser.parse_args()
file_number = dest_data + args.file_number_
IP = args.ip_number_
bitstream = dest_bit + args.bitstream_number_
amp = args.amp_number_

rp = casperfpga.CasperFpga(IP)
rp.upload_to_ram_and_program(bitstream)
print(f'FPGA IP: {IP}')
print(f'FPGA Bitstream: {bitstream}')

rp.registers.reg_cntrl.write(rst_cntrl = 'pulse')

npz = np.load(str(file_number))
sequence = npz["data"]
data_array = sequence.astype('>i4')
data_bytes = data_array.tobytes()

rp.write_int('amp_reg', int(amp))

rp.write('shared_bram1', data_bytes)

print('waveform sent')
