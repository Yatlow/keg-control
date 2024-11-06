# keg-control
Keg washing system

The Python code runs on a Raspberry PI
It runs different cycles for keg cleaning/sanitizing and other cycles
The Hardware is GPIO-trigged and includes pumps, pneumatic solenoid valves, signal lights, etc..

The Python code also functions as a FLASK server that communicates with a local database for different variables (e.g how long to run each process within the cycle, how many times to repeat)

The Frontend web page sends variables to FLASK server to change in real time and save to database
