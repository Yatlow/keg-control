import RPi.GPIO as GPIO
from multiprocessing import Manager
from threading import Thread, Lock
import os
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from flask import Flask, request, jsonify
from flask_cors import CORS

# GPIO Setup
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Flask app setup
app = Flask(__name__)
CORS(app)

# Initialize I2C and ADCs
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
Pressureinraw = AnalogIn(ads, ADS.P2)
Pressureoutraw = AnalogIn(ads, ADS.P3)

# Define pin numbers
Inputs = [25, 27, 24, 10, 18, 22, 14, 23]
Outputs = [6, 9, 11, 0, 5, 13, 19, 26, 21, 20, 16, 12, 15, 7, 8, 1]
Errlight = 6
InProceslight = 9
STBYlight = 11
ErrNmbr = 0

# Initialize shared variables and locks
manager = Manager()
shared_values = manager.list([0, 0, 0])  # Placeholder for three values
lock = Lock()

# Setup GPIO
GPIO.setup(Outputs, GPIO.OUT)
GPIO.setup(Inputs, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.output(Outputs, GPIO.LOW)

# Global variables for pressure
Pressurein = 0
Pressureout = 0
PressureguageC = 30

# Pressure Conversion
def convert_pressure():
    global Pressurein, Pressureout, Pressureinraw, Pressureoutraw, PressureguageC
    VLin = 0.4
    VLout = 0.451
    pressureinmed = PressureguageC * (Pressureinraw.voltage - VLin) / 4
    pressureoutmed = PressureguageC * (Pressureoutraw.voltage - VLout) / 4
    Pressurein = round(pressureinmed, 2)
    Pressureout = round(pressureoutmed, 2)
    #print(f'Pressure in: {Pressurein} PSI, Pressure out: {Pressureout} PSI')

# Function to update shared values safely with a lock
@app.route('/update', methods=['POST'])
def update_variable():
    global shared_values
    try:
        if 'index0' in request.form and request.form['index0']:
            new_value = int(request.form['index0'])
            with lock:
                shared_values[0] = new_value
        if 'index1' in request.form and request.form['index1']:
            new_value = int(request.form['index1'])
            with lock:
                shared_values[1] = new_value
        if 'index2' in request.form and request.form['index2']:
            new_value = int(request.form['index2'])
            with lock:
                shared_values[2] = new_value

        print(f"Updated shared values: {list(shared_values)}")
        return jsonify(success=True, new_values=list(shared_values))
    except Exception as e:
        print(f"Error updating shared values: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

# Basic index route
@app.route('/')
def index():
    return "Keg Control API is running!"

# Flask Error Handler
@app.errorhandler(500)
def internal_error(error):
    return f"Internal Server Error: {str(error)}", 500

# Cycle function to actually use the updated values from Flask
def cycle(shared_values):
    global ErrNmbr, Pressurein, Pressureout
    
    last_shared_values = None  # Track previous values
    
    while True:
        with lock:  # Lock shared values for reading
            FirstAirPurgeRecure, FirstAirPurgeTon, FirstAirPurgeToff = shared_values[0], shared_values[1], shared_values[2]

        # Detect if shared values have changed
        if last_shared_values != list(shared_values):
            print(f"Shared values updated: {list(shared_values)}")
            last_shared_values = list(shared_values)
        
        # Sum the values for cycle conditions
        suming = FirstAirPurgeRecure + FirstAirPurgeTon + FirstAirPurgeToff
        print(f"Sum of values: {suming}")  # Print sum of the shared values
        
        # Control lights based on the sum of the values
        if suming < 100:
            GPIO.output(STBYlight, GPIO.HIGH)
            GPIO.output(InProceslight, GPIO.LOW)
            GPIO.output(Errlight, GPIO.LOW)
        if 100 <= suming < 1000:
            GPIO.output(STBYlight, GPIO.LOW)
            GPIO.output(InProceslight, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.LOW)
        if suming >= 1000:
            GPIO.output(STBYlight, GPIO.LOW)
            GPIO.output(InProceslight, GPIO.LOW)
            GPIO.output(Errlight, GPIO.HIGH)

        # Run pressure conversion logic
        convert_pressure()

        # Example condition: Check if Pressure in is too low or too high
        if Pressurein < 5 or Pressureout < 5:
            ErrNmbr = 6  # Timeout error for pressure
            #print(f"Error: Pressure values are too low. Pressure in: {Pressurein} PSI, Pressure out: {Pressureout} PSI")
        
        # Add a delay before the next cycle
        time.sleep(3)

# Threaded function for Flask app and background tasks
def run_flask():
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'), debug=False)

# GPIO Cleanup function
def cleanup_gpio():
    GPIO.cleanup()

# Boot process
def boot():
    # Simulate setting up initial parameters
    shared_values[0] = 1
    shared_values[1] = 1
    shared_values[2] = 1.5
    print("Boot process initialized")
    
    # Start system cycle thread
    cycle_thread = Thread(target=cycle, args=(shared_values,))
    cycle_thread.daemon = True  # Daemonize so it ends when the main program ends
    cycle_thread.start()

    # Run Flask app in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Wait for the Flask thread to finish (will never happen as Flask is a long-running process)
    flask_thread.join()

# Start the system
if __name__ == "__main__":
    try:
        boot()
    except KeyboardInterrupt:
        print("Shutting down...")
        cleanup_gpio()

