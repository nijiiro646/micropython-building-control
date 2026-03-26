# ENGR 120 Design Project Main Script
# Team 3: Watt's Up
# by 虹色の魔女

from machine import *
import network as ntw
import socket as socks
from utime import *
import sysutil
import wphandler
import AuthHandler
import threading
import os
import math

active=True

# Setup system utilities
sysutil.setup()

# Timeout for occupancy to be marked "off" after last motion detection, in seconds
MOTION_TIMEOUT = const(5)

 # gas measurement interval in ms
GAS_MEASURE_INTERVAL = const(1000)

#GAS_BASELINE_INTERVAL = const(600)

# temperature measurement interval in ms
TEMP_MEASURE_INTERVAL = const(200)

# ppm eCO2 threshold to turn on ventilation
# Based on our research, 1000 ppm is the upper limit for "good/well-ventilated" air quality
CO2_THRESHOLD = const(1000)

# Total width for LEDs using Pulse Width Modulation
PW_TOTAL = const(0.02)

# Total voltage across the Pico's 3V3 and Ground terminals
VS = const(3.3)






# Inputs
ambient_light = ADC(28)
thermistor = ADC(27)

PIR = Pin(18, Pin.IN, Pin.PULL_DOWN)

# Unfortunately, the gas sensor didn't work.
# So, a potentiometer will be used in its stead for demonstration purposes.
#gas_sda = Pin(10)
#gas_scl = Pin(11)
#i2c = I2C(1,sda=gas_sda, scl=gas_scl, freq=400000)
#gas_sensor = sgp.Adafruit_SGP30(i2c)

gas_adc = ADC(26)



# Outputs
heat_system = Pin(3, Pin.OUT)
light_system = Pin(6, Pin.OUT)
ventilation_system = Pin(9, Pin.OUT)
buzzer = Pin(16, Pin.OUT)






# Script variables
lights_pulse_ontime = PW_TOTAL*0.5
lights_pulse_offtime = PW_TOTAL*0.5

alarm_timer = 0

# Thermistor is averaged over 10 readings for stability
thermistor_vals = []

# Other parameters:
# Time of last motion detection (s)
last_motion_time = 0

# Time of last gas and temp measurements (ms)
last_gas_time = 0
last_temp_time = 0

alarm_timer = 0
alarm_tripped = False




# Input data from the sensors
input_data = {
    "light":0,
    "temp":0,
    "occupancy":False,
    "eco2":0
}

# Current settings, controlled by the web interface
settings = {
    "lights":1,
    "heat":0,
    "alarm":0,
    "vent":1,
    "settemp":21
}


# Load settings on init
if(os.path.isfile('settings.txt')):
    sfile = open('settings.txt')
    sdata = sfile.readlines()
    for line in sdata:
        if(not ":" in line):
            continue
        dvals = line.split(":")
        if(len(dvals)!=2 or not (dvals[0] in settings)):
            continue
        vstr = dvals[1]
        try:
            settings[dvals[0]] = sysutil.parse_dictval(dvals[1])
        except ValueError:
            print("[MENT] Server loading error: invalid settings value: "+dvals[1])
    sfile.close()









# Sets the default values for each output.
# Called when the system is started up or shut down
def set_default_vals():
    # The buzzer sounds when no voltage is supplied to its IO channel,
    # so the default (off) is when we do apply voltage.
    buzzer.value(1)
    heat_system.value(0)
    light_system.value(0)
    ventilation_system.value(0)






# Activate access point
# "I want to connect wirelessly, from my pico."
ap = ntw.WLAN(ntw.AP_IF)
ap.config(essid="Watt's Up", password="TryAg4in!")
ap.active(True)

# Gateway address (3rd element in tuple) must be 192.168.4.1
ap.ifconfig(('192.168.4.13', '255.255.255.0', '192.168.4.1', '0.0.0.0'))




# Wait for activation before proceeding
while not ap.active():
    pass

print("[INFO] Access point activated.")
print("[INFO] Homepage available at "+ap.ifconfig()[0])

# Put on the socks
s = socks.socket(socks.AF_INET, socks.SOCK_STREAM)

s.bind(('', 80))
s.listen(5) # maximum number of requests that can be queued

