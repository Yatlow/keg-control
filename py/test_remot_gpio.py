import RPi.GPIO as GPIO
from multiprocessing import Manager, Process
import os
import signal
import time
from time import sleep
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
app = Flask(__name__)
CORS(app) 

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
Pressureinraw = AnalogIn(ads, ADS.P2)
Pressureoutraw = AnalogIn(ads, ADS.P3)
VLin= 0.4
VLout= 0.451

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


GPIO.setup(Outputs, GPIO.OUT)
GPIO.setup(Inputs, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.output(Outputs, GPIO.LOW)

def protectheat():
    if GPIO.input(Water_Level) == GPIO.LOW:
        print('heat on')
    else:
        print('Heat off')
    while True:
        if GPIO.input(Water_Level) == GPIO.LOW:
            GPIO.output(Heat, GPIO.HIGH)
        else:
            GPIO.output(Heat, GPIO.LOW)
           
def cunvertpressure():
    global Pressurein
    global Pressureout
    global Pressureinraw
    global Pressureoutraw
    global PressureguageC
    global VLin
    global VLout
    VLin= 0.4
    VLout= 0.451
    pressureinmed = PressureguageC*(Pressureinraw.voltage-0.4)/(4)
    pressureoutmed = PressureguageC*(Pressureoutraw.voltage-0.451)/(4)
    Pressurein =round(pressureinmed,2)
    Pressureout =round(pressureoutmed,2)
    print(Pressureinraw.voltage, Pressureoutraw.voltage)
    print('Pressure in:',Pressurein,'PSI, Pressure out:',Pressureout,'PSI')

def checkpruessurecanceled():
    global Pressurein
    global Pressureout
    i=0
    x=0
    y=0
    while i<10:
        if GPIO.input(pressure_cancel) == GPIO.HIGH:
            if y==0:
                x=1
                i=i+1
            if y==1:
                i=0
            y=0
        if GPIO.input(pressure_cancel) == GPIO.LOW:
            if x==0:
                y=1
                i=i+1
            if x==1:
                i=0
            x=0
    if x==1:
        print('pressure check canceled')
        Pressurein=10000
        Pressureout=1000
    if y==1:
        Pressurein=0
        Pressureout=0
        cunvertpressure()
             
def Err(ErrNmbr):
    x=0
    while True:
        if ErrNmbr == 1:
            print('Air input Err #1')
            GPIO.output(Air_In, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(1)
            GPIO.output(Air_In, GPIO.LOW)
            sleep(1)
        if ErrNmbr == 2:
            print('Water input Err #2')
            GPIO.output(Water_In, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(1)
            GPIO.output(Water_In, GPIO.LOW)
            sleep(1)
        if ErrNmbr == 3:
            print('Caustic input Err #3')
            GPIO.output(Caustic_In, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(0.5)
            GPIO.output(Caustic_In, GPIO.LOW)
            sleep(0.5)
        if ErrNmbr == 4:
            print('Co2 input Err #4')
            GPIO.output(Co2_In, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(1)
            GPIO.output(Co2_In, GPIO.LOW)
            sleep(1)
        if ErrNmbr == 5:
            print('Emergancy BTN Err #7')
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(1)
            GPIO.output(Errlight, GPIO.LOW)
        if ErrNmbr == 6:
            print('Timed Out building Pressure- pressure is',Pressureout,'PSI')
            GPIO.output(Errlight, GPIO.HIGH)
            GPIO.output(Co2_In, GPIO.HIGH)
            sleep(1)
            GPIO.output(Co2_In, GPIO.LOW)
        if ErrNmbr == 7:
            print('Paa input Err #5')
            GPIO.output(Paa_In, GPIO.HIGH)
            GPIO.output(Errlight, GPIO.HIGH)
            sleep(1)
            GPIO.output(Paa_In, GPIO.LOW)
            sleep(1)
            
def Pauseindicator():
    GPIO.output(Outputs, GPIO.LOW)
    GPIO.output(STBYlight, GPIO.HIGH)
    while True:
        GPIO.output(InProceslight, GPIO.HIGH)
        print('Pause Press green BTN to Resume')
        sleep(0.5)
        GPIO.output(InProceslight, GPIO.LOW)
        sleep(0.5)

def filltanks():
    while True:
        if GPIO.input(FillCaus) == GPIO.LOW:
            GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
            GPIO.output(Water_In, GPIO.HIGH)   
            GPIO.output(Caustic_In, GPIO.HIGH)
        if GPIO.input(FillPaa) == GPIO.LOW:
            GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
            GPIO.output(Water_In, GPIO.HIGH)   
            GPIO.output(Paa_In, GPIO.HIGH)
        if GPIO.input(FillCaus) == GPIO.HIGH and GPIO.input(FillPaa) == GPIO.HIGH:
            GPIO.output(Ground_Pneu_valves, GPIO.LOW)
            GPIO.output(Water_In, GPIO.LOW)
        if GPIO.input(FillCaus) == GPIO.HIGH:
            GPIO.output(Caustic_In, GPIO.LOW)
        if GPIO.input(FillPaa) == GPIO.HIGH:
            GPIO.output(Paa_In, GPIO.LOW)

def Stdby():
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

def AirPurge(Recure,purgetimeon,purgetimeoff):# - changeble vars
    print('Air purge: air in for',purgetimeon,'sec, keg empty for', purgetimeoff,'seconds, repeet', Recure,'times' )
    global ErrNmbr
    GPIO.output(Air_In, GPIO.HIGH)
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.LOW)
    t=0
    while t<300:
        sleep(0.01)
        t=t+1
    checkpruessurecanceled()
    if Pressurein<Pressurinthresh:
        ErrNmbr =1
        Err(1)
    x = 0
    while x <Recure:
        GPIO.output(Air_In, GPIO.HIGH)
        t=0
        while t< purgetimeon:
            sleep(0.01)
            t=t+0.01
        GPIO.output(Air_In, GPIO.LOW)
        t=0
        while t< purgetimeoff:
            sleep(0.01)
            t=t+0.01
        x = x+1
    x = 0
    GPIO.output(keg2, GPIO.HIGH)
    GPIO.output(keg1, GPIO.LOW)
    while x <Recure:
        GPIO.output(Air_In, GPIO.HIGH)
        t=0
        while t< purgetimeon:
            sleep(0.01)
            t=t+0.01
        GPIO.output(Air_In, GPIO.LOW)
        t=0
        while t< purgetimeoff:
            sleep(0.01)
            t=t+0.01
        x = x+1
    x = 0
    GPIO.output(keg1, GPIO.HIGH)    
    t=0
    while t< purgetimeon:
        sleep(0.01)
        t=t+0.01
    GPIO.output(Air_In, GPIO.LOW)
    t=0
    while t< purgetimeoff:
        sleep(0.01)
        t=t+0.01

def WaterSquirt():# - changeble vars
    print('rinsing with water')
    global Pressurein
    global ErrNmbr
    t=0
    while t<30:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.HIGH)
    while t<400: #initialflud- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.LOW)
    checkpruessurecanceled()
    if Pressurein<Pressurinthresh:
        ErrNmbr =2
        Err(2)
    i = 1
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.HIGH)
    while i < 6 : #recure med squirt- changeble vars
        GPIO.output(Water_In, GPIO.HIGH)
        t=0
        while t<40: #med squirt water on leangth- changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Water_In, GPIO.LOW)
        t=0
        while t<30: #med squirt water off leangth- changeble vars
            sleep(0.01)
            t=t+1
        i= i+1
    i = 1
    while i < 5 : #recure short squirt- changeble vars
        GPIO.output(Water_In, GPIO.HIGH)
        t=0
        while t<20: #short squirt water on leangth- changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Water_In, GPIO.LOW)
        t=0
        while t<15: #short squirt water off leangth- changeble vars
            sleep(0.01)
            t=t+1
        i= i+1
    i = 1
    while i < 5 :  #recure long squirt- changeble vars
        GPIO.output(Water_In, GPIO.HIGH)
        GPIO.output(Air_In, GPIO.HIGH)
        t=0
        while t<160: #long squirt water on leangth- changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Water_In, GPIO.LOW)
        GPIO.output(Air_In, GPIO.LOW)
        t=0
        while t<160: #long squirt water off leangth- changeble vars
            sleep(0.01)
            t=t+1
        i= i+1  
    GPIO.output(Water_In, GPIO.HIGH)
    t=0
    while t<200:
        sleep(0.01)
        t=t+1
    GPIO.output(Pump, GPIO.HIGH)
    t=0
    while t<1100: #squirt water with pump leangth- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(Pump, GPIO.LOW)
    t=0
    while t<200:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.LOW)

def PumpSquirt(Purge): # - changeble vars
    if Purge== 0:
        print('the Pump is squirting with Caustic & air')
    if Purge== 21:
        print('the Pump is squirting with Paa & co2')
    global ErrNmbr
    PaaPumpuRecure=15 #initial paa squirt recure - changeble vars
    PaaPumpOn=30 #initial paa squirt pump on - changeble vars
    PaaPumpOff=30 #initial paa squirt pump off - changeble vars
    CausticPumpuRecure=15 #initial Caustic squirt recure - changeble vars
    CausticPumpOn=30 #initial Caustic squirt pump on - changeble vars
    CausticPumpOff=30 #initial Caustic squirt pump off - changeble vars
    if Purge==Co2_In:
        pumpRecure=PaaPumpuRecure
        pumpOn=PaaPumpOn
        pumpOff=PaaPumpOff
    if Purge==Air_In:
        pumpRecure=CausticPumpuRecure
        pumpOn=CausticPumpOn
        pumpOff=CausticPumpOff
    i = 0
    while i < pumpRecure : 
        GPIO.output(Pump, GPIO.HIGH)
        t=0
        while t<pumpOn:
            sleep(0.01)
            t=t+1                                                                   
        GPIO.output(Pump, GPIO.LOW)
        t=0
        while t<pumpOff:
            sleep(0.01)
            t=t+1
        i= i+1
    GPIO.output(Pump, GPIO.HIGH)
    i = 1
    withAir=7
    if Purge==Co2_In:#recure pump squirt with co2 - changeble vars
        rcurePumpAndAirSquirt=withCo2
    if Purge==Air_In: #recure pump squirt with Air - changeble vars
        rcurePumpAndAirSquirt=withAir
    while i < rcurePumpAndAirSquirt : 
        GPIO.output(Pump, GPIO.HIGH)
        GPIO.output(Purge, GPIO.HIGH)
        if Purge==Co2_In:
            GPIO.output(Purge, GPIO.HIGH)
            t=0
            while t<120: #CO2 and pump intervale - changeble vars
                sleep(0.01)
                t=t+1
        if Purge==Air_In:# caustic purge pump and air - changeble vars
            t=0
            while t<20: #air and pump intervale- changeble vars
                sleep(0.01)
                t=t+1
            GPIO.output(Purge, GPIO.LOW)
            sleep(1)
        GPIO.output(Pump, GPIO.LOW)
        GPIO.output(Purge, GPIO.LOW)
        t=0
        while t<120:
            sleep(0.01)
            t=t+1
        i= i+1
    i = 1
    if Purge==Air_In: # caustic pump squirt post air - changeble vars
        t=0
        while t<40:
            sleep(0.01)
            t=t+1
    while i < 7 : #recure- changeble vars
        GPIO.output(Pump, GPIO.HIGH)
        t=0
        while t<120: #pump on - changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Pump, GPIO.LOW)
        t=0
        while t<120: #pump off- changeble vars
            sleep(0.01)
            t=t+1
        i= i+1
    GPIO.output(Pump, GPIO.LOW)

def causticrinse():# - changeble vars
    global ErrNmbr
    GPIO.output(keg2, GPIO.HIGH)
    GPIO.output(keg1, GPIO.HIGH)
    t=0
    while t<50:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.HIGH)
    t=0
    while t<20:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.LOW)
    t=0
    while t<1:
        sleep(0.01)
        t=t+1
    GPIO.output(Pump, GPIO.HIGH)
    GPIO.output(Caustic_In, GPIO.HIGH)
    GPIO.output(Main_Drain, GPIO.LOW)
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.LOW)
    GPIO.output(Caustic_Out, GPIO.HIGH)
    t=0
    while t<200: 
        sleep(0.01)
        t=t+1
    t=0
    checkpruessurecanceled()
    while t<200:
        sleep(0.01)
        t=t+1
    if Pressurein<Pumppressurethresh:
        ErrNmbr =3
        Err(3)
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.HIGH)
    t=0
    while t<500: #initial caustic flud both kegs- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.LOW)
    t=0
    while t<1500: #caustic rinse keg1- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.HIGH)
    t=0
    while t<1500: #caustic rinse keg2- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(Caustic_Out, GPIO.LOW)
    t=0
    while t<1000:  #pressurize caustic in keg with closed outpots- changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(Caustic_Out, GPIO.HIGH)
    PumpSquirt(Air_In) #caustic pump squirt
    GPIO.output(Water_In, GPIO.HIGH)
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.HIGH)
    t=0
    while t<50:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.LOW)
    t=0
    while t<1:
        sleep(0.01)
        t=t+1
    GPIO.output(Pump, GPIO.HIGH)
    GPIO.output(Caustic_In, GPIO.HIGH)
    GPIO.output(Caustic_Out, GPIO.HIGH)
    t=0
    while t<1500: #second caustic flud both kegs - changeble vars
        sleep(0.01)
        t=t+1
    t=0
    GPIO.output(Caustic_Out, GPIO.LOW)
    GPIO.output(Pump, GPIO.LOW)
    while t<2000:
        sleep(0.01)
        t=t+1
    GPIO.output(Caustic_In, GPIO.LOW)
    GPIO.output(Caustic_Out, GPIO.HIGH)
    AirPurge(3,0.75,1)# caustic air purge- changeble vars
    GPIO.output(Caustic_Out, GPIO.LOW)

