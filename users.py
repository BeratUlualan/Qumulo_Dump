import sys
from os import path
import logging
import json
from qumulo.rest_client import RestClient
import qumulo.lib.auth
import qumulo.lib.request
import qumulo.rest
import time
import jmespath
import sys, getopt
from getpass import getpass

def main(argv):
    # Logging Details
    logging.basicConfig(filename='qumulo_sync.log', level=logging.INFO,
        format='%(asctime)s,%(levelname)s,%(message)s')

    # Argument Parameters Details 
    err_msg = '''
usage: qumulo_sync.py [-a|--auto_approve] [-d|--dump] [-s|--set] 

Dump or Set SMB settings and shares. 

optional arguments:
-h, --help          Show this help message and exit
-a, --auto_approve  Sync all existing settings without confirmation. If you want to use it, please put it before other arguments.
-d, --dump          Dump SMB settings and shares.
-s, --set           Sent SMB settings and shares.
    '''
    try:
        if len(sys.argv) > 1:
            opts, args = getopt.getopt(argv,'hads :',["help","auto_approve","dump","set"])
            approve = False
        else:
            print(err_msg)
            sys.exit(2)

    except getopt.GetoptError:
      print (err_msg)
      sys.exit(2)
    
    for opt, arg in opts:
        if opt in ("-h","--help"):
            print (err_msg)
            sys.exit()
        elif opt in ("-d","--dump"):
            prc = login('primary')
            print ()
            users_list(prc)
        elif opt in ("-a","--auto_approve"):
            approve = True
        else:            
            if opt in ("-s","--set"):
                src = login('secondary')
                print ()
                users_define(src, approve)

def login(cluster):
    # Cluster address is one of the IP addresses of the cluster nodes that is required for the API connectivity
    # Default port number is 8000
    # There is a user requirement which must have NFS_EXPORT_READ, NFS_EXPORT_WRITE, QUOTA_READ, QUOTA_WRITE, SMB_SHARE_READ, SMB_SHARE_WRITE privileges. 
    # If you don't want to use "admin" user, please define above privileges for the user that you want to use.  
    # You can define this parameters as shown in the documentation or you can enter manually when you run the script. 

    cluster_address = ""
    port = ""
    username = ""
    password = ""

    if path.exists('credentials.json') == True:
        json_file = open('credentials.json','r')
        json_data = json_file.read()
        json_object = json.loads(json_data)

        cluster_address = json_object[cluster]['cluster_address']
        if cluster_address == "":
            cluster_address = input(cluster.capitalize() + " Cluster Address: ")

        port = json_object[cluster]['port']
        if port == "":
            port = input(cluster.capitalize() +  " Port: ")

        username = json_object[cluster]['username']
        if username == "":
            username = input(cluster.capitalize() +  " Username: ")

        password = json_object[cluster]['password']
        if password == "":
            password = getpass(cluster.capitalize() +  " Password: ")

    else:
        print()
        cluster_address = input(cluster.capitalize() + " Cluster address: ")
        port = input(cluster.capitalize() + " Port: ")
        username = input(cluster.capitalize() + " Username: ")
        password = getpass(cluster.capitalize() + "Password: ")
    
    logging.info('Login credentials defined for {} - {}'.format(cluster_address, username))

    try:
        rc = RestClient(cluster_address, port)
        rc.login(username, password)
        print ("Connection established with " + cluster_address)
        logging.info('Connection established with {}'.format(cluster_address))

        return (rc)

    except Exception as excpt:
        logging.error('Connection issue with {}'.format(cluster_address))
        print("Error connecting to %s cluster: %s" % cluster_address, excpt)
        print(__doc__)
        sys.exit(1)

def users_list(rc):
    users = rc.users.list_users()
    users_json_file = open('users.json', 'w')
    json.dump(users, users_json_file, indent=4)
    users_json_file.close()
      

def users_define(rc, approve):
    approve = False
    users_json_file = open('users.json','r')
    users_json_data = users_json_file.read()
    users_json_object = json.loads(users_json_data)
    
    users = users_json_object
    for user in users:
        
        primary_group = user['primary_group']
        if user['uid'] != "":
            uid = user['uid']
        else:
            uid = None
        home_directory = user['home_directory']
        password = "Admin123"
        name = user['name']

        existing_users = rc.users.list_users() 
        existing_user_check = jmespath.search(f"[?uid == '{uid}' || name == '{name}'].[uid, name]", existing_users)
        if existing_user_check != [] :
            print (name + " is already defined... ")
            logging.info('{} user is already defined.'.format(name))
            if approve == False:
                update_confirm = input("Do you want to update "+ name +" user?: [Y/n]")
            else:
                update_confirm = "Y"
                print(name + " is being updated...")
                logging.info('User {} was updated succesfully.'.format(name))
        
            if update_confirm == "y" or update_confirm == "Y" or update_confirm == "Yes" or update_confirm == "yes":
                #password = getpass("Enter user password for "+name+" : ")
                checked_name = jmespath.search(f"[?uid == '{uid}'].[name]", existing_users)
                checked_uid = jmespath.search(f"[?name == '{name}'].[uid]", existing_users)
                if name == checked_name and uid == checked_uid:
                    user_id = jmespath.search(f"[?uid == '{uid}'].[id]", existing_users)
                    rc.users.modify_user(user_id, name, primary_group, uid, home_directory=home_directory, password=password)
                else:
                    continue
            else:
                print(name + " wasn't updated...")
            logging.info('User {} wasn\'t updated.'.format(name))
        else:
            if approve == False:
                create_confirm = input("Do you want to create "+ name +" user?: [Y/n]")
            else:
                create_confirm = "Y"
                print(name+ " is being created...")
        
            if create_confirm == "y" or create_confirm == "Y" or create_confirm == "Yes" or create_confirm == "yes": 
                #password = getpass("Enter user password for "+name+" : ")
                rc.users.add_user(name, primary_group, password, uid=None, home_directory=None) 
                print("A new user was created (" + name +")")
                logging.info('A new user was created ({})'.format(name))
        print ()

if __name__ == '__main__':
    main(sys.argv[1:])

