import sys
from os import path
import logging
import json
from qumulo.rest_client import RestClient
import qumulo.lib.auth
import qumulo.lib.request
import qumulo.rest
import time
import sys, getopt
from getpass import getpass

def main(argv):
    # Logging Details
    logging.basicConfig(filename='operation.log', level=logging.DEBUG,
        format='%(asctime)s,%(levelname)s,%(message)s')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

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
            quota_list(prc)
        elif opt in ("-a","--auto_approve"):
            approve = True
        else:            
            if opt in ("-s","--set"):
                src = login('secondary')
                print ()
                quota_define(src, approve)

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
    
    logging.info(f'Login credentials defined for {cluster_address} - {username}')
    
    try:
        rc = RestClient(cluster_address, port)
        rc.login(username, password)
        logging.info(f'Connection established with {cluster_address}')
        
        return rc

    except Exception as excpt:
        logging.error(f'Connection issue with {cluster_address}')
        logging.error(f'Error: {excpt}')
        sys.exit(1)
        
def quota_list(rc):
    quotas=list(rc.quota.get_all_quotas_with_status(page_size=1000))[0]['quotas']
    quota_json_file = open('quotas.json', 'w')
    json.dump(quotas, quota_json_file, indent=4)
    quota_json_file.close()
    logging.info(f'Totally {len(quotas)} directory quotas were added into the JSON file')
    
def quota_define(rc, approve):
    approve = False
    quota_json_file = open('quotas.json','r')
    quota_json_data = quota_json_file.read()
    quota_json_object = json.loads(quota_json_data)
    
    quotas = quota_json_object
    for x in range(len(quotas)):
        fs_path = quotas[x]['path']
        limit = quotas[x]['limit']
        try: 
            file_id = rc.fs.get_file_attr(fs_path)['id']
            try:
                rc.quota.get_quota(file_id)
                print ("Quota for "+ fs_path + " is already defined... ")
                logging.info(f'{fs_path} quota is already defined.')
                if approve == False:
                    update_confirm = input("Do you want to update "+ fs_path +" directory quota?: [Y/n]")
                else:
                    update_confirm = "Y"
                    print("Directory quota for " + fs_path + " is being updated...")
                    logging.info(f'Directory quota for {fs_path} was updated succesfully.')
            
                if update_confirm in ["y","Y","Yes","yes"]:
                    rc.quota.update_quota(file_id, limit)
                else:
                    print("Directory quota for " + fs_path + " wasn't updated...")
                    logging.info(f'Directory quota for {fs_path} wasn\'t updated.')
            except: 
                    if approve == False:
                        create_confirm = input("Do you want to create "+ fs_path +" directory quota?: [Y/n]")
                    else:
                        create_confirm = "Y"
                        print("Directory quota for " + fs_path + " is being created...")
                
                    if create_confirm == "y" or create_confirm == "Y" or create_confirm == "Yes" or create_confirm == "yes": 
                        rc.quota.create_quota(file_id, limit)
                        logging.info(f'A new directory quota was created for {fs_path}')

        except qumulo.lib.request.RequestError as excpt:
            if (excpt.status_code == 404):
                print (f"Directory {fs_path} does not exist on the cluster.")
                logging.info(f'Directory {fs_path} does not exist on destination.')
                create_dir = input("Do you want to create"+ fs_path +" directory?: [Y/n]")
                if create_dir in ['y','Y','Yes','yes']:
                    fs_path_splitted = fs_path.split("/")
                    name = fs_path_splitted[-2]
                    path = '/'.join(fs_path_splitted[:-2])
                    if path == "":
                        path = "/"
                    rc.fs.create_directory(dir_path=path, name=name)
                    file_id = rc.fs.get_file_attr(fs_path)['id']
                    rc.quota.create_quota(file_id, limit)
            else:
                print ("Error: %s" % excpt)
            
if __name__ == '__main__':
    main(sys.argv[1:])
