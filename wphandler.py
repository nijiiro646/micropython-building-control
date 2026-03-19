# ENGR 120 Design Project - Webpage & HTML Handler
# by 虹色の魔女


import os


idstrings = {0:"off",1:"on",2:"passive"}

# Preload base page source
pagesauce_base = open("mainpage.html","rt").read()


# Gets the specified file
# Returns response code and content-type as strings, and data as either string or bytes (depending on file type)
# If the requested file does not exist, it returns the 404 not found page.
# If the requested file is a system internal file, it returns the 403 Forbidden page.
def get_file(href):
    if(href==""):
        return "HTTP/1.1 200 OK", "text/html", get_html()
    print("Get file: "+href)
    if(not os.path.isfile(href) or not ('.' in href) or len(href.split("."))<2):
        return "HTTP/1.1 404 Not Found", "text/html", open("pnf.html","rt").read()

    ext = href.split(".")[1]
    if(ext=="py" or ext=="txt"):
        return "HTTP/1.1 403 Forbidden", "text/html", open("forbidden.html","rt").read()

    # Don't want to keep this in memory any longer than necessary, Pico has only 200kB of RAM.
    if(ext=="webp"):
        return "HTTP/1.1 200 OK", "image/webp", open(href,"rb").read()
    else:
        return "HTTP/1.1 200 OK", "text/html", open(href,"rt").read()


def get_element_id(html_line):
    if(not "id" in html_line):
        return ""
    idindex = html_line.find("id=")+4
    end_index = html_line[idindex:].find('"')
    return html_line[idindex:end_index+idindex]


# Returns the html for the main page.
# Parameters: data - dictionary of measured data from the microcontroller
# settings - dictionary of current settings for the system
# login_state - boolean indicating whether the user is logged in with an admin account
# Returns the html for the main page.
# Parameters: data - dictionary of measured data from the microcontroller
# settings - dictionary of current settings for the system
# login_state - boolean indicating whether the user is logged in with an admin account
def get_html(data, settings, login_state):
    global pagesauce_base
    result = pagesauce_base

    checked_inputs = ["light_"+idstrings[settings["lights"]],
        "heat_"+idstrings[settings["heat"]],
        "alarm_"+("on" if settings["alarm"] else "off")]#,
        #"vent_"+idstrings[settings["vent"]]]

    # Here we can replace keystrings in the base html with a passed parameter dict
    if(login_state):
        result = result.replace(">Login<",">Logout<")
        result = result.replace("/login.html","/logoutredirect.html")
        result = result.replace(" disabled","") # Should replace all instances

    result = result.replace("%TEMP%",str(settings["settemp"]))

    res_lines = result.split("\n")
    result = ""
    for line in res_lines:
        if(not '"radio"' in line):
            result = result+line+"\n"
            continue

        input_id = get_element_id(line)
        if(input_id in checked_inputs):
            line = line.replace(">"," checked>")
        result = result+line+"\n"

    
    return result


# Returns a dictionary of parameter values from the response
# Extracts parameters from an http response and returns them as a dictionary.
def parse_response(response_text):
    data_dict = {}
    # We'll need to put in checks everywhere in case it's not the right kind of response
    start_index = response_text.find('?')+1
    end_index = response_text.find(' HTTP/')
    if(start_index<0 or end_index<0):
        return data_dict
    
    params = response_text[start_index:end_index].split("&")
    
    for param in params:
        data=param.split("=")
        if(len(data)!=2):
            continue
        data_dict[data[0]] = data[1]
    
    return data_dict

