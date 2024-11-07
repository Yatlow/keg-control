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

manager = Manager()
shared_values = manager.list([
    1, #'preboobotMeteg': 1
    0,    #'pressureMeteg': 1
    1, # FirstAirPurgeRecure,   2
    1,  #FirstAirPurgeToff      3
    1.5,   #FirstAirPurgeTon    4 
    4,  # InitialWaterFlud      5
    6,  # recureMedSquirt       6
    0.4,  # medSquirtWaterOn      7
    0.3,  # medSquirtWaterOff     8
    5,  # recureShortSquirt     9
    0.2,  # ShortSquirtWaterOn    10
    0.15,  # ShortSquirtWaterOff   11
    5,  # recureLongSquirt      12
    1.6,  # LongSquirtWaterOn     13
    1.6,  # LongSquirtWaterOff    14
    11,  # RinseWaterWithPump    15
    5,  # PostWaterPurgeRecure  16
    1,  # PostWaterPurgeTon     17
    2,  # PostWaterPurgeToff    18
    5,  # InitialCausticFlud    19
    15,  # CausticRinseKeg1      20
    15,  # CausticRinseKeg2      21
    10,  # pressurizeCausticInKeg22
    15,  # causticSoakInKeg      23
    15,  # SecondCausticFlud     24
    15,  # recureShortCausticSquirt25
    0.3,  # CausticSquirtPumpOn   26
    0.3,  # CausticSquirtPumpOff  27
    7,  # recurePurgeCausticSquirt28
    0.2,  # airAndPumpIntervale   29
    7,  # recureLastCausticSquirt30
    1.2,  # CausticLastSquirtPumpOn31
    1.2,  # CausticLastSquirtPumpOff32
    3,  # PostCausticPurgeRecure33
    0.75,  # PostCausticPurgeTon34
    1,  # PostCausticPurgeToff35
    3,  # postCausticWaterRinseRecure37
    1,  # postCausticWaterRinseOn38
    2,  # postCausticWaterRinseOf39
    35,  # SanitizeInitialKeg140
    35,  # SanitizeInitialKeg241
    10,  # SanitizeInitialBothKegs42
    15,  # paaInitialPumpRecure43
    0.3,  # paaInitialPumpOn44
    0.3,  # paaInitialPumpOff45
    7,  # paaSquirtRecure46
    1.2,  # Co2PumpIntervale47
    100,  # postSquirtSanitizeBothKegs48
    9,  # co2PurgeKeg1Recure49
    0.7,  # co2PurgeKeg1Open50
    2.4,  # co2PurgeKeg1Closed51
    9,  # co2PurgeKeg2Recure52
    0.7,  # co2PurgeKeg2Open53
    2.4,  # co2PurgeKeg2Closed54
    5,  # co2PurgeBothKegsOpen55
    15,  # kegPdestination56
    12,  # TimeOutPdestination57
    15,  # PostTimeOutBuildP58
    35   # PTimeWhenSensorDisabled59
])
lock = Lock()