sysutil.log("System initialized. Access point started: "+str(ap.ifconfig()))





#============= Actuator control functions =============#


# Pulse the "light system" LED using pulse width modulation
def lights_pulse():
    global settings
    global input_data
    if(settings["lights"]==0 or settings["lights"]==2 and (lights_pulse_ontime<=0.003) or not input_data["occupancy"]):
        light_system.value(0)
        sleep(PW_TOTAL)
        return
    elif(settings["lights"]==1):
        light_system.value(1)
        sleep(PW_TOTAL)
        return
        

    light_system.value(1)
    sleep(lights_pulse_ontime)
    light_system.value(0)
    sleep(lights_pulse_offtime)



# Toggle the alarm buzzer every second
# Called from machine_loop() when the alarm is tripped
def run_alarm():
    global buzzer
    global alarm_timer
    t = ticks_ms()
    if(t > alarm_timer):
        buzzer.toggle()
        alarm_timer = t+1000



# Updates the state of the "heater" actuator based on settings and temperature
def update_heater_state():
    global input_data
    global settings
    global heat_system
    temp = input_data["temp"]
    heat_setting = settings["heat"]
    
    if(heat_setting==0):
        heat_system.value(0)
        return

    settemp = settings["settemp"] if (heat_setting==1 or (heat_setting==2 and input_data["occupancy"])) else 18
    if(heat_system.value()==1 and temp>settemp+1):
        heat_system.value(0)
    elif(heat_system.value()==0 and temp<settemp-1):
        heat_system.value(1)


# Updates the state of the "ventilation" actuator based on settings and eCO2 in the room
def update_vent_state():
    global input_data
    global settings
    global ventilation_system

    vent_setting = settings["vent"]


    if(vent_setting==0):
        ventilation_system.value(0)
    elif(vent_setting==1):
        ventilation_system.value(1)
    else:
        ventilation_system.value(input_data["eco2"]>CO2_THRESHOLD)




# Disused function for handling the broken gas sensor
# def measure_gas():
#     global gas_sensor
#     gas_sensor._i2c.writeto(gas_sensor._addr, bytes([0x20, 0x08]))
#     t1 = ticks_ms()
#     for _i in range(2):
#         lights_pulse()
#     
#     # 2 * (SGP30_WORD_LEN+1)
#     crc_result = bytearray(2*(2+1))
#     gas_sensor._i2c.readfrom_into(gas_sensor._addr, crc_result)
#     result = []
#     for i in range(2):
#         word = crc_result[3*i], crc_result[3*i+1]
#         # Not going to bother checking checksums
#         result.append(word[0] << 8 | word[1])
#     return result


# Calculates a temperature in degrees celcius from the adc thermistor reading adc_raw
# Result is rounded to the nearest whole number and stored to input_data["temp"]
def calc_temp_from_adc(adc_raw):
    global input_data
    v = adc_raw/65535*VS
    r = (10*v)/(VS-v)
    try:
        temp = round((1/(1/298+1/3960*math.log(v/(VS-v))) - 273)*0.95, 0)
    except ValueError:
        print("Temperature calculation error!")
        temp = 21
    print("Temperature: %.2f"%temp)
    input_data["temp"]=int(temp)





# Reads the data from the sensors and updates the input_data dictionary
def read_data():
    global lights_pulse_ontime
    global lights_pulse_offtime
    global last_gas_time
    global gas_adc
    global last_baseline_time
    global ventilation_system
    global last_temp_time
    
    
    
    if(time()>last_motion_time+MOTION_TIMEOUT):
        input_data["occupancy"]=False


    ambient_val = ambient_light.read_u16()
    input_data["light"]=ambient_val
    if ambient_val>25000:
        pwr = min(1.0,(ambient_val-25000)/10000)
        lights_pulse_ontime = PW_TOTAL*pwr
        lights_pulse_offtime = PW_TOTAL*(1-pwr)
    else:
        lights_pulse_ontime=0


    ticks = ticks_ms()
    
    # Average over 10 readings for stability
    if(ticks>last_temp_time+TEMP_MEASURE_INTERVAL):
        thermistor_vals.append(thermistor.read_u16())
        last_temp_time=ticks
    if(len(thermistor_vals)>=10):
        calc_temp_from_adc(sum(thermistor_vals)/len(thermistor_vals))
        update_heater_state()
        thermistor_vals.clear()
        
        
        


    
    if(ticks>last_gas_time+GAS_MEASURE_INTERVAL):
        last_gas_time = ticks
        raw_data = gas_adc.read_u16()
        eCO2 = 0.03493*raw_data+393.01
        input_data["eco2"] = eCO2
        #print("eCO2 (simulated): %i"%eCO2)
        update_vent_state()

    
    input_data["light"] = ambient_light.read_u16()
        



