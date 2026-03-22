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
import adafruit_sgp30 as sgp
import math

active=True

# Setup system utilities
sysutil.setup()

# Timeout for the lights to switch off when there's no motion detected, in seconds
MOTION_TIMEOUT = const(5)
GAS_MEASURE_INTERVAL = const(1000) # gas measurement interval in ms
GAS_BASELINE_INTERVAL = const(600)

# Total width for LEDs using Pulse Width Modulation
PW_TOTAL = const(0.02)

# Total voltage across the Pico's 3V3 and Ground terminals
VS = 3.3


# Modified by the script. Kept here so as to be recalculated
# only when changed, rather than every cycle
lights_pulse_ontime = PW_TOTAL*0.5
lights_pulse_offtime = PW_TOTAL*0.5

alarm_timer = 0

# Inputs

ambient_light = ADC(28)
thermistor = ADC(26)

PIR = Pin(18, Pin.IN, Pin.PULL_DOWN)

gas_sda = Pin(10)
gas_scl = Pin(11)
i2c = I2C(1,sda=gas_sda, scl=gas_scl, freq=400000)
#i2c.init(I2C.MASTER, baudreate=100000)

gas_sensor = sgp.Adafruit_SGP30(i2c)


co2eq, tvoc = gas_sensor.iaq_measure()
print("CO2eq = %d ppm \t TVOC = %d ppb" % (co2eq, tvoc))

# Initialize gas sensor
# 0x2003 -> Init_air_quality
#gas_sensor.writeto(0x58, '\x20\x03')


# Outputs

heat_system = Pin(3, Pin.OUT)
light_system = Pin(6, Pin.OUT)
ventilation_system = Pin(9, Pin.OUT)

buzzer = Pin(16, Pin.OUT)





