import RPi.GPIO as GPIO
from multiprocessing import Manager, Process
from threading import Thread, Lock
import os
import time
import signal
from time import sleep
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3

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

GBTN = 25
RBTN = 27
ErrBTN = 24
Water_Level= 10
pressure_cancel=18
ShutdownBtn=22
FillCaus=23
FillPaa=14
Inputs = [25,27,24,10,18,22,14,23]

STBYlight = 11
InProceslight = 9
Errlight =6
Pump = 13
Heat = 5
Main_Drain = 19
Water_In = 26
Air_In = 0
Caustic_In = 15
Caustic_Out = 7
Paa_In = 8
Paa_Out =16
Co2_In = 21
keg1= 12
keg2= 20
Ground_Pneu_valves= 1

statuslights=[STBYlight,InProceslight,Errlight]

Outputs = [6,9,11,0,5,13,19,26,21,20,16,12,15,7,8,1]

ErrNmbr= 0
Btnstatus=0
Callsucsess=0

Pressurein = 0
Pressureout= 0
PressureguageC = 30
Pressurinthresh=5
Pumppressurethresh=5
Pressuroutthresh= 5
kegpresuuredest= 15 #keg pressure setination- changeble vars
washer_thread = None
thread_running = False
FromWebVars = [1, 2, 3]
current_values=[]