# A function for handling the PIR sensor.
# Called when the sensor detects motion.
# If the alarm is switched on, it sets the alarm as "tripped".
# Otherwise, it marks that the space is occupied.
def pir_handler(pin):
    global heat_system
    global last_motion_time
    global settings
    global input_data
    global alarm_tripped
    sleep(0.1)

    if(settings["alarm"]>0):
        alarm_tripped=True
        sysutil.log("Motion alarm tripped!")
        print("Motion alarm tripped!")
        return



    input_data["occupancy"]=True
    print("Motion detected")
    last_motion_time = time()
    #heat_system.value(1)
    


# Returns a dictionary of booleans indicating whether each actuator is "on" or "off".
# Used by the web ui to display active indicators.
def get_actuator_state():
    state={
        "heater":heat_system.value()==1,
        "lights":not (settings["lights"]==0 or settings["lights"]==2 and (lights_pulse_ontime<=0.003) or not input_data["occupancy"]),
        "vent": ventilation_system.value()==1,
        "alarm":alarm_tripped
        
        }
    return state



# ============= Wifi & web interface interaction handling ============= #

# Checks for a valid cookie in an http request (string)
# Returns true if there is a cookie and it contains a valid access token, otherwise false.
# Also returns the token as a string, or empty string if no valid token.
def check_cookie(request):
    cookie_index = request.find("we-agree-cookie")
    if(cookie_index<0):
        return False, ""

    print("Got cookie!")
    cookiestr = request[cookie_index:]
    token_index = cookiestr.find("token=")
    if(token_index<0):
        print("[MENT] Invalid cookie: "+cookiestr)
        return False, ""

    # 6 characters in "token=", then 24-character token
    token = cookiestr[token_index+6:token_index+6+24]
    return AuthHandler.is_valid_token(token), token




# Sets the settings as given in params (Dictionary)
# agent (String) is the username that updated the settings in the web ui.
# This information is also recorded in the system log.
def set_settings(params,agent):
    global alarm_tripped
    param_values = ["Off","On","Passive"]
    changed=False
    if("heat_stats" in params):
        value = param_values.index(params["heat_stats"])
        if(value<0 or value>2):
            value=2
        if(value!=settings["heat"]):
            changed=True
            settings["heat"] = value
            sysutil.log("Heater set to "+param_values[value]+" by "+agent)
            print("Heater set to "+param_values[value]+" by "+agent)
    if("light_stats" in params):
        value = param_values.index(params["light_stats"])
        if(value<0 or value>2):
            value=2
        if(value!=settings["lights"]):
            changed=True
            settings["lights"] = value
            sysutil.log("Lights set to "+param_values[value]+" by "+agent)
            print("Lights set to "+param_values[value]+" by "+agent)
        if("Ventilation_stats" in params):
            value = param_values.index(params["Ventilation_stats"])
            if(value<0 or value>2):
                value=2
            if(value!=settings["vent"]):
                changed=True
                settings["vent"] = value
                sysutil.log("Ventilation set to "+param_values[value]+" by "+agent)
                print("Ventilation set to "+param_values[value]+" by "+agent)
    if("alarm_stats" in params):
        value = param_values.index(params["alarm_stats"])
        if(value!=settings["alarm"]):
            changed=True
            settings["alarm"] = value
            if(value==0):
                alarm_tripped = False
                buzzer.value(1)
            sysutil.log("Alarm turned "+param_values[value]+" by "+agent)
            print("Alarm turned "+param_values[value]+" by "+agent)
    if("settemp" in params):
        if(params["settemp"].isdigit()):
            val = int(params["settemp"])
            if(val<18):
                val=18
            elif(val>25):
                val=25
            if(settings["settemp"]!=val):
                changed=True
                settings["settemp"] = val
                sysutil.log("Temperature set to "+str(val)+" by "+agent)
                print("Temperature set to "+str(val)+" by "+agent)

    if(changed):
        outfile = open("settings.txt","wt")
        for k in settings.keys():
            outfile.write(k+":"+str(settings[k])+"\n")
        outfile.close()



