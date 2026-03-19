# sysutil.py
# ENGR 120 Design Project - System Utilities
# by 虹色の魔女


import utime

global logfile


# Initial setup function
# Opens the logfile.
def setup():
    global logfile
    logfile = open("system_log.txt","a")
    

# Returns the current timestamp as a string, in the format
# YYYY/MM/DD@HH:MM:SS
def get_timestamp():
    current_time = utime.localtime(utime.time())
    return f"{current_time[0]:04d}/{current_time[1]:02d}/{current_time[2]:02d}@{current_time[3]:02d}:{current_time[4]:02d}:{current_time[5]:02d}"


# Writes the given infostr string to the logfile
def log(infostr):
    global logfile
    logfile.write(get_timestamp()+"\t"+infostr+"\n")
    logfile.flush()


def parse_dictval(val):
    if(val.isdigit()):
        return int(val)
    elif(val=="True"):
        return True
    elif(val=="False"):
        return False
    else:
        raise ValueError


# Decodes http %-escapes in given string s
# Returns the decoded string
def decode_string(s):
    r = s.replace("%26","&")
    r = r.replace("%20"," ")
    r = r.replace("%21","!")
    r = r.replace("%22",'"')
    r = r.replace("%A3","£")
    r = r.replace("%23","#")
    r = r.replace("%24","$")
    r = r.replace("%26","&")
    r = r.replace("%27","'")
    r = r.replace("%5E","^")
    r = r.replace("%2B","+")
    r = r.replace("%2C",",")
    r = r.replace("%3F","?")
    r = r.replace("%40","@")
    r = r.replace("%28","(")
    r = r.replace("%29",")")
    r = r.replace("%5B","[")
    r = r.replace("%5D","]")
    r = r.replace("%5C","\\")
    r = r.replace("%3B",";")
    r = r.replace("%2F","/")
    r = r.replace("%3C","<")
    r = r.replace("%3D","=")
    r = r.replace("%3E",">")
    r = r.replace("%3F","?")
    
    
    r = r.replace("%25","%")
    
    
    return r