def paasanitize():
    global ErrNmbr
    GPIO.output(Water_In, GPIO.HIGH)
    t=0
    while t<20:
        sleep(0.01)
        t=t+1
    GPIO.output(Water_In, GPIO.LOW)
    t=0
    while t<7:
        sleep(0.01)
        t=t+1
    GPIO.output(Paa_In, GPIO.HIGH)
    GPIO.output(Pump, GPIO.HIGH)
    t=0
    GPIO.output(Main_Drain, GPIO.LOW)
    GPIO.output(keg1, GPIO.LOW)
    while t<400:
        sleep(0.01)
        t=t+1
    checkpruessurecanceled()
    if Pressurein<Pumppressurethresh:
        ErrNmbr =7
        Err(7)
    GPIO.output(Main_Drain, GPIO.LOW)
    GPIO.output(Paa_Out, GPIO.HIGH)
    GPIO.output(keg2, GPIO.LOW)
    GPIO.output(keg1, GPIO.HIGH)
    t=0
    while t<3500: #sanitize keg 1 - changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.HIGH)
    t=0
    while t<3500:#sanitize keg 2  - changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(Paa_Out, GPIO.LOW)
    t=0
    while t<1000:#sanitize both kegs  - changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(Paa_Out, GPIO.HIGH)
    PumpSquirt(Co2_In) #paa pump squirt  - changeble vars
    t=0
    while t<1000:#post squirt sanitize both kegs - changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(Pump, GPIO.LOW) 

