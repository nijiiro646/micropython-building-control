# AuthHandler.py
# ENGR 120 Design Project - User Manager
# Command-line interface for managing user authentication
# by 虹色の魔女


import AuthHandler
from string import ascii_letters, digits, punctuation, printable


# Prompts for username and password and prints the authentication status
def login_check():
	username = input("Enter username: ")
	password = input("Enter password: ")
	if(AuthHandler.auth_check(username,password)):
		print("Authentication OK\n")
	else:
		print("Authentication failed\n")
	mainmenu()


# Validates username.
# Returns false if the username already exists, or if it contains disallowed characters.
def username_check(username):
	if(AuthHandler.user_exists(username)):
		print("User already exists. Please enter a different username.")
		return False


	for c in username:
		if(not (c in ascii_letters) and not (c in digits) and not (c=="_" or c==".")):
			print("Disallowed character found in username. Please use only letters, numbers, underscore, and period.")
			return False


	return True


# Validates password.
# Returns false if the password contains disallowed characters, otherwise true.
def password_check(pw):

	for c in pw:
		if(not (c in printable)):
			print("Disallowed character found in password. Please use ASCII characters only.")
			return False

	return True


# Prompts to enter username and password, validates them, and adds them to the stored credentials.
def add_new():
	username = input("Enter username: ")
	
	while(not username_check(username)):
		print("\n")
		username = input("Enter username: ")
	
	pw = input("Enter password: ")
	while(not password_check(pw)):
		print("\n")
		pw = input("Enter password: ")

	AuthHandler.set_user(username,pw)
	print("User successfully registered.\n")
	mainmenu()


# Prompts the user to enter a valid username, and then a new password for that user.
def change_pw():
	username = input("Enter username: ")
	while (not AuthHandler.user_exists(username)):
		print("User does not exist. Try again.\n")
		username = input("Enter username: ")

	pw = input("Enter new password: ")
	while(not password_check(pw)):
		print("\n")
		pw = input("Enter new password: ")

	AuthHandler.set_user(username,pw)
	print("Password updated.\n")
	mainmenu()


# Prompts the user to enter a username, and removes the credentials for that user (with confirmation)
def remove():
	username = input("Enter username: ")
	while (not AuthHandler.user_exists(username)):
		print("User does not exist. Try again.\n")
		username = input("Enter username: ")
	print("Are you sure to remove this user? [y/N]")
	r = input("> ")
	if(r!="y" and r!="Y"):
		print("Operation canceled.\n")
	else:
		AuthHandler.remove_user(username)
		print("User removed.\n")
	mainmenu()






# Prints the main menu and waits for input
def mainmenu():
	print("=== Main Menu ===\nSelect operation:\n1 - Add new user\n2 - Change password\n3 - Remove user\n4 - Exit\n");

	r = input("> ")

	if(r=="1"):
		add_new()
	elif(r=="2"):
		change_pw()
	elif(r=="3"):
		remove()
	elif(r=="4"):
		import sys
		sys.exit()
	# For testing purposes. Should be removed in final build.
	elif(r=="5"):
		login_check()
	else:
		print("Unrecognized input: "+r+"\n")
		mainmenu()




print("= User Credential Configurator =\n\n")
mainmenu()