# Input data from the sensors
input_data = {
    "light":0,
    "temp":0,
    "occupancy":False
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






# Other parameters:
# Time of last motion detection (s)
last_motion_time = 0

# Time of last gas measurement (ms)
last_gas_time = 0

last_baseline_time = time()+60

alarm_timer = 0
alarm_tripped = False

# Whether or not a gas sensor measurement has been made after sending the measure command
measured_gas = False




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







def lights_pulse():
    global settings
    if(settings["lights"]==0 or settings["lights"]==2 and lights_pulse_ontime<=0.003):
        light_system.value(0)
        sleep(PW_TOTAL)
        return
    elif(settings["lights"]==1):
        light_system.value(1)
        sleep(PW_TOTAL)
        return
        
    #global lights_pulse_ontime
    #global lights_pulse_offtime
    light_system.value(1)
    sleep(lights_pulse_ontime)
    light_system.value(0)
    sleep(lights_pulse_offtime)



def run_alarm():
    global buzzer
    t = ticks_ms()
    if(t > alarm_timer):
        buzzer.toggle()
        alarm_timer = t+1000



# Reverse-engineered from the "official" driver script.
# Need to run the lights_pulse while waiting for the sensor
def measure_gas():
    global gas_sensor
    gas_sensor._i2c.writeto(gas_sensor._addr, bytes([0x20, 0x08]))
    t1 = ticks_ms()
    for _i in range(2):
        lights_pulse()
    
    # 2 * (SGP30_WORD_LEN+1)
    crc_result = bytearray(2*(2+1))
    gas_sensor._i2c.readfrom_into(gas_sensor._addr, crc_result)
    result = []
    for i in range(2):
        word = crc_result[3*i], crc_result[3*i+1]
        # Not going to bother checking checksums
        result.append(word[0] << 8 | word[1])
    return result


def calc_temp_from_voltage(v):
    # Other resistor in our voltage divider circuit is 10kΩ
    r = (10*v)/(VS-v)
    temp = round(1/(1/298+1/3960*math.log(r/10)) - 273, 1)
    print("Temperature: "+temp)


# Reads the data from the sensors and updates the input_data dictionary
# Todo: Secure value bounds when interpreting
def read_data():
    global lights_pulse_ontime
    global lights_pulse_offtime
    global gas_sensor
    global last_gas_time
    global measured_gas
    global last_baseline_time
    

    ambient_val = ambient_light.read_u16()
    if ambient_val>25000:
        pwr = min(1.0,(ambient_val-25000)/10000)
        lights_pulse_ontime = PW_TOTAL*pwr
        lights_pulse_offtime = PW_TOTAL*(1-pwr)
    else:
        lights_pulse_ontime=0
    
    
    if(time()>last_motion_time+MOTION_TIMEOUT):
        heat_system.value(0)
        input_data["occupancy"]=False

    if(ticks_ms()%1000==0):
        calc_temp_from_voltage(thermistor.read_u16())

    
    
    ventilation_system.value(settings["vent"])

    ticks = ticks_ms()
    if(ticks>last_gas_time+GAS_MEASURE_INTERVAL):
        last_gas_time = ticks
        co2eq, tvoc = measure_gas()#gas_sensor.iaq_measure()
        print("CO2eq = %d ppm \t TVOC = %d ppb" % (co2eq, tvoc))

        
       




    global input_data
    input_data["light"] = ambient_light.read_u16()
    input_data["temp"] = thermistor.read_u16()
        

    
    



# A function for handling the PIR sensor.
def pir_handler(pin):
    global heat_system
    global last_motion_time
    global settings
    global input_data
    sleep(0.1)
    if(!pin.value()):
        return

    if(settings["alarm"]>0):
        alarm_tripped=True
        sysutil.log("Motion alarm tripped!")
        return



    input_data["occupancy"]=True
    print("Motion detected")
    last_motion_time = time()
    #heat_system.value(1)
    

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




# Main settings (on-off-passive) to be moved to helper function
def set_settings(params,agent):
    param_values = ["Off","On","Passive"]
    changed=False
    if("heat_stats" in params):
        value = param_values.index(params["heat_stats"])
        if(value<0 || value>2):
            value=2
        if(value!=settings["heat"]):
            changed=True
            settings["heat"] = value
            sysutil.log("Heater set to "+param_values[value]+" by "+agent)
            print("Heater set to "+param_values[value]+" by "+agent)
    if("light_stats" in params):
        value = param_values.index(params["light_stats"])
        if(value<0 || value>2):
            value=2
        if(value!=settings["lights"]):
            changed=True
            settings["lights"] = value
            sysutil.log("Lights set to "+param_values[value]+" by "+agent)
            print("Lights set to "+param_values[value]+" by "+agent)
        if("Ventilation_stats" in params):
            value = param_values.index(params["Ventilation_stats"])
            if(value<0 || value>2):
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
    print(filename)
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
        response = wphandler.get_html(input_data, settings, login_state)
    else:
        response_code, content_type, response = wphandler.get_file(filename)
    
    if(filename=="login.html"):
        if(has_params):
        # To be moved to a separate function later
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

    # Every time the page is refreshed it will receive params.
    # Additionally, since it's using a form, the params remain in the url
    # so they get re-sent if the client refreshes the page.
    # To fix this, add some js in the main page html that sets the window href.
    # Maybe we can also put something there that auto-refreshes the page every 10 seconds or so?

set_default_vals()

# Set up handler for PIR sensor
PIR.irq(trigger=Pin.IRQ_RISING, handler=pir_handler)


# Main loop to handle the webpage, defined separately to be called by a separate thread.
# This is necessary because socket.accept() blocks the thread while waiting for a connection.
# Additionally, reading the gas sensor data blocks the thread for 12 ms, which interferes with
# the pulse-width modulation on the LEDs. So, we run the PWM LEDs on a separate thread also.
def machine_loop():
    global active
    global alarm_tripped
    while active:
        read_data()
        lights_pulse()
        if(alarm_tripped):
            run_alarm()
    
    
    print("Stopped machine loop")
        



# Need to have this on the main thread and the data collection on the second thread.
# Keep a global parameter indicating that the main thread is active and check it each time
# in the background thread. Otherwise, the threads won't stop correctly.
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
        