def get_current_settings():
    # Connect to the database
    conn = sqlite3.connect('/home/raspberry/Desktop/keg_washer/settings.db')
    cursor = conn.cursor()

    # Fetch all the settings for id = 1
    cursor.execute('SELECT * FROM settings WHERE id = 1')
    row = cursor.fetchone()
    conn.close()

    # Log the row to check the data
    print("Current settings:", row)

    # Return a dictionary with all the settings
    return {
        'preboobotMeteg': row[1],
        'pressureMeteg': row[2],
        'FirstAirPurgeRecure': row[3],
        'FirstAirPurgeTon': row[4],
        'FirstAirPurgeToff': row[5],
        'InitialWaterFlud': row[6],
        'recureMedSquirt': row[7],
        'medSquirtWaterOn': row[8],
        'medSquirtWaterOff': row[9],
        'recureShortSquirt': row[10],
        'ShortSquirtWaterOn': row[11],
        'ShortSquirtWaterOff': row[12],
        'recureLongSquirt': row[13],
        'LongSquirtWaterOn': row[14],
        'LongSquirtWaterOff': row[15],
        'RinseWaterWithPump': row[16],
        'PostWaterPurgeRecure': row[17],
        'PostWaterPurgeTon': row[18],
        'PostWaterPurgeToff': row[19],
        'InitialCausticFlud': row[20],
        'CausticRinseKeg1': row[21],
        'CausticRinseKeg2': row[22],
        'pressurizeCausticInKeg': row[23],
        'causticSoakInKeg': row[24],
        'SecondCausticFlud': row[25],
        'recureShortCausticSquirt': row[26],
        'CausticSquirtPumpOn': row[27],
        'CausticSquirtPumpOff': row[28],
        'recurePurgeCausticSquirt': row[29],
        'airAndPumpIntervale': row[30],
        'recureLastCausticSquirt': row[31],
        'CausticLastSquirtPumpOn': row[32],
        'CausticLastSquirtPumpOff': row[33],
        'PostCausticPurgeRecure': row[34],
        'PostCausticPurgeTon': row[35],
        'PostCausticPurgeToff': row[36],
        'postCausticWaterRinseRecure': row[37],
        'postCausticWaterRinseOn': row[38],
        'postCausticWaterRinseOf': row[39],
        'SanitizeInitialKeg1': row[40],
        'SanitizeInitialKeg2': row[41],
        'SanitizeInitialBothKegs': row[42],
        'paaInitialPumpRecure': row[43],
        'paaInitialPumpOn': row[44],
        'paaInitialPumpOff': row[45],
        'paaSquirtRecure': row[46],
        'Co2PumpIntervale': row[47],
        'postSquirtSanitizeBothKegs': row[48],
        'co2PurgeKeg1Recure': row[49],
        'co2PurgeKeg1Open': row[50],
        'co2PurgeKeg1Closed': row[51],
        'co2PurgeKeg2Recure': row[52],
        'co2PurgeKeg2Open': row[53],
        'co2PurgeKeg2Closed': row[54],
        'co2PurgeBothKegsOpen': row[55],
        'kegPdestination': row[56],
        'TimeOutPdestination': row[57],
        'PostTimeOutBuildP': row[58],
        'PTimeWhenSensorDisabled': row[59]
    }


    print('Stand By, Reddy for cycle')
    GPIO.cleanup()
    Outputs = [6,9,11,0,5,13,19,26,21,20,16,12,15,7,8,1]
    Inputs = [25,27,24,10,18,22,14,23]
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(Outputs, GPIO.OUT)
    GPIO.setup(Inputs, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.output(Outputs, GPIO.LOW)
    GPIO.output(STBYlight, GPIO.HIGH)

@app.route('/update', methods=['POST'])
def update_variable():
    global shared_values
    try:
        updated_values = {}
        for i, param in enumerate([
            'preboobotMeteg', 'pressureMeteg', 'FirstAirPurgeRecure', 'FirstAirPurgeTon', 'FirstAirPurgeToff',
            'InitialWaterFlud', 'recureMedSquirt', 'medSquirtWaterOn', 'medSquirtWaterOff', 'recureShortSquirt',
            'ShortSquirtWaterOn', 'ShortSquirtWaterOff', 'recureLongSquirt', 'LongSquirtWaterOn', 'LongSquirtWaterOff',
            'RinseWaterWithPump', 'PostWaterPurgeRecure', 'PostWaterPurgeTon', 'PostWaterPurgeToff', 'InitialCausticFlud',
            'CausticRinseKeg1', 'CausticRinseKeg2', 'pressurizeCausticInKeg', 'causticSoakInKeg', 'SecondCausticFlud',
            'recureShortCausticSquirt', 'CausticSquirtPumpOn', 'CausticSquirtPumpOff', 'recurePurgeCausticSquirt',
            'airAndPumpIntervale', 'recureLastCausticSquirt', 'CausticLastSquirtPumpOn', 'CausticLastSquirtPumpOff',
            'PostCausticPurgeRecure', 'PostCausticPurgeTon', 'PostCausticPurgeToff', 'postCausticWaterRinseRecure',
            'postCausticWaterRinseOn', 'postCausticWaterRinseOf', 'SanitizeInitialKeg1', 'SanitizeInitialKeg2',
            'SanitizeInitialBothKegs', 'paaInitialPumpRecure', 'paaInitialPumpOn', 'paaInitialPumpOff', 'paaSquirtRecure',
            'Co2PumpIntervale', 'postSquirtSanitizeBothKegs', 'co2PurgeKeg1Recure', 'co2PurgeKeg1Open',
            'co2PurgeKeg1Closed', 'co2PurgeKeg2Recure', 'co2PurgeKeg2Open', 'co2PurgeKeg2Closed', 'co2PurgeBothKegsOpen',
            'kegPdestination', 'TimeOutPdestination', 'PostTimeOutBuildP', 'PTimeWhenSensorDisabled'
        ]):
            if param in request.form and request.form[param]:
                new_value = float(request.form[param]) if '.' in request.form[param] else int(request.form[param])
                with lock:
                    shared_values[i] = new_value
                update_db_value(param, new_value)  # Update DB

                updated_values[param] = new_value

        print(f"Updated shared values: {updated_values}")

        return jsonify(success=True, updated_values=updated_values)

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
        'preboobotMeteg': shared_values[0],
        'pressureMeteg': shared_values[1],
        'FirstAirPurgeRecure': shared_values[2],
        'FirstAirPurgeTon': shared_values[3],
        'FirstAirPurgeToff': shared_values[4],
        'InitialWaterFlud': shared_values[5],
        'recureMedSquirt': shared_values[6],
        'medSquirtWaterOn': shared_values[7],
        'medSquirtWaterOff': shared_values[8],
        'recureShortSquirt': shared_values[9],
        'ShortSquirtWaterOn': shared_values[10],
        'ShortSquirtWaterOff': shared_values[11],
        'recureLongSquirt': shared_values[12],
        'LongSquirtWaterOn': shared_values[13],
        'LongSquirtWaterOff': shared_values[14],
        'RinseWaterWithPump': shared_values[15],
        'PostWaterPurgeRecure': shared_values[16],
        'PostWaterPurgeTon': shared_values[17],
        'PostWaterPurgeToff': shared_values[18],
        'InitialCausticFlud': shared_values[19],
        'CausticRinseKeg1': shared_values[20],
        'CausticRinseKeg2': shared_values[21],
        'pressurizeCausticInKeg': shared_values[22],
        'causticSoakInKeg': shared_values[23],
        'SecondCausticFlud': shared_values[24],
        'recureShortCausticSquirt': shared_values[25],
        'CausticSquirtPumpOn': shared_values[26],
        'CausticSquirtPumpOff': shared_values[27],
        'recurePurgeCausticSquirt': shared_values[28],
        'airAndPumpIntervale': shared_values[29],
        'recureLastCausticSquirt': shared_values[30],
        'CausticLastSquirtPumpOn': shared_values[31],
        'CausticLastSquirtPumpOff': shared_values[32],
        'PostCausticPurgeRecure': shared_values[33],
        'PostCausticPurgeTon': shared_values[34],
        'PostCausticPurgeToff': shared_values[35],
        'postCausticWaterRinseRecure': shared_values[36],
        'postCausticWaterRinseOn': shared_values[37],
        'postCausticWaterRinseOf': shared_values[38],
        'SanitizeInitialKeg1': shared_values[39],
        'SanitizeInitialKeg2': shared_values[40],
        'SanitizeInitialBothKegs': shared_values[41],
        'paaInitialPumpRecure': shared_values[42],
        'paaInitialPumpOn': shared_values[43],
        'paaInitialPumpOff': shared_values[44],
        'paaSquirtRecure': shared_values[45],
        'Co2PumpIntervale': shared_values[46],
        'postSquirtSanitizeBothKegs': shared_values[47],
        'co2PurgeKeg1Recure': shared_values[48],
        'co2PurgeKeg1Open': shared_values[49],
        'co2PurgeKeg1Closed': shared_values[50],
        'co2PurgeKeg2Recure': shared_values[51],
        'co2PurgeKeg2Open': shared_values[52],
        'co2PurgeKeg2Closed': shared_values[53],
        'co2PurgeBothKegsOpen': shared_values[54],
        'kegPdestination': shared_values[55],
        'TimeOutPdestination': shared_values[56],
        'PostTimeOutBuildP': shared_values[57],
        'PTimeWhenSensorDisabled': shared_values[58]
    }
    
    # Return the initial values in a JSON response
    return jsonify({
        'success': True,
        'initial_values': initial_values
    })