def Co2purge():
    global ErrNmbr
    GPIO.output(Paa_In, GPIO.LOW)
    GPIO.output(Co2_In, GPIO.HIGH)
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.HIGH)
    r=0
    while r<100:
        sleep(0.01)
        r=r+1
    GPIO.output(keg1, GPIO.LOW)
    r=0
    while r<200:
        sleep(0.01)
        r=r+1
    checkpruessurecanceled()
    if Pressurein<Pressurinthresh:
        ErrNmbr =4
        Err(4)
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.LOW)
    c=0
    while c <9:#co2 purge keg1- recure - changeble vars
        GPIO.output(Co2_In, GPIO.HIGH)
        t=0
        while t<70:#co2 purge keg1- gas open - changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Co2_In, GPIO.LOW)
        t=0
        while t<240: #co2 purge keg1- gas closed - changeble vars
            sleep(0.01)
            t=t+1
        c= c+1
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.HIGH)
    c = 0
    while c<9:#co2 purge keg2- recure - changeble vars
        GPIO.output(Co2_In, GPIO.HIGH)
        t=0
        while t<70: #co2 purge keg2- gas open - changeble vars
            sleep(0.01)
            t=t+1
        GPIO.output(Co2_In, GPIO.LOW)
        t=0
        while t<240: #co2 purge keg2- gas closed - changeble vars
            sleep(0.01)
            t=t+1
        c= c+1
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(Co2_In, GPIO.HIGH)
    t=0
    while t<500: #co2 purge both kegs- gas open - changeble vars
        sleep(0.01)
        t=t+1
    GPIO.output(Co2_In, GPIO.LOW)
    t=0
    while t<500: #let paa come out after closing co2
        sleep(0.01)
        t=t+1
    GPIO.output(Paa_Out, GPIO.LOW)

