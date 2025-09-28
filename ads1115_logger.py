#!/usr/bin/env python3
"""
ADS1115 Soil Moisture Sensor Logger to InfluxDB
Reads 2 capacitive soil moisture sensors every 60 seconds
"""

import time
import sys
from datetime import datetime
from influxdb import InfluxDBClient
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# InfluxDB Configuration
INFLUX_HOST = 'localhost'
INFLUX_PORT = 8086
INFLUX_DATABASE = 'growroom'

# ADS1115 Configuration
ADS_ADDRESS = 0x48
GAIN = 1  # +/- 4.096V range (good for 0-3.3V sensors)

# Measurement interval (seconds)
INTERVAL = 60

# Soil Moisture Sensor Calibration
# IMPORTANT: You need to calibrate these values for your specific sensors!
# To calibrate:
# 1. Put sensor in AIR (completely dry) and note the voltage - this is your DRY value
# 2. Put sensor in WATER (fully submerged) and note the voltage - this is your WET value
# 3. Update the values below

SENSOR_CONFIG = {
    'A0': {
        'enabled': True,
        'name': 'soil_moisture_1',
        'location': 'pot_1',
        'dry_voltage': 2.8,    # Voltage reading in dry air (calibrate this!)
        'wet_voltage': 1.2,    # Voltage reading in water (calibrate this!)
    },
    'A1': {
        'enabled': True,
        'name': 'soil_moisture_2',
        'location': 'pot_2',
        'dry_voltage': 2.8,    # Voltage reading in dry air (calibrate this!)
        'wet_voltage': 1.2,    # Voltage reading in water (calibrate this!)
    },
    'A2': {
        'enabled': False,
        'name': 'unused_3',
        'location': 'unused',
        'dry_voltage': 2.8,
        'wet_voltage': 1.2,
    },
    'A3': {
        'enabled': False,
        'name': 'unused_4',
        'location': 'unused',
        'dry_voltage': 2.8,
        'wet_voltage': 1.2,
    }
}

def calculate_moisture_percent(voltage, dry_voltage, wet_voltage):
    """
    Convert voltage to moisture percentage
    0% = completely dry (in air)
    100% = completely wet (in water)
    """
    try:
        # Calculate percentage (inverted because capacitive sensors read lower voltage when wet)
        moisture_percent = ((dry_voltage - voltage) / (dry_voltage - wet_voltage)) * 100
        
        # Constrain to 0-100%
        moisture_percent = max(0, min(100, moisture_percent))
        
        return round(moisture_percent, 1)
    except Exception as e:
        print(f"Error calculating moisture: {e}")
        return None

def setup_ads1115():
    """Initialize ADS1115 ADC"""
    try:
        # Create the I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)
        
        # Create the ADS1115 object with specific address
        ads = ADS.ADS1115(i2c, gain=GAIN, address=ADS_ADDRESS)
        
        print(f"ADS1115 initialized successfully at address 0x{ADS_ADDRESS:02x}")
        print(f"Gain setting: {GAIN} (+/- 4.096V)")
        return ads
    except Exception as e:
        print(f"Error initializing ADS1115: {e}")
        print("Please check I2C connection and address")
        sys.exit(1)

def setup_influxdb():
    """Initialize InfluxDB client"""
    try:
        client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT)
        
        # Check if database exists, create if not
        databases = client.get_list_database()
        if not any(db['name'] == INFLUX_DATABASE for db in databases):
            client.create_database(INFLUX_DATABASE)
            print(f"Created database: {INFLUX_DATABASE}")
        
        client.switch_database(INFLUX_DATABASE)
        print(f"Connected to InfluxDB database: {INFLUX_DATABASE}")
        return client
    except Exception as e:
        print(f"Error connecting to InfluxDB: {e}")
        sys.exit(1)

def read_soil_sensors(ads):
    """Read all enabled soil moisture sensors"""
    data = {}
    
    try:
        # Map channel names to ADC pins
        channels = {
            'A0': ADS.P0,
            'A1': ADS.P1,
            'A2': ADS.P2,
            'A3': ADS.P3
        }
        
        for channel_name, channel_pin in channels.items():
            config = SENSOR_CONFIG[channel_name]
            
            if config['enabled']:
                # Create analog input for this channel
                chan = AnalogIn(ads, channel_pin)
                
                # Read voltage
                voltage = chan.voltage
                
                # Calculate moisture percentage
                moisture = calculate_moisture_percent(
                    voltage,
                    config['dry_voltage'],
                    config['wet_voltage']
                )
                
                data[channel_name] = {
                    'name': config['name'],
                    'location': config['location'],
                    'voltage': round(voltage, 3),
                    'moisture_percent': moisture
                }
        
        return data
    except Exception as e:
        print(f"Error reading soil sensors: {e}")
        return None

def send_to_influxdb(client, data):
    """Send soil moisture data to InfluxDB"""
    try:
        json_body = []
        
        for channel, values in data.items():
            # Create a data point for each sensor
            json_body.append({
                "measurement": "soil_moisture",
                "tags": {
                    "location": "growroom",
                    "sensor": values['name'],
                    "pot": values['location'],
                    "channel": channel
                },
                "fields": {
                    "voltage": float(values['voltage']),
                    "moisture_percent": float(values['moisture_percent']) if values['moisture_percent'] is not None else None
                }
            })
        
        client.write_points(json_body)
        return True
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")
        return False

def main():
    """Main loop"""
    print("Starting Soil Moisture Sensor Logger (ADS1115)")
    print("="*60)
    
    # Initialize ADC and database
    ads = setup_ads1115()
    influx_client = setup_influxdb()
    
    # Display enabled sensors
    print("\nEnabled sensors:")
    for channel, config in SENSOR_CONFIG.items():
        if config['enabled']:
            print(f"  {channel}: {config['name']} at {config['location']}")
    
    print("\n⚠️  CALIBRATION REMINDER:")
    print("  Make sure you've calibrated dry_voltage and wet_voltage")
    print("  for accurate moisture readings!")
    
    print(f"\nLogging interval: {INTERVAL} seconds")
    print("Press Ctrl+C to stop")
    print("="*60)
    
    try:
        while True:
            # Read soil moisture data
            sensor_data = read_soil_sensors(ads)
            
            if sensor_data:
                # Send to InfluxDB
                if send_to_influxdb(influx_client, sensor_data):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n[{timestamp}]")
                    
                    # Display readings
                    for channel, values in sensor_data.items():
                        print(f"  {values['name']} ({values['location']}): "
                              f"{values['moisture_percent']}% "
                              f"({values['voltage']}V)")
                else:
                    print("Failed to send data to InfluxDB")
            else:
                print("Failed to read sensor data")
            
            # Wait for next reading
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nStopping logger...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        influx_client.close()
        print("Logger stopped")

if __name__ == "__main__":
    main()