# Setup GPIO
GPIO.setup(Outputs, GPIO.OUT)
GPIO.setup(Inputs, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.output(Outputs, GPIO.LOW)



@app.route('/update', methods=['POST'])
def update_variable():
    global shared_values
    try:
        # Check if the values were sent in the form and update them
        if 'index0' in request.form and request.form['index0']:
            new_value = int(request.form['index0'])
            with lock:
                shared_values[0] = new_value
            update_db_value('FirstAirPurgeRecure', new_value)  # Update DB

        if 'index1' in request.form and request.form['index1']:
            new_value = int(request.form['index1'])
            with lock:
                shared_values[1] = new_value
            update_db_value('FirstAirPurgeTon', new_value)  # Update DB

        if 'index2' in request.form and request.form['index2']:
            new_value = int(request.form['index2'])
            with lock:
                shared_values[2] = new_value
            update_db_value('FirstAirPurgeToff', new_value)  # Update DB

        print(f"Updated shared values: {list(shared_values)}")

        # Return the updated values in the response
        return jsonify(success=True, new_values=list(shared_values))

    except Exception as e:
        print(f"Error updating shared values: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/')
def index():
    #print("Index route is being called")
    #return "Hello from the index route!"
    print("Index route is being called")
    settings = get_current_settings()  # Fetch current settings
    return render_template('index.html', settings=settings)
    print("compleete")

@app.route('/get_initial_values', methods=['GET'])
def get_initial_values():
    # Prepare initial values to return, for example, shared_values
    initial_values = {
        'FirstAirPurgeRecure': shared_values[0],
        'FirstAirPurgeTon': shared_values[1],
        'FirstAirPurgeToff': shared_values[2],
        'Pressurein': Pressurein,
        'Pressureout': Pressureout
    }
    
    # Return the initial values in a JSON response
    return jsonify({
        'success': True,
        'initial_values': initial_values
    })
    
@app.route('/reset', methods=['POST'])
def reset_variables():
    try:
        # Set defaults
        reset_values = {
            'FirstAirPurgeRecure': 1,
            'FirstAirPurgeTon': 1,
            'FirstAirPurgeToff': 1.5
        }

        # Update the database with default values
        for param, default_value in reset_values.items():
            update_db_value(param, default_value)
            # Update shared values in memory as well
            if param == 'FirstAirPurgeRecure':
                shared_values[0] = default_value
            elif param == 'FirstAirPurgeTon':
                shared_values[1] = default_value
            elif param == 'FirstAirPurgeToff':
                shared_values[2] = default_value

        print(f"Reset shared values: {list(shared_values)}")  # Log the reset shared values

        # Return default values to the frontend
        return jsonify(success=True, new_values=reset_values)

    except Exception as e:
        print(f"Error resetting values: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

def update_db_value(parameter, value):
    """
    Helper function to update a specific value in the database.
    :param parameter: The name of the parameter (e.g. 'FirstAirPurgeRecure')
    :param value: The new value to be set
    """
    try:
        conn = sqlite3.connect('/home/raspberry/Desktop/keg_washer/settings.db')
        cursor = conn.cursor()
        
        # Ensure we're updating the correct row (id=1)
        query = f"UPDATE settings SET {parameter} = ? WHERE id = 1"
        cursor.execute(query, (value,))
        conn.commit()
        conn.close()
        print("db updated")
    except Exception as e:
        print(f"Error updating database value for {parameter}: {str(e)}")

@app.route('/test')
def test_route():
    return "Test route works!"   

# Flask Error Handler
@app.errorhandler(500)
def internal_error(error):
    return f"Internal Server Error: {str(error)}", 500

# Cycle function to actually use the updated values from Flask
def Cycle():
    global ErrNmbr, Pressurein, Pressureout
    
    last_shared_values = None  # Track previous values
    print ("cycle start")
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
        sleep(300)


def checkbtn():
    global Btnstatus
    Btnstatus = 0
    if GPIO.input(ErrBTN) == GPIO.HIGH:
        Btnstatus=3
    if GPIO.input(GBTN) == GPIO.HIGH and GPIO.input(RBTN) == GPIO.LOW:
        Btnstatus=2
    if GPIO.input(RBTN) == GPIO.HIGH and GPIO.input(GBTN) == GPIO.LOW:
        Btnstatus=1
    if GPIO.input(RBTN) == GPIO.LOW and GPIO.input(GBTN) == GPIO.LOW:
        Btnstatus=4

def shutdown():
    shutStarted = 0
    Shutdown_pushTime=0
    Shutdown_push_req=10
    while True:
        while Shutdown_pushTime < Shutdown_push_req:
            sleep(0.01)
            if GPIO.input(ShutdownBtn) == GPIO.HIGH and shutStarted == 0:
                Shutdown_pushTime=Shutdown_pushTime+1
        print('shuting down')
        os.system("sudo systemctl poweroff")
        shutStarted = 1

def main():
    global ErrNmbr
    OutputstateH= None
    procind=0
    Pause=0
    stop=0
    push_req = 70
    Pauseproc= None
    fillproc = Process(target=filltanks)
    fillproc.start()
    Pause=0
    Stdby()
    print('Stdby parameters set for first time')
    proc= None
    push_req = 70
    ErrNmbr=0
    starttime=0
    resumetime=0 
    pausedtime=0
    totaltime=0
    pauseddurationtime=0
    printtime=0
    RPtime=0
    minutes=00
    seconds=00
    
    ##################################################test
    proc = Thread(target=Cycle)
    proc.daemon = True  # Daemonize so it ends when the main program ends
    proc.start()
    
def boot():
    global ErrNmbr
    global Pressurein
    global Pressureout
    global VLout
    global VLin
    global Callsucsess
    Errproc= None
    testsucsess=0
    pressed=0
    shared_values[0] = 1
    shared_values[1] = 1
    shared_values[2] = 1.5
    
    
    
    Heatproc = Process(target=protectheat)
    Heatproc.start()
    print('heat elament protection active')
    
    Shutproc = Process(target=shutdown)
    Shutproc.start()
    print('Shutdown protection active')
    
    def preboot():
        GPIO.output(Outputs, GPIO.LOW)
        x=0
        while x<3:
            a=statuslights[x]
            GPIO.output(statuslights, GPIO.LOW)
            GPIO.output(a, GPIO.HIGH)
            x=x+1
            sleep(0.5)
            if x==3:
                x=0
                GPIO.output(statuslights, GPIO.LOW)
        if GPIO.input(pressure_cancel) == GPIO.LOW:
            print('Launching test cycle')
    
    prebootproc = Process(target=preboot)
    prebootproc.start()
    GPIO.output(Outputs, GPIO.LOW) 
    #####################################################B=0
    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
    checkbtn()
    shared_values[0] = 1
    shared_values[1] = 1
    shared_values[2] = 1.5
    print("Boot process initialized")
    last_shared_values = None  # Track previous values    
    # Start system cycle thread
    prebootproc.terminate()#FOR test
    main_thread = Thread(target=main)
    main_thread.daemon = True  # Daemonize so it ends when the main program ends
    #main_thread.start()
    
    
    # Run Flask app in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    
    # Wait for the Flask thread to finish (will never happen as Flask is a long-running process)
    flask_thread.join()

   
# Run Flask app in a separate thread
def run_flask():
    print("flask runing")
    #app.run(host='0.0.0.0', port=5000, debug=False)
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'), debug=False)
    

# Cleanup GPIO function
def cleanup_gpio():
    GPIO.cleanup()

# Start the system
if __name__ == "__main__":
    try:
        boot()
    except KeyboardInterrupt:
        print("Shutting down...")



