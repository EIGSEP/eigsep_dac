import numpy as np
import matplotlib.pyplot as plt
import glob
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from scipy import interpolate



parser = ArgumentParser(description = 'plot', formatter_class = ArgumentDefaultsHelpFormatter)
parser.add_argument('-f', dest = 'file_number_', type = str, help = 'File ending for data')

parser.add_argument('--p1', action = 'store_true', help = 'Display plot: max amplitudes')
parser.add_argument('--p2', action = 'store_true', help = 'Display plot: adc1')
parser.add_argument('--p3', action = 'store_true', help = 'Display plot: adc2')
parser.add_argument('--p4', action = 'store_true', help = 'Display plot: ave')
parser.add_argument('--p5', action = 'store_true', help = 'Display plots: ave and amp1')
parser.add_argument('--p6', action = 'store_true', help = 'Display plots: stack')
args = parser.parse_args()
file_number = args.file_number_


directory = '/home/dominiv/simulink/dac/adc_data/'
ending = file_number

data_ = np.loadtxt('/home/dominiv/simulink/dac/scripts/celsius_data.txt')
x = data_[:,0]
y = data_[:,1]*1e3
r_0 = 10000
r_fix = 10000
b_0 = 333
N = 14
f = interpolate.interp1d(y,x)

def bit_res(bit):
    r = r_fix*((b_0/bit)*((r_0+r_fix)/r_0)-1)
    return r

def load_data(name, extra=False, additive=None):
    if extra:
        my_list = sorted(glob.glob(directory + name + str(ending) +str(additive)+'/*'))
        print((directory + name + ending+'_on' +'/*'))
        my_array = []
        for i in my_list:
            data = np.load(i)
            my_array.append(data)
        name = np.concatenate(my_array, axis = 0)
        return name
    

    my_list = sorted(glob.glob(directory + name + str(ending) +'/*'))
    print((directory + name + ending +'/*'))
    my_array = []
    for i in my_list:
        data = np.load(i)
        my_array.append(data)
    name = np.concatenate(my_array, axis = 0)
    return name

def plotter(x=None,*args, sharex=False,sharey=False, **kwargs):
    number = len(args)
    print(number)
    if x is None:
        x = list(range(len(args[0])))

    fig, ax = plt.subplots(number,1, sharex=sharex, sharey=sharey, figsize=(10,6))
    if number == 1:
        ax=[ax]

    for i,data in enumerate(args):
        label = kwargs.get(f"label{i+1}", f"Data {i + 1}")
        axisx = kwargs.get(f"axisx{i+1}", f"axis {i + 1}")
        axisy = kwargs.get(f"axisy{i+1}", f"axis {i + 1}")
        title = kwargs.get(f"title", f"title {i + 1}")
        ax[i].plot(x,data, color='black', label = label)
        ax[i].set_xlabel(axisx)
        ax[i].set_ylabel(axisy)
        ax[0].set_title(title)

    plt.legend()
    plt.tight_layout()
    plt.show()









if args.p1:
    amp1 = load_data('max_amp1')
    amp2 = load_data('max_amp2')
    print('amp1 shape:', amp1.shape)
    print('amp2 shape:', amp2.shape)
    plotter(None,amp1,amp2,sharex=False,sharey=False, label1='max_amp1', label2='max_amp2', axisx1='counts', axisx2='counts', axisy1='amplitude',axisy2='amp',title='ADC Max Amps')


if args.p2:
    adc1 = load_data('adc1')
    adc2 = load_data('adc2')
    print('adc1 shape:', adc1.shape)
    print('adc2 shape:', adc2.shape)
    plotter(None,adc1[0],adc2[0],sharex=True,sharey=False,label1='adc1',label2='adc2',axisx1='counts',axisx2='adc inputs', title='ADC Data')

#if args.p3:
#    plt.figure()
#    plt.plot(adc2[0], label = 'adc2 data')
#    plt.legend()
#    plt.ylabel('Amplitudes')
#    plt.xlabel('Counts')
#    plt.show()
#
#if args.p4:
#    plt.figure()
#    plt.plot(ave[0], label = 'ave data')
#    plt.legend()
#    plt.ylabel('Average Temp')
#    plt.xlabel('Counts')
#    plt.show()

if args.p5:
    ave = load_data('ave')[8:]
    ave = f(bit_res(ave))
    amp2 = load_data('max_amp2')[8:]
    print('ave shape:', ave.shape)
    print('amp2 shape:', amp2.shape)

    plotter(None,ave,amp2,sharex=True,sharey=False, label1='ave', label2='max_amp2', axisx1='counts', axisx2='counts', axisy1='Celsius',axisy2='max amp bit',title='Temp and Max Amp')




if args.p6:
    aven = load_data('ave', extra=True, additive='_on')
    amp2n = load_data('max_amp2', extra=True, additive='_on')
    avef = load_data('ave', extra=True, additive='_off')
    amp2f = load_data('max_amp2', extra=True, additive='_off')
    

    
    ave = np.concatenate((aven, avef))#0.00039166598100936627#*0.02635658914728682
    amp2 = np.concatenate((amp2n, amp2f))
    print(ave.shape, amp2.shape)
    ave = f(bit_res(ave))


    plotter(None,ave,amp2,sharex=True,sharey=False, label1='ave', label2='max_amp2', axisx1='counts', axisx2='counts', axisy1='Celsius',axisy2='max amp bit',title='Temp and Max Amp')