def kegprssurize():
    global Pressurein
    global Pressureout
    global ErrNmbr
    GPIO.output(Co2_In, GPIO.HIGH)
    GPIO.output(keg1, GPIO.LOW)
    GPIO.output(keg2, GPIO.LOW)
    t=0
    while t<200:
        sleep(0.01)
        t=t+1
    checkpruessurecanceled()
    if Pressurein<(Pressuroutthresh+1):
        ErrNmbr =4
        Err(4)
    TK= time.time()
    TO= time.time()
    TT=TO-TK
    GPIO.output(keg1, GPIO.HIGH)
    GPIO.output(keg2, GPIO.HIGH)
    checkpruessurecanceled()
    while Pressureout<kegpresuuredest:
        sleep(0.2)
        checkpruessurecanceled()
        TO= time.time()
        TT=TO-TK
        if TT>12: #timed out to reach keg pressure destination- changeble vars
            print('Timed Out building Pressure- pressure is',Pressureout,'PSI, building pressure for 15 s')  #edit with var - changeble vars
            sleep(15)#adiitional pressure after time out - changeble vars
            Pressureout=Pressuroutthresh+1
    if TT<7 and GPIO.input(pressure_cancel) == GPIO.LOW:
        TS=7-TT
        TTT=round(TT,1)
        TSS=round(TS,1)
        print('it took',TTT,'seconds to get to', Pressuroutthresh, 'PSI, pressurizing for',TSS,'more seconds')
        sleep(TS)
    if GPIO.input(pressure_cancel) == GPIO.HIGH:
        t=0
        print('pressure detect is off, building pressure for 35 s') #edit with var - changeble vars
        while t<3500: #pressurizing time if pressure sensors are off- changeble vars
            sleep(0.01)
            t=t+1
    GPIO.output(Co2_In, GPIO.LOW)
    