@app.route('/reset', methods=['POST'])
def reset_variables():
    try:
        # Default values for all variables
        reset_values = {
            'preboobotMeteg': 1,
            'pressureMeteg': 0,
            'FirstAirPurgeRecure': 1,
            'FirstAirPurgeTon': 1,
            'FirstAirPurgeToff': 1.5,
            'InitialWaterFlud': 4,
            'recureMedSquirt': 6,
            'medSquirtWaterOn': 0.4,
            'medSquirtWaterOff': 0.3,
            'recureShortSquirt': 5,
            'ShortSquirtWaterOn': 0.2,
            'ShortSquirtWaterOff': 0.15,
            'recureLongSquirt': 5,
            'LongSquirtWaterOn': 1.6,
            'LongSquirtWaterOff': 1.6,
            'RinseWaterWithPump': 11,
            'PostWaterPurgeRecure': 5,
            'PostWaterPurgeTon': 1,
            'PostWaterPurgeToff': 2,
            'InitialCausticFlud': 5,
            'CausticRinseKeg1': 15,
            'CausticRinseKeg2': 15,
            'pressurizeCausticInKeg': 10,
            'causticSoakInKeg': 15,
            'SecondCausticFlud': 15,
            'recureShortCausticSquirt': 15,
            'CausticSquirtPumpOn': 0.3,
            'CausticSquirtPumpOff': 0.3,
            'recurePurgeCausticSquirt': 7,
            'airAndPumpIntervale': 0.2,
            'recureLastCausticSquirt': 7,
            'CausticLastSquirtPumpOn': 1.2,
            'CausticLastSquirtPumpOff': 1.2,
            'PostCausticPurgeRecure': 3,
            'PostCausticPurgeTon': 0.75,
            'PostCausticPurgeToff': 1,
            'postCausticWaterRinseRecure': 3,
            'postCausticWaterRinseOn': 1,
            'postCausticWaterRinseOf': 2,
            'SanitizeInitialKeg1': 35,
            'SanitizeInitialKeg2': 35,
            'SanitizeInitialBothKegs': 10,
            'paaInitialPumpRecure': 15,
            'paaInitialPumpOn': 0.3,
            'paaInitialPumpOff': 0.3,
            'paaSquirtRecure': 7,
            'Co2PumpIntervale': 1.2,
            'postSquirtSanitizeBothKegs': 100,
            'co2PurgeKeg1Recure': 9,
            'co2PurgeKeg1Open': 0.7,
            'co2PurgeKeg1Closed': 2.4,
            'co2PurgeKeg2Recure': 9,
            'co2PurgeKeg2Open': 0.7,
            'co2PurgeKeg2Closed': 2.4,
            'co2PurgeBothKegsOpen': 5,
            'kegPdestination': 15,
            'TimeOutPdestination': 12,
            'PostTimeOutBuildP': 15,
            'PTimeWhenSensorDisabled': 35
        }

        # Update the database with default values
        for param, default_value in reset_values.items():
            update_db_value(param, default_value)
            # Update shared values in memory as well
            index = list(reset_values.keys()).index(param)
            shared_values[index] = default_value

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

