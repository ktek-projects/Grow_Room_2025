#!/usr/bin/env python3
"""
BME280 Sensor Data Logger to InfluxDB (DFRobot Library)
Reads temperature, humidity, and pressure every 60 seconds
"""

import time
import sys
import math
from datetime import datetime
from influxdb import InfluxDBClient
import os

# Add the DFRobot library path
sys.path.append(os.path.expanduser('~/DFRobot_BME280/python/raspberrypi'))
from DFRobot_BME280 import *

# InfluxDB Configuration
INFLUX_HOST = 'localhost'
INFLUX_PORT = 8086
INFLUX_DATABASE = 'growroom'

# BME280 Configuration
I2C_BUS = 1
I2C_ADDRESS = 0x77  # DFRobot BME280 I2C address

# Measurement interval (seconds)
INTERVAL = 60

def setup_bme280():
    """Initialize BME280 sensor using DFRobot library"""
    try:
        sensor = DFRobot_BME280_I2C(i2c_addr=I2C_ADDRESS, bus=I2C_BUS)
        
        # Check if sensor is detected
        retry_count = 0
        while not sensor.begin():
            retry_count += 1
            if retry_count > 3:
                print(f"Error: BME280 sensor not detected at address 0x{I2C_ADDRESS:02x}")
                print("Please check wiring and I2C address")
                sys.exit(1)
            print(f"Attempting to connect to sensor... (attempt {retry_count}/3)")
            time.sleep(2)
        
        print(f"BME280 sensor initialized successfully at address 0x{I2C_ADDRESS:02x}")
        
        # Configure sensor settings
        sensor.set_config_filter(BME280_IIR_FILTER_SETTINGS[0])
        sensor.set_config_T_standby(BME280_CONFIG_STANDBY_TIME_125)
        sensor.set_ctrl_meas_sampling_temp(BME280_TEMP_OSR_SETTINGS[3])
        sensor.set_ctrl_meas_sampling_press(BME280_PRESS_OSR_SETTINGS[3])
        sensor.set_ctrl_sampling_humi(BME280_HUMI_OSR_SETTINGS[3])
        sensor.set_ctrl_meas_mode(NORMAL_MODE)
        
        time.sleep(2)  # Wait for configuration to complete
        print("Sensor configuration complete")
        
        return sensor
    except Exception as e:
        print(f"Error initializing BME280: {e}")
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

def calculate_vpd(temperature, humidity):
    """
    Calculate Vapor Pressure Deficit (VPD)
    VPD = SVP - AVP
    where SVP = Saturated Vapor Pressure, AVP = Actual Vapor Pressure
    """
    try:
        # Calculate Saturated Vapor Pressure (SVP) using Magnus formula
        # SVP (kPa) = 0.61078 * exp(17.27 * T / (T + 237.3))
        svp = 0.61078 * math.exp((17.27 * temperature) / (temperature + 237.3))
        
        # Calculate Actual Vapor Pressure (AVP)
        # AVP = (RH / 100) * SVP
        avp = (humidity / 100.0) * svp
        
        # Calculate VPD
        vpd = svp - avp
        
        return round(vpd, 2)
    except Exception as e:
        print(f"Error calculating VPD: {e}")
        return None

def read_sensor_data(sensor):
    """Read data from BME280 sensor using DFRobot library"""
    try:
        # Check if data is ready
        if sensor.get_data_ready_status:
            # Read sensor data using properties (not methods!)
            temperature = sensor.get_temperature
            pressure = sensor.get_pressure / 100.0  # Convert Pa to hPa
            humidity = sensor.get_humidity
            
            # Calculate VPD
            vpd = calculate_vpd(temperature, humidity)
            
            return {
                'temperature': round(temperature, 2),
                'humidity': round(humidity, 2),
                'pressure': round(pressure, 2),
                'vpd': vpd
            }
        else:
            return None
    except Exception as e:
        print(f"Error reading sensor data: {e}")
        return None

def send_to_influxdb(client, data):
    """Send sensor data to InfluxDB"""
    try:
        json_body = [
            {
                "measurement": "environment",
                "tags": {
                    "location": "growroom",
                    "sensor": "bme280"
                },
                "fields": {
                    "temperature": data['temperature'],
                    "humidity": data['humidity'],
                    "pressure": data['pressure'],
                    "vpd": data['vpd']
                }
            }
        ]
        
        client.write_points(json_body)
        return True
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")
        return False

def main():
    """Main loop"""
    print("Starting BME280 to InfluxDB Logger (DFRobot)")
    print("="*50)
    
    # Initialize sensor and database
    sensor = setup_bme280()
    influx_client = setup_influxdb()
    
    print(f"Logging interval: {INTERVAL} seconds")
    print("Press Ctrl+C to stop")
    print("="*50)
    
    try:
        while True:
            # Read sensor data
            sensor_data = read_sensor_data(sensor)
            
            if sensor_data:
                # Send to InfluxDB
                if send_to_influxdb(influx_client, sensor_data):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] T: {sensor_data['temperature']}°C | "
                          f"H: {sensor_data['humidity']}% | "
                          f"P: {sensor_data['pressure']}hPa | "
                          f"VPD: {sensor_data['vpd']}kPa")
                else:
                    print("Failed to send data to InfluxDB")
            else:
                print("Waiting for sensor data to be ready...")
            
            # Wait for next reading
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\nStopping logger...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        influx_client.close()
        print("Logger stopped")

if __name__ == "__main__":
    main()