def Cycle(shared_values):
    print('start Cycle')
#start cycle and purge until btn is up
    global ErrNmbr
    global Pressurein
    global Pressureout
    GPIO.output(Outputs, GPIO.LOW)
    # GPIO.output(InProceslight, GPIO.HIGH)
    # GPIO.output(Main_Drain, GPIO.HIGH)
    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
    while True:
        FirstAirPurgeRecure, FirstAirPurgeTon, FirstAirPurgeToff = shared_values[0], shared_values[1], shared_values[2]
        suming=FirstAirPurgeRecure+FirstAirPurgeTon+FirstAirPurgeToff
        if suming<100:
           GPIO.output(STBYlight, GPIO.HIGH) 
        if suming>100 and suming < 1000:
           GPIO.output(InProceslight, GPIO.HIGH) 
        if suming<1000:
           GPIO.output(Errlight, GPIO.HIGH)
        print(shared_values,suming)
        sleep(3)


def ShortCycle():
    print('start Short Cycle')
#start cycle and purge until btn is up
    global ErrNmbr
    global Pressurein
    global Pressureout
    GPIO.output(Outputs, GPIO.LOW)
    GPIO.output(InProceslight, GPIO.HIGH)
    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
#paa sanitize
    print('Paa sanitation')
    paasanitize()
    print('Purging keg with Co2')
