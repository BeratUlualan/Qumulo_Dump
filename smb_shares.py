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
import jmespath
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
    
    logging.info(f'Login credentials defined for {cluster_address} - {username}')

    try:
        rc = RestClient(cluster_address, port)
        rc.login(username, password)
        print ("Connection established with " + cluster_address)
        logging.info(f'Connection established with {cluster_address}')

        return (rc)

    except Exception as excpt:
        logging.error(f'Connection issue with {cluster_address}')
        logging.error(f'Error: {excpt}')
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
                if "auth_id" in permission['trustee']:
                    del permission['trustee']['auth_id']
        else:
            # All domains but API_CREATOR_DOMAIN and API_INTERNAL_DOMAIN use
            #   identities that are not specific to the cluster, and auth_id
            #   will mismatch.
            if 'auth_id' in permission['trustee']:
                del permission['trustee']['auth_id']
        loose_permissions.append(permission)
    return loose_permissions

def get_tenant_name(rc, tenant_id):
    tenants = rc.multitenancy.list_tenants()
    for tenant in tenants:
        if tenant_id == tenant.id:
            return tenant.name

def get_tenant_id(rc, tenant_name):
    tenants = rc.multitenancy.list_tenants()
    for tenant in tenants:
        if tenant_name == tenant.name:
            return tenant.id  

def smb_list(rc):
    smb_shares=rc.smb.smb_list_shares(populate_trustee_names=True)['entries']
    shares = []
    count = 0
    for share in smb_shares:
        share_details = {}
        id_ = share['id']
        share_details = rc.smb.smb_list_share(share_id=id_)
        share_details = {
            "share_name" : share_details['share_name'],
            "fs_path" : share_details['fs_path'],
            "description" : share_details['description'],
            "allow_fs_path_create" : True,
            "access_based_enumeration_enabled" : share_details['access_based_enumeration_enabled'],
            "default_file_create_mode" : share_details['default_file_create_mode'],
            "default_directory_create_mode" : share_details['default_directory_create_mode'],
            "require_encryption" : share_details['require_encryption'],
            "network_permissions" : share_details['network_permissions'],
            "tenant_name" : get_tenant_name(rc, share_details['tenant_id']),
            "permissions" : loosen_trustees(share_details['permissions'])
        }
        shares.append(share_details)
        logging.info(f'{share["share_name"]} configurations was listed')
        count +=1
    logging.info(f'Totally {count} SMB share were added into the JSON file')
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
    count = 0
    for share in shares:
        share_name = share['share_name']
        fs_path = share['fs_path']
        description = share['description']
        allow_fs_path_create = share['allow_fs_path_create']
        access_based_enumeration_enabled = share['access_based_enumeration_enabled']
        default_file_create_mode = share['default_file_create_mode']
        default_directory_create_mode = share['default_directory_create_mode']
        permissions = share['permissions']
        require_encryption = share['require_encryption']
        tenant_id = get_tenant_id(rc, share['tenant_name'])
        network_permissions = share['network_permissions']

        smb_shares = rc.smb.smb_list_shares(populate_trustee_names=True)['entries']
        existing_share = jmespath.search(
            f"[?share_name == '{share_name}']", smb_shares
        )
        
        if existing_share != []:
            edited_permissions = loosen_trustees(permissions)
            share_id = existing_share[0]["id"]
            print (share_name + " SMB share is already defined... ")
            logging.info(f'{share_name} - SMB share is already defined.')

            if approve == False:
                update_confirm = input("Do you want to update "+ share_name +" SMB share?: [Y/n]")
            else:
                update_confirm = "Y"
                print(share_name + " share configuration is being updated...")
            
            if update_confirm == "y" or update_confirm == "Y" or update_confirm == "Yes" or update_confirm == "yes":
                rc.smb.smb_modify_share(
                    share_id = share_id,
                    share_name = share_name,
                    fs_path = fs_path,
                    description = description,
                    permissions = edited_permissions,
                    allow_fs_path_create=False,
                    tenant_id = tenant_id,
                    access_based_enumeration_enabled = access_based_enumeration_enabled,
                    default_file_create_mode = default_file_create_mode,
                    default_directory_create_mode = default_directory_create_mode,
                    require_encryption = require_encryption,
                    network_permissions = network_permissions
                    )
                print("OK")
                logging.info(f'{share_name} share configuration was updated.')
            else:
                print(share_name + " share wasn't updated...")
                logging.info(f'{share_name} share wasn\'t updated.')
        else: 
            if approve == False:
                create_confirm = input("Do you want to create "+ share_name +" SMB share?: [Y/n]")
            else:
                create_confirm = "Y"
                print(share_name + " share configuration is being created...")
            
            if create_confirm in ["y","Y","Yes","yes"]:
                rc.smb.smb_add_share(
                    share_name = share['share_name'],
                    fs_path = share['fs_path'],
                    description = share['description'],
                    allow_fs_path_create = True,
                    access_based_enumeration_enabled = share['access_based_enumeration_enabled'],
                    default_file_create_mode = share['default_file_create_mode'],
                    default_directory_create_mode = share['default_directory_create_mode'],
                    permissions = share['permissions'],
                    require_encryption = share['require_encryption'],
                    tenant_id = get_tenant_id(rc, share['tenant_name']),
                    network_permissions = share['network_permissions']
                )
                logging.info('{} share configuration was created.'.format(share['share_name']))
        count +=1
    logging.info(f'Totally {count} NFS exports were added into the JSON file')
if __name__ == '__main__':
    main(sys.argv[1:])