# Main run loop for the web interface
def main_loop():
    global input_data
    global settings
    conn, addr = s.accept()
   

   #Apparently this can throw errors.
    try:
        request = conn.recv(1024) 
    except Exception as e:
        print("[ERROR] Caught connection error: ")
        print(e)
        return
    
    rqstring = str(request)
    rqfile = rqstring.find("GET /")
    http_index = rqstring.find("HTTP")

    # In case of an invalid request, return a 400 Bad Reqeust error.
    # Currently the server does not support POST or other types of requests.
    if(rqfile<0 or http_index<0 or http_index <= rqfile):
        print("[MENT] Invalid request: "+rqstring)
        conn.send("HTTP/1.1 400 Bad Request\n")
        conn.send("Content-Type: text/html\n")
        conn.send("Connection: close\n\n")
        conn.sendall("400 Bad Request")
        return


    
    filename = rqstring[rqfile+5:http_index-1]
    #print(filename)
    has_params = "?" in filename
    if(has_params):
        filename = filename[:filename.find("?")]
    if(filename=="" or filename=="mainpage.html"):
        print("[INFO] Received inbound connection: "+str(addr))
        login_state, token = check_cookie(rqstring)
        print("Login state: "+str(login_state))
        if(has_params and login_state):
            try:
                username = AuthHandler.get_user_for_token(token)
            except KeyError:
                pass
            finally:
                params = wphandler.parse_response(rqstring)
                set_settings(params,username)

        response_code = "HTTP/1.1 200 OK"
        content_type = "text/html"
        response = wphandler.get_html(input_data, settings, get_actuator_state(), login_state)
    else:
        response_code, content_type, response = wphandler.get_file(filename)
    
    if(filename=="login.html"):
        if(has_params):
            params = wphandler.parse_response(rqstring)
            if("uname" in params and "psw" in params):
                username = sysutil.decode_string(params["uname"])
                password = sysutil.decode_string(params["psw"])
                if(AuthHandler.auth_check(username,password)):
                    # Send to LoginRedirect and give cookie
                    response = open("loginredirect.html","rt").read()
                    token = AuthHandler.generate_token_for_user(username)
                    response = response.replace("%COOKIE%","token="+token)
                else:
                    #response = open("login.html","rt").read()
                    response = response.replace("%MESSAGE%","Unable to login due to an 8th-layer error. Please try again.")
        
        response = response.replace("%MESSAGE%","")


    conn.send(response_code+"\n")
    conn.send("Content-Type: "+content_type+"\n")
    conn.send("Connection: close\n\n")
    conn.sendall(response)
    conn.close()


set_default_vals()

# Set up handler for PIR sensor
PIR.irq(trigger=Pin.IRQ_RISING, handler=pir_handler)


# Main loop to handle the machine interactions, defined separately to be called by a separate thread.
# This is necessary because socket.accept() blocks the thread while waiting for a connection.
def machine_loop():
    global active
    global alarm_tripped
    while active:
        read_data()
        lights_pulse()
        if(alarm_tripped):
            run_alarm()
    
    print("Stopped machine loop")
        

machine_thread = threading.Thread(target=machine_loop)
machine_thread.start()


# Main data collection & control loop
while True:
    try:
        main_loop()

    # Catch errors and set default values before closing.
    # Stopping the script in Thonny throws a KeyboardInterrupt
    except KeyboardInterrupt:
        sysutil.log("System shut down from main terminal.")
        set_default_vals()
        active=False
        import sys
        sys.exit()
    
    # For other errors, actually raise the error so it shows in the console
    except Exception as e:
        sysutil.log("System closed due to an unhandled error")
        set_default_vals()
        active=False
        print("[ERROR] System closed due to an unhandled error:")
        raise e
        