#purge With CO2
    Co2purge()
    print('Building Pressure in keg to',Pressuroutthresh,'PSI')
#build pressure
    kegprssurize()
    print('sucsses!')
    sleep(0.5)
    Stdby()
    
def purgecycle():
    global Pressurein
    global Pressureout
    print('start keg emptying cycle')
    GPIO.output(Outputs, GPIO.LOW)
    GPIO.output(Ground_Pneu_valves, GPIO.HIGH)
    GPIO.output(Main_Drain, GPIO.HIGH)
    GPIO.output(InProceslight, GPIO.HIGH)
    AirPurge(15,1,1)
    ('sucsses')
    Stdby()
 
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
       
    proc = Process(target=Cycle)
    procind=1

def boot(shared_values):
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
    main()

@app.route('/')
def index():
    return "Keg Control API is running!"


@app.route('/update', methods=['POST'])
def update_variable():
    global FromWebVars
    try:
        # Try to convert inputs to int, set to 0 if None or invalid
        if 'index0' in request.form and request.form['index0']:
            FromWebVars[0] = int(request.form['index0'])
        if 'index1' in request.form and request.form['index1']:
            FromWebVars[1] = int(request.form['index1'])
        if 'index2' in request.form and request.form['index2']:
            FromWebVars[2] = int(request.form['index2'])

        print(f"Updated FromWebVars: {FromWebVars}")  # Debug print
        return jsonify(success=True, new_values=FromWebVars)
    except ValueError as e:
        print(f"Value error: {str(e)}")  # Log the value error
        return jsonify(success=False, error="Invalid input; please provide numbers."), 400
    except Exception as e:
        print(f"Error updating FromWebVars: {str(e)}")  # Log the error
        return jsonify(success=False, error=str(e)), 500
        
        
@app.route('/current_values', methods=['GET'])
def current_values():
    return jsonify(current_values=FromWebVars)  # Return the list of current values

@app.errorhandler(500)
def internal_error(error):
    return f"Internal Server Error: {str(error)}", 500

# def updateVal():
#     global FromWebVars  # Access the global FromWebVars
#     global kegpresuuredest
#     global current_values
#     last_values = FromWebVars.copy()  # Store the initial values
#     while True:
#         current_values = FromWebVars.copy()  # Get the current values
if __name__ == '__main__':
    manager = Manager()
    shared_values = manager.list([0, 0, 0])  # Placeholder for three values
    boot(shared_values)
    # if not thread_running:  # Check if the thread is not already running
    #     washer_thread = Thread(target=updateVal)
    #     washer_thread.start()
    #     thread_running = True  # Set the flag to indicate the thread is running
    app.run(host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'), debug=False)   

