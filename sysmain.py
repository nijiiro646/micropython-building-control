# ENGR 120 Design Project Main Script
# Team 3: Watt's Up
# by 虹色の魔女

from machine import *
import network as ntw
import socket as socks
from utime import sleep, time
import sysutil
import wphandler
import AuthHandler
import threading


active=True

# Setup system utilities
sysutil.setup()

# Timeout for the lights to switch off when there's no motion detected, in seconds
MOTION_TIMEOUT = 5

# Total width for LEDs using Pulse Width Modulation
PW_TOTAL = 0.02


# Modified by the script. Kept here so as to be recalculated
# only when changed, rather than every cycle
lights_pulse_ontime = PW_TOTAL*0.5
lights_pulse_offtime = PW_TOTAL*0.5

# Inputs

ambient_light = ADC(28)
thermistor = ADC(26)

PIR = Pin(18, Pin.IN, Pin.PULL_DOWN)

# gas_sda = Pin(10)
# gas_scl = Pin(11)
# gas_sensor = I2C(1,sda=gas_sda, scl=gas_scl, freq=400000)




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
    "alarm":False,
    "settemp":21
}





# Other parameters:
# Time of last motion detection
last_motion_time = 0




# Sets the default values for each output.
# Called when the system is started up or shut down
# Once the UI is properly implemented, this should set values based on stored settings.
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





# Reads the data from the sensors and updates the input_data dictionary
# Todo: Secure value bounds when interpreting
def read_data():
    global lights_pulse_ontime
    global lights_pulse_offtime
    #if(time()%5==0):
     #   print("Light sensor: "+str(ambient_light.read_u16()))
      #  print("Thermistor: "+str(thermistor.read_u16()))
    

    ambient_val = ambient_light.read_u16()
    if ambient_val>25000:
        pwr = min(1.0,(ambient_val-25000)/10000)
        lights_pulse_ontime = PW_TOTAL*pwr
        lights_pulse_offtime = PW_TOTAL*(1-pwr)
    else:
        lights_pulse_ontime=0
    
    
    
    if(time()>last_motion_time+MOTION_TIMEOUT):
        heat_system.value(0)



    global input_data
    input_data["light"] = ambient_light.read_u16()
    input_data["temp"] = thermistor.read_u16()
        


def lights_pulse():
    if(lights_pulse_ontime<=0):
        light_system.value(0)
        return
        
    #global lights_pulse_ontime
    #global lights_pulse_offtime
    light_system.value(1)
    sleep(lights_pulse_ontime)
    light_system.value(0)
    sleep(lights_pulse_offtime)
    
    



# A function for handling the PIR sensor.
def pir_handler(pin):
    global heat_system
    global last_motion_time
    sleep(0.1)
    if(pin.value()):
        print("Motion detected")
        last_motion_time = time()
        heat_system.value(1)
        

# Checks for a valid cookie in an http request (string)
# Returns true if there is a cookie and it contains a valid access token, otherwise false.
def check_cookie(request):
    cookie_index = request.find("we-agree-cookie")
    if(cookie_index<0):
        return False

    print("Got cookie!")
    cookiestr = request[cookie_index:]
    token_index = cookiestr.find("token=")
    if(token_index<0):
        print("[MENT] Invalid cookie: "+cookiestr)
        return False

    # 6 characters in "token=", then 24-character token
    token = cookiestr[token_index+6:token_index+6+24]
    #Testing
    print("Token: "+token)
    return AuthHandler.is_valid_token(token)


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
        login_state=check_cookie(rqstring)
        print("Login state: "+str(login_state))

        response_code = "HTTP/1.1 200 OK"
        content_type = "text/html"
        response = wphandler.get_html(input_data, settings)
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
def machine_loop():
    global active
    while active:
        read_data()
        lights_pulse()
    
    
    print("Stopped background loop")
        
        



# Need to have this on the main thread and the data collection on the second thread.
# Keep a global parameter indicating that the main thread is active and check it each time
# in the background thread. Otherwise, the threads won't stop correctly.
bg_thread = threading.Thread(target=machine_loop)
bg_thread.start()


# Main data collection & control loop
while True:
    try:
        main_loop()
        read_data()
        lights_pulse()

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
        sysutil.log("System closed due to an unhandled error in main loop")
        set_default_vals()
        active=False
        print("[ERROR] System closed due to an unhandled error:")
        raise e
        



