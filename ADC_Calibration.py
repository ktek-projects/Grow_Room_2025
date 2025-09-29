# Run this calibration helper script
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import time

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c, gain=1, address=0x48)

print('=== Soil Moisture Sensor Calibration ===')
print('\nSensor 1 (Channel A0):')
print('Put sensor in DRY AIR, then press Enter...')
input()
chan0 = AnalogIn(ads, ADS.P0)
dry1 = chan0.voltage
print(f'Dry voltage A0: {dry1:.3f}V')
print('Put sensor in WATER, then press Enter...')
input()
wet1 = chan0.voltage
print(f'Wet voltage A0: {wet1:.3f}V')

print('\nSensor 2 (Channel A1):')
print('Put sensor in DRY AIR, then press Enter...')
input()
chan1 = AnalogIn(ads, ADS.P1)
dry2 = chan1.voltage
print(f'Dry voltage A1: {dry2:.3f}V')
print('Put sensor in WATER, then press Enter...')
input()
wet2 = chan1.voltage
print(f'Wet voltage A1: {wet2:.3f}V')