def load_values_from_db():
    try:
        conn = sqlite3.connect('/home/raspberry/Desktop/keg_washer/settings.db')
        cursor = conn.cursor()

        # Fetch the latest values from the database
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        result = cursor.fetchone()

        if result:
            with lock:
                # Assign each value from the database to the shared_values list
                for i, value in enumerate(result[1:]):  # Skipping the 'id' column
                    shared_values[i] = value
            print(f"Loaded values from DB: {list(shared_values)}")
        conn.close()
    except Exception as e:
        print(f"Error loading values from DB: {str(e)}")

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
    
    def converttime(TT):
        global seconds
        global minutes        
        if TT<10:
            seconds=int(TT)
            print('00:0{}'.format(seconds))
        if TT>9 and TT<60:
            seconds=int(TT)
            print('00:{}'.format(seconds))
        if TT>60:
            M= round(TT/60,0)
            minutes=int(M)
            S=round((TT-(minutes*60)),0)
            seconds= int(S)
            if seconds<0:
                minutes=minutes-1
                seconds=seconds+60
            if minutes<9:
                if seconds>9:
                    print('0{}:{}'.format(minutes,seconds)) 
                if seconds<10:
                    print('0{}:0{}'.format(minutes,seconds))
            if minutes>9:
                if seconds>9:
                    print('{}:{}'.format(minutes,seconds)) 
                if seconds<10:
                    print('{}:0{}'.format(minutes,seconds))
       
            
    while True:
        pushTime = 0
        pressed = 0
        if stop==1:
            totaltime = (time.time() - starttime)
            printtime=round(totaltime,2)
            print('Stdby parameters set, program ran for')
            converttime(printtime)
            fillproc = Process(target=filltanks)
            fillproc.start()
            proc= None
            push_req = 70
            ErrNmbr=0
            procind=0
        while pushTime < push_req:#butoon examin
            checkbtn()
            sleep(0.01)
            pushTime = pushTime+1
            if Btnstatus==3 and ErrNmbr!=5:#checks if emergancy button is pressed
                push_req=20
                pressed=1
            if Pause==1 and Btnstatus==2 or Pause==1 and Btnstatus==4:
                push_req=20
            if Btnstatus==0: #checks if no butoon is pressed
                pushTime=0
                stop=0
                if proc and GPIO.input(GBTN) == GPIO.HIGH:
                    pressed = 1
            if proc!=None and proc.is_alive()==False:
                stop=1
                pushTime=push_req+1
        if pressed ==1: #will enter this loop only if a procces is runing and triger button was reliesed or in an emergancy eror           
            if Btnstatus==1:#green button scenarios
                if procind==1 or procind==3: 
                    if Pause==1: #checks if a cycle is currently Paused and green button was pressed log enogh to resume..
                        if Pauseproc:#if Pause indicator is on, turn it off
                            Pauseproc.terminate()
                            Pauseproc=None
                            Pause=0
                        GPIO.output(Outputs, GPIO.LOW)
                        if OutputstateH:
                            GPIO.output(OutputstateH, GPIO.HIGH)
                        os.kill(proc.pid, signal.SIGCONT)
                        resumetime= time.time()
                        pauseddurationtime=resumetime-pausedtime
                        starttime= starttime+pauseddurationtime
                        printtime=round(RPtime,2)
                        print('resume','Pausduration',round(pauseddurationtime,2))
                        converttime(printtime)
                        push_req = 20
                        pressed=0
                    if Pause ==0 and pressed==1:#checks if standert cycle was trigered and not Paused
                        if proc.is_alive()==True: #checks if cycle is active via checking standby light- for pausing
                            x=0
                            OutputstateH=[]
                            while x<16:
                                r=(Outputs[x])
                                if GPIO.input(r) == GPIO.HIGH:
                                    OutputstateH.append(r)
                                x=x+1
                            i=6
                            if i in OutputstateH:
                                totaltime = (time.time() - starttime)
                                printtime=round(totaltime,2)
                                proc.terminate()
                                Stdby()
                                stop=1 
                                proc=None
                                ErrNmbr = 0
                                print('stop/Err reset GBTN')
                                converttime(printtime)
                            else:
                                os.kill(proc.pid, signal.SIGSTOP)
                                Pauseproc= Process(target=Pauseindicator)
                                Pauseproc.start()
                                pausedtime= time.time()
                                RPtime= (time.time() - starttime)
                                printtime=round(RPtime,2)                            
                                print('Pause')
                                converttime(printtime)
                                Pause=1
                                push_req = 70                                
                if procind==2 or procind==4:#if another proc was trigered (emergancy eror/keg empty cycle) it will stop and return to standby
                    if Pause==1:#if Pause indicator is on, turn it off
                        Pauseproc.terminate()
                        Pauseproc=None
                        Pause=0
                    if proc.is_alive()== True:
                        totaltime = (time.time() - starttime)
                        printtime=round(totaltime,2)
                        proc.terminate()
                        Stdby()
                        stop=1 
                        proc=None
                        ErrNmbr = 0
                        print('stop/Err reset GBTN')
                        converttime(printtime)
            if Btnstatus==2:#red button will stop any procces and return to standby
                if Pause==1:#if Pause indicator is on, turn it off
                    Pauseproc.terminate()
                    Pauseproc=None
                    Pause=0
                if proc.is_alive()== True:
                    totaltime = (time.time() - starttime)
                    printtime=round(totaltime,2)
                    proc.terminate()
                    Stdby()
                    stop=1 
                    proc=None
                    ErrNmbr = 0
                    print('stop/Err reset RBTN')
                    converttime(printtime)
            if Btnstatus==3:#emergancy button will stop any procces and return to standby
                if Pause==1:#if Pause indicator is on, turn it off
                    Pauseproc.terminate()
                    Pauseproc=None
                    Pause=0
                if proc:
                    proc.terminate()
                    totaltime = (time.time() - starttime)
                    printtime=round(totaltime,2)
                    print('totaltime')
                    converttime(printtime)
                ErrNmbr = 5
                proc = Process(target=Err,args=(5,))
                proc.start()
                procind=4
                push_req = 20
            if Btnstatus ==4:#green & red buttons toogether will stop any procces and return to standby
                if Pause==1:#if Pause indicator is on, turn it off
                    Pauseproc.terminate()
                    Pauseproc=None
                    Pause=0
                if proc.is_alive()== True:
                    totaltime = (time.time() - starttime)
                    printtime=round(totaltime,2)
                    print('totaltime')
                    converttime(printtime)
                    proc.terminate()
                    Stdby()
                    stop=1 
                    proc=None
                    ErrNmbr = 0
                    print('stop/Err reset R&GBTN')
        if proc==None and stop ==0 and ErrNmbr==0:#if no proc is runing, and procces wasnt just aborted- will start apropriete procces
            print('startsomthing')
            if fillproc.is_alive()== True:
                fillproc.terminate()
            starttime = time.time()
            print("Start Time: 00:00",)
            if Btnstatus==1:
                proc = Thread(target=Cycle)
                procind=1
            if Btnstatus == 2:
                proc = Thread(target=purgecycle)
                procind=2
            if Btnstatus==4:
                proc = Thread(target=ShortCycle)
                procind=3
            GPIO.output(Outputs, GPIO.LOW)
            proc.daemon = True  # Daemonize so it ends when the main program ends
            proc.start()
            push_req=20
        checkbtn()

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
    #shared_values[0] = 1
    #shared_values[1] = 1
    #shared_values[2] = 1.5
    
    print("Boot process initialized")
    load_values_from_db()
    
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
    B=2 #for testing
    while B<1:
        ErrNmbr=0
        if pressed==0:
            print('Click GTBN for test cycle')
        if Errproc==None:
            if pressed==1:
                print('Click GTBN reset')
            pressed=0
        Boot_push_req = 5
        Boot_pushTime = 0
        EMRG=0
        while Boot_pushTime < Boot_push_req:
            sleep(0.01)
            checkbtn()
            if Btnstatus==0:
                if EMRG==1:
                    prebootproc = Process(target=preboot)
                    prebootproc.start()
                    EMRG=0
            if Btnstatus==1:
                Boot_pushTime=Boot_pushTime+1
                GPIO.output(Errlight,GPIO.LOW)
            else:
                Boot_pushTime=0
                pressed=0
                if Errproc:
                    pressed=1
            if Btnstatus==3:
                prebootproc.terminate()
                GPIO.output(statuslights, GPIO.LOW)
                GPIO.output(Errlight,GPIO.HIGH)
                print('Emergancy BTN Err #5')
                EMRG=1
                sleep(0.5)
            if Btnstatus==0 and prebootproc.is_alive()== True and Errproc:
                GPIO.output(statuslights, GPIO.LOW)
                GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                prebootproc.terminate()
            if GPIO.input(FillCaus) == GPIO.LOW:
                GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                GPIO.output(Water_In, GPIO.HIGH)   
                GPIO.output(Caustic_In, GPIO.HIGH)
            if GPIO.input(FillPaa) == GPIO.LOW:
                GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                GPIO.output(Water_In, GPIO.HIGH)   
                GPIO.output(Paa_In, GPIO.HIGH)
            if GPIO.input(FillCaus) == GPIO.HIGH and GPIO.input(FillPaa) == GPIO.HIGH:
                GPIO.output(Water_In, GPIO.LOW)
            if GPIO.input(FillCaus) == GPIO.HIGH:
                GPIO.output(Caustic_In, GPIO.LOW)
            if GPIO.input(FillPaa) == GPIO.HIGH:
                GPIO.output(Paa_In, GPIO.LOW)
        if pressed==1:
            Errproc.terminate()
            prebootproc.terminate()
            prebootproc = Process(target=preboot)
            prebootproc.start()
            Errproc=None
        if Errproc==None and pressed==0 and testsucsess==0:
            prebootproc.terminate()           
            if GPIO.input(pressure_cancel) == GPIO.LOW:
                global Pressurein
                global Pressureout
                testsucsess=0
                print('testing water input')
                GPIO.output(Water_In, GPIO.HIGH)
                sleep(2)
                if GPIO.input(pressure_cancel) == GPIO.HIGH:
                    print('pressure check canceled')
                    Pressurein=10000
                if GPIO.input(pressure_cancel) == GPIO.LOW:
                    checkpruessurecanceled()
                if Pressurein<Pressurinthresh:
                    ErrNmbr =2
                    prebootproc.terminate()
                    GPIO.output(Outputs, GPIO.LOW)
                    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                    GPIO.output(Errlight, GPIO.HIGH)
                    GPIO.output(Main_Drain, GPIO.HIGH)
                    Errproc = Process(target=Err,args=(2,))
                    Errproc.start()
                if ErrNmbr<1:
                    print('testing Air input')
                    GPIO.output(Water_In, GPIO.LOW)
                    sleep(0.1)
                    GPIO.output(Air_In, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(keg1, GPIO.LOW)
                    GPIO.output(keg2, GPIO.LOW)
                    sleep(2)
                    if GPIO.input(pressure_cancel) == GPIO.HIGH:
                        print('pressure check canceled')
                        Pressurein=10000
                    if GPIO.input(pressure_cancel) == GPIO.LOW:
                        checkpruessurecanceled()
                    if Pressurein<Pressurinthresh:
                        ErrNmbr =1
                        prebootproc.terminate()
                        GPIO.output(Outputs, GPIO.LOW)
                        GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                        GPIO.output(Errlight, GPIO.HIGH)
                        Errproc = Process(target=Err,args=(1,))
                        Errproc.start()
                if ErrNmbr<1:
                    print('test caustic input')
                    GPIO.output(keg1, GPIO.HIGH)
                    GPIO.output(keg2, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(Air_In, GPIO.LOW)
                    sleep(0.2)
                    GPIO.output(Water_In, GPIO.HIGH)
                    sleep(0.5)
                    GPIO.output(Water_In, GPIO.LOW)
                    GPIO.output(Caustic_In, GPIO.HIGH)
                    GPIO.output(Pump, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(keg1, GPIO.LOW)
                    GPIO.output(keg2, GPIO.LOW)
                    sleep(2)
                    if GPIO.input(pressure_cancel) == GPIO.HIGH:
                        print('pressure check canceled')
                        Pressurein=10000
                    if GPIO.input(pressure_cancel) == GPIO.LOW:
                        checkpruessurecanceled()
                    if Pressurein<Pumppressurethresh:
                        ErrNmbr =3
                        prebootproc.terminate()
                        GPIO.output(Outputs, GPIO.LOW)
                        GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                        GPIO.output(Errlight, GPIO.HIGH)
                        Errproc = Process(target=Err,args=(3,))
                        Errproc.start()
                if ErrNmbr<1:
                    print('testing Paa input ')
                    GPIO.output(keg1, GPIO.HIGH)
                    GPIO.output(keg2, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(Caustic_In, GPIO.LOW)
                    GPIO.output(Pump, GPIO.LOW)
                    GPIO.output(Water_In, GPIO.HIGH)
                    sleep(0.5)
                    GPIO.output(Water_In,GPIO.LOW)
                    sleep(0.1)
                    GPIO.output(Paa_In, GPIO.HIGH)
                    GPIO.output(Pump, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(keg1, GPIO.LOW)
                    GPIO.output(keg2, GPIO.LOW)
                    sleep(2)
                    if GPIO.input(pressure_cancel) == GPIO.HIGH:
                        print('pressure check canceled')
                        Pressurein=10000
                    if GPIO.input(pressure_cancel) == GPIO.LOW:
                        checkpruessurecanceled()
                    if Pressurein<Pumppressurethresh:
                        ErrNmbr =7
                        prebootproc.terminate()
                        GPIO.output(Outputs, GPIO.LOW)
                        GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                        GPIO.output(Errlight, GPIO.HIGH)
                        Errproc = Process(target=Err,args=(7,))
                        Errproc.start()
                if ErrNmbr<1:
                    print('testing Co2 input')
                    GPIO.output(keg1, GPIO.HIGH)
                    GPIO.output(keg2, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(Paa_In, GPIO.LOW)
                    GPIO.output(Pump, GPIO.LOW)
                    sleep(0.1)
                    GPIO.output(Co2_In, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(keg1, GPIO.LOW)
                    GPIO.output(keg2, GPIO.LOW)
                    sleep(2)
                    if GPIO.input(pressure_cancel) == GPIO.HIGH:
                        print('pressure check canceled')
                        Pressurein=10000
                    if GPIO.input(pressure_cancel) == GPIO.LOW:
                        checkpruessurecanceled()
                    if Pressurein<Pressuroutthresh:
                        ErrNmbr =4
                        prebootproc.terminate()
                        GPIO.output(Outputs, GPIO.LOW)
                        GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
                        GPIO.output(Errlight, GPIO.HIGH)
                        Errproc = Process(target=Err,args=(4,))
                        Errproc.start()
                if ErrNmbr<1:
                    GPIO.output(Co2_In, GPIO.LOW)
                    GPIO.output(keg1, GPIO.HIGH)
                    GPIO.output(keg2, GPIO.HIGH)
                    GPIO.output(Water_In, GPIO.HIGH)
                    sleep(2)
                    GPIO.output(Water_In, GPIO.HIGH)
                    sleep(4)
                    GPIO.output(Water_In, GPIO.LOW)
                    GPIO.output(Air_In, GPIO.HIGH)
                    sleep(1)
                    GPIO.output(Air_In, GPIO.HIGH)
                    sleep(3)
                    GPIO.output(keg1, GPIO.LOW)
                    GPIO.output(keg2, GPIO.LOW)
                    GPIO.output(Air_In, GPIO.LOW)
                    GPIO.output(Main_Drain, GPIO.LOW)
                    GPIO.output(statuslights, GPIO.LOW)
                    testsucsess=1
                    x=0
            else:
                testsucsess=1
                x=0
        if testsucsess==1:
            while x<3:
                GPIO.output(statuslights, GPIO.HIGH)
                sleep(0.5)
                GPIO.output(statuslights, GPIO.LOW)
                sleep(0.5)
                x=x+1 
        print('boot cycle compleete')
        B=B+1
    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
    checkbtn()
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
