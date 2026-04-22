import casperfpga
import matplotlib.pyplot as plt
import numpy as np
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import datetime
import time
import os




# Argument parsing
parser = ArgumentParser(description='Red Pitaya Settings', formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument('-i', dest='ip_number_', type=str, default='169.254.134.200', help='IP of RP')
parser.add_argument('-f', dest='freq_number_', type=float, default=1.5e3, help='Frequency')
parser.add_argument('-a', dest='ampl_number_', type=float, default=1000, help='Amplitude')
parser.add_argument('-b', dest='bitstream_number_', type=str, default='wave_sync_2024-08-19_1149.fpg', help='File Name')
parser.add_argument('-t', dest='time_number_', type=float, default=1, help='Time between max amplitude recording in seconds')
parser.add_argument('-l', dest='limit_number_', type=str, default='30', help='time to record in minutes')
parser.add_argument('-n', dest='file_number_', type=str, default='new', help='File name to save to')
parser.add_argument('--p1', action='store_true', help='Display live plot')
parser.add_argument('--s', action='store_true', help='save')
parser.add_argument('--p2', action='store_true', help='Display plot of first data set')
parser.add_argument('--p0', action='store_true', help='No plot, just record')
parser.add_argument('--pt', action='store_true', help='Test data plot')

args = parser.parse_args()
freq_number = args.freq_number_
ampl_number = args.ampl_number_
ip_number = args.ip_number_
bitstream_number = args.bitstream_number_
time_number = args.time_number_
limit_number = args.limit_number_
file_name = args.file_number_

# Set up FPGA connection and configuration
frequency = freq_number
amplitude = ampl_number
IP = ip_number
path = '/home/dominiv/simulink/dac/bitstream/'
save_path_home = '/home/dominiv/simulink/dac/adc_data/'

bitstream = bitstream_number
program = path + bitstream
sec = time_number
limit = int(limit_number)*60
save_path = file_name

def files(file_number):
    """
    Creates file directory
    
    Parameters:
    file_number (int): Number to name file in the directory
    
    """

    if os.path.exists(save_path_home+'counts'+file_number):
        print(save_path_home+'counts'+file_number)
        return

    os.makedirs(save_path_home + 'counts' + file_number)
    os.makedirs(save_path_home + 'adc1' + file_number)
    os.makedirs(save_path_home + 'adc2' + file_number)
    os.makedirs(save_path_home + 'max_amp1' + file_number)
    os.makedirs(save_path_home + 'ave' + file_number)
    os.makedirs(save_path_home + 'max_amp2' + file_number)



class Plotter:
    def __init__(self, frequency, amplitude, IP, program, test=False):
        if test == False:

            self.rp = casperfpga.CasperFpga(IP)
            self.rp.upload_to_ram_and_program(program)
            print(f'FPGA IP: {IP}')
            print(f'FPGA Bitstream: {bitstream}')
            # Arm the snapshot block
            print('arming snapshot block...')
            self.rp.snapshots.adc_in_snap_ss.arm()
            print('done')
            
            read_length = 1024
            
            # Configure FPGA registers
            self.rp.registers.reg_cntrl.write(rst_cntrl='pulse')
            self.rp.write_int('my_ampl_register', int(amplitude))
            self.rp.write_int('my_freq_register', int(frequency))
            print('Frequency and Amplitude Set')
            print(int(frequency), self.rp.read_int("my_freq_register"))
            print(int(amplitude), self.rp.read_int("my_ampl_register"))
            print('Measured clock speed:', self.rp.estimate_fpga_clock())

        self.fig, self.ax = None, None
        self.line1 = None
        self.line2 = None


        self.count_list = []
        self.adc1_list = []
        self.adc2_list = []
        self.max1_list = []
        self.max2_list = []
        self.ave_list = []
      


    
    def make_fig(self):
        plt.ion()
        self.fig, (self.ax1, self.ax2) = plt.subplots(2,1,figsize=(10, 6))
        self.line1 = self.ax1.plot([], [], 'black', label='input 1')
        self.ax1.set_title('signal to adc')
        self.ax1.set_xlabel('counts')
        self.ax1.set_ylabel('amplitude')
        self.ax1.legend()
    
        self.line2 = self.ax2.plot([], [], 'black', label='input 2')
        self.ax2.set_title('dac to adc')
        self.ax2.set_xlabel('counts')
        self.ax2.set_ylabel('amplitude')
        self.ax2.legend()
        print('starting live plot')


    def x_axis(self):
        self.a = 0
        self.b = 1024
        print(self.b)

    
    def data_capture(self):


        self.rp.snapshots.adc_in_snap_ss.arm()
        #self.rp.registers.reg_cntrl.write(rst_cntrl='pulse')
        self.rp.registers.trigger_cntrl.write(trig_cntrl='pulse')
        self.adc_in = self.rp.snapshots.adc_in_snap_ss.read(arm=False)['data']
        self.adc_in1 = np.array(self.adc_in['adc_data_ch1'])
        self.adc_in2 = np.array(self.adc_in['adc_data_ch2'])
        #self.ave = np.mean(self.adc_in1)
        #self.#x = np.linspace(0, len(adc_in))
        #self.x = np.linspace(self.a, self.b)
        #self.b = self.rp.registers.adc_sample_cnt.read_uint()
        #self.a = self.b - 1024
        
        #self.x = np.arange(len(self.adc_in1))
        self.x = np.linspace(self.a, self.b, 1024)
        #print(self.adc_in1)
        self.count_list.append(self.x)
        self.adc1_list.append(self.adc_in1)
        self.adc2_list.append(self.adc_in2)
        #self.ave_list.append(self.ave)
        self.a += self.x.size
        self.a += self.x.size
        self.b += self.x.size
        #print('mean', np.mean(self.adc_in1))


    def plot_live(self):
        self.line1[0].set_xdata(self.x)
        self.line1[0].set_ydata(self.adc_in1)
        self.ax1.relim()
        self.ax1.autoscale_view()
        self.line2[0].set_xdata(self.x)
        self.line2[0].set_ydata(self.adc_in2)
        self.ax2.relim()
        self.ax2.autoscale_view()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        #self.fig.canvas.draw()
        #self.fig.canvas.flush_events()
        plt.pause(.1)

    def plot_single(self):
        self.line1[0].set_xdata(self.x)
        self.line1[0].set_ydata(self.adc_in1)
        self.ax1.relim()
        self.ax1.autoscale_view()
        self.line2[0].set_xdata(self.x)
        self.line2[0].set_ydata(self.adc_in2)
        self.ax2.relim()
        self.ax2.autoscale_view()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(1000)

    def max_value(self):
        max_amp1 = np.max(self.adc_in1)
        max_amp2 = np.max(self.adc_in2)
        ave = np.mean(self.adc_in1)
        self.ave_list.append(ave)
        self.max1_list.append(max_amp1)
        self.max2_list.append(max_amp2)
        print('max adc1 amplitude:', max_amp1)
        print('max adc2 amplitude:', max_amp2)
        print('ave temp:', ave)
        
        print('ave shape:', np.array(self.ave_list).shape)
        print('max amp2 shape:', np.array(self.max2_list).shape)


    
    def save(self):
        """
        Saves currently appended DAC, difference frequency, sampled data, and unix values
    
        Parameters:
        dac_values (list): List of bit values DAC is set to
        df_values (list): List of difference frequencies
        wave_values (list): List of data sampled from SDR
        unix_values (list): List of unix values
    
        """
        files(save_path)
        current_time = datetime.datetime.now()
        timestamp = current_time.strftime('%Y-%m-%d_%H-%M-%S')
        directory = '/home/dominiv/simulink/dac/adc_data/'
        
        np.save(directory + 'counts'+save_path +  f'/count_values_{timestamp}', np.array(self.count_list))
        np.save(directory + 'adc1'+save_path + f'/adc1_values_{timestamp}', np.array(self.adc1_list))
        np.save(directory + 'adc2'+save_path + f'/adc2_values_{timestamp}', np.array(self.adc2_list))
        np.save(directory + 'max_amp1'+save_path + f'/max_amp1_{timestamp}', np.array(self.max1_list))
        np.save(directory + 'max_amp2'+save_path + f'/max_amp2_{timestamp}', np.array(self.max2_list))
        np.save(directory + 'ave'+save_path + f'/ave_{timestamp}', np.array(self.ave_list))
        print(f'saved on {timestamp}')    
        print('saved!')

    def save_reset(self):
        self.count_list = []
        self.adc1_list = []
        self.adc2_list = []
        self.max1_list = []
        self.max2_list = []
        self.ave_list = []
        print('lists reset')

    def test_data(self):
        self.x = np.linspace(self.a, self.b, 1024)
        self.f = 10e6

        #self.sin = np.sin(2*np.pi*self.x*self.f)
        self.sin = self.x
        self.adc_in1 = self.sin

        self.adc_in2 = -self.sin

        self.adc1_list.append(self.adc_in1)
        self.adc2_list.append(self.adc_in2)
        self.count_list.append(x)
        self.a += self.x.size
        self.b += self.x.size


if args.p1:
    p = Plotter(frequency,amplitude,IP,program)
    try:
        num = 0
        p.make_fig()
        p.x_axis()
        past = time.time()
        starting = time.time()
        ending = time.time()
        while ending-starting<=limit:
            current = time.time()
            p.data_capture()
            #data = test_data()
            print('data captured')
            p.plot_live()
            num += 1
            print(num)
            ending = time.time()
            if current - past >= sec:
                p.max_value()
                past = time.time()
            if num == 50 and args.s:
                p.save()
                p.save_reset()
                num = 0
            #plt.pause(.1)
    except KeyboardInterrupt:
        print('stopped plotting')



if args.p2:
    p = Plotter(frequency,amplitude,IP,program)
    try:
        num = 0
        p.make_fig()
        p.x_axis()
        p.data_capture()
        p.plot_single()
    except KeyboardInterrupt:
        print('stopped plotting')

if args.p0:
    p = Plotter(frequency,amplitude,IP,program)
    p.x_axis()
    try:
        num = 0
        past = time.time()
        starting = time.time()
        ending = time.time()
        while ending-starting<=limit:
            current = time.time()
            p.data_capture()
            print('data captured')
            num += 1
            print(num)
            ending = time.time()
            if current - past >= sec:
                p.max_value()
                past = time.time()
            if num == 50 and args.s:
                p.save()
                p.save_reset()
                num = 0
            #plt.pause(.1)
    except KeyboardInterrupt:
        print('stopped plotting')

if args.pt:
    p = Plotter(frequency,amplitude,IP,program, test=True)
    p.x_axis()
    try:
        num = 0
        #p.make_fig()
        past = time.time()
        while True:
            current = time.time()
            p.test_data()
            #data = test_data()
            print('data captured')
            #p.plot_live()
            num += 1
            print(num)
            if current - past >= sec:
                p.max_value()
                past = time.time()
            if num == 50 and args.s:
                p.save()
                p.save_reset()
                num = 0
            #plt.pause(.1)
    except KeyboardInterrupt:
        print('stopped plotting')
print('time elapsed:', (ending-starting)/60, 'min')
print('done')



#
#rp = casperfpga.CasperFpga(IP)
#rp.upload_to_ram_and_program(program)
#print(f'FPGA IP: {IP}')
#print(f'FPGA Bitstream: {bitstream}')
## Arm the snapshot block
#print('arming snapshot block...')
#rp.snapshots.adc_in_snap_ss.arm()
#print('done')
#
#read_length = 1024
#
## Configure FPGA registers
#rp.registers.reg_cntrl.write(rst_cntrl='pulse')
#rp.write_int('my_ampl_register', int(amplitude))
#rp.write_int('my_freq_register', int(frequency))
#print('Frequency and Amplitude Set')
#print(int(frequency), rp.read_int("my_freq_register"))
#print(int(amplitude), rp.read_int("my_ampl_register"))
#print('Measured clock speed:', rp.estimate_fpga_clock())
#
##adc_in = rp.snapshots.adc_in_snap_ss.read(arm=False)['data']
#
## Function to capture data
#def data_capture():
#    rp.snapshots.adc_in_snap_ss.arm()
#    rp.registers.reg_cntrl.write(rst_cntrl='pulse')
#    adc_in = rp.snapshots.adc_in_snap_ss.read(arm=False)['data']
#    adc_in1 = np.array(adc_in['adc_data_ch1'])
#    adc_in2 = np.array(adc_in['adc_data_ch2'])
#    #x = np.linspace(0, len(adc_in))
#    x = np.arange(len(adc_in1))
#    print(adc_in1)
#    return x, adc_in1, adc_in2
#
## Initialize plot variables globally
#fig, ax = None, None
#line1 = None
#line2 = None
#
#def make_fig():
#    plt.ion()
#    fig, (ax1, ax2) = plt.subplots(2,1,figsize=(10, 6))
#    line1 = ax1.plot([], [], 'black', label='input 1')
#    ax1.set_title('signal to adc')
#    ax1.set_xlabel('counts')
#    ax1.set_ylabel('amplitude')
#    ax1.legend()
#
#    line2 = ax2.plot([], [], 'black', label='input 2')
#    ax2.set_title('dac to adc')
#    ax2.set_xlabel('counts')
#    ax2.set_ylabel('amplitude')
#    ax2.legend()
#    print('starting live plot')
#    return line1, line2
#
## Function to plot live data
#def plot_live(x):
#    line1[0].set_xdata(x[0])  # Access the first element of the line list
#    line1[0].set_ydata(x[1])
#    ax1.relim()
#    ax1.autoscale_view()
#    line2[0].set_xdata(x[0])  # Access the first element of the line list
#    line2[0].set_ydata(x[2])
#    ax2.relim()
#    ax2.autoscale_view()
#    fig.canvas.draw()
#    fig.canvas.flush_events()
#    fig.canvas.draw()
#    fig.canvas.flush_events()
#    #plt.pause(0.1)
#
#
#a = 0
#b = 1024
#
## Test data function
#def test_data():
#    global a, b
#    a += 1024
#    b += 1024
#    x = np.linspace(a, b)
#    sin = np.sin(x)
#    return x, sin
#
## Run live plot if --p1 is passed
#if args.p1:
#    try:
#        make_fig()
#        while True:
#            data = data_capture()
#            #data = test_data()
#            print('data captured')
#            plot_live(data)
#            plt.pause(.1)
#    except KeyboardInterrupt:
#        print('stopped plotting')
#
#print('done')
#
