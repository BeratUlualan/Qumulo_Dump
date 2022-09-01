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
    logging.basicConfig(filename='smb.log', level=logging.INFO,
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
            smb_list(prc)
        elif opt in ("-a","--auto_approve"):
            approve = True
        else:            
            if opt in ("-s","--set"):
                src = login('secondary')
                print ()
                smb_define(src, approve)

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

def loosen_trustees(permissions):
    '''Find an identity for each domain that can be used cross cluster'''
    loose_permissions=[]
    for permission in permissions:
        if permission['trustee']['domain'] == "LOCAL":
            # SIDs for local users are unique per cluster, strip them.
            if 'sid' in permission['trustee']:
                del permission['trustee']['sid']
            # A deleted user can still be referenced by auth_id, but we will
            #   match by name if they still exist.
            if permission['trustee']['name']:
                del permission['trustee']['auth_id']
        else:
            # All domains but API_CREATOR_DOMAIN and API_INTERNAL_DOMAIN use
            #   identities that are not specific to the cluster, and auth_id
            #   will mismatch.
            if 'auth_id' in permission['trustee']:
                del permission['trustee']['auth_id']
        loose_permissions.append(permission)
    return loose_permissions

def smb_list(rc):
    shares = []
    smb_shares=rc.smb.smb_list_shares()
    for x in range(len(smb_shares)):
        share_details = {}
        id_ = smb_shares[x]['id']
        share_details = rc.smb.smb_list_share(id_=id_)
        share_details = {
            "share_name" : share_details['share_name'],
            "fs_path" : share_details['fs_path'],
            "description" : share_details['description'],
            "read_only" : None,
            "allow_guest_access" : None,
            "allow_fs_path_create" : True,
            "access_based_enumeration_enabled" : share_details['access_based_enumeration_enabled'],
            "default_file_create_mode" : share_details['default_file_create_mode'],
            "default_directory_create_mode" : share_details['default_directory_create_mode'],
            "require_encryption" : share_details['require_encryption'],
            "bytes_per_sector" : "512",
            "network_permissions" : share_details['network_permissions'],
            "permissions" : loosen_trustees(share_details['permissions'])
        }
        shares.append(share_details)
    
    smb_settings = rc.smb.get_smb_settings()
    smb_dump = {
        "smb_settings" : smb_settings,
        "smb_shares" : shares
    }
    smb_json_file = open('smb.json', 'w')
    json.dump(smb_dump, smb_json_file, indent=4)
    smb_json_file.close()
      

def smb_define(rc, approve):
    smb_json_file = open('smb.json','r')
    smb_json_data = smb_json_file.read()
    smb_json_object = json.loads(smb_json_data)

    shares = smb_json_object['smb_shares']
    for x in range(len(shares)):
        share_name = shares[x]['share_name']
        fs_path = shares[x]['fs_path']
        description = shares[x]['description']
        read_only = shares[x]['read_only']
        allow_guest_access = shares[x]['allow_guest_access']
        allow_fs_path_create = shares[x]['allow_fs_path_create']
        access_based_enumeration_enabled = shares[x]['access_based_enumeration_enabled']
        default_file_create_mode = shares[x]['default_file_create_mode']
        default_directory_create_mode = shares[x]['default_directory_create_mode']
        permissions = shares[x]['permissions']
        bytes_per_sector = shares[x]['bytes_per_sector']
        require_encryption = shares[x]['require_encryption']
        network_permissions = shares[x]['network_permissions']

        try:
            rc.smb.smb_list_share(share_name)
            print (share_name + " SMB share is already defined... ")
            logging.info('{} SMB share is already defined.'.format(share_name))

            if approve == False:
                update_confirm = input("Do you want to update "+ share_name +" SMB share?: [Y/n]")
            else:
                update_confirm = "Y"
                print(share_name + " share configuration is being updated...")
            
            if update_confirm == "y" or update_confirm == "Y" or update_confirm == "Yes" or update_confirm == "yes":
                existing_share = rc.smb.smb_list_share(name=share_name)
                rc.smb.smb_modify_share(
                    id_ = existing_share['id'],
                    fs_path = fs_path,
                    description = description,
                    permissions = permissions,
                    allow_fs_path_create=False,
                    access_based_enumeration_enabled = access_based_enumeration_enabled,
                    default_file_create_mode = default_file_create_mode,
                    bytes_per_sector = bytes_per_sector,
                    default_directory_create_mode = default_directory_create_mode,
                    require_encryption = require_encryption,
                    network_permissions = network_permissions,
                    )
                logging.info('{} share configuration was updated.'.format(share_name))
            else:
                print(share_name + " share wasn't updated...")
                logging.info('{} share wasn\'t updated.'.format(share_name))
        except: 
            if approve == False:
                create_confirm = input("Do you want to create "+ share_name +" SMB share?: [Y/n]")
            else:
                create_confirm = "Y"
                print(share_name + " share configuration is being created...")
            
            if create_confirm == "y" or create_confirm == "Y" or create_confirm == "Yes" or create_confirm == "yes":
                rc.smb.smb_add_share(
                    shares[x]['share_name'],
                    shares[x]['fs_path'],
                    shares[x]['description'],
                    read_only = shares[x]['read_only'],
                    allow_guest_access = shares[x]['allow_guest_access'],
                    allow_fs_path_create = True,
                    access_based_enumeration_enabled = shares[x]['access_based_enumeration_enabled'],
                    default_file_create_mode = shares[x]['default_file_create_mode'],
                    default_directory_create_mode = shares[x]['default_directory_create_mode'],
                    permissions = shares[x]['permissions'],
                    bytes_per_sector = shares[x]['bytes_per_sector'],
                    require_encryption = shares[x]['require_encryption'],
                    network_permissions = shares[x]['network_permissions']
                )
                logging.info('{} share configuration was created.'.format(shares[x]['share_name']))

if __name__ == '__main__':
    main(sys.argv[1:])
