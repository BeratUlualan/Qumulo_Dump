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
import jmespath

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
            nfs_list(prc)
        elif opt in ("-a","--auto_approve"):
            approve = True
        else:            
            if opt in ("-s","--set"):
                src = login('secondary')
                print ()
                nfs_define(src, approve)

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

        return (rc)

    except Exception as excpt:
        logging.error(f'Connection issue with {cluster_address}')
        logging.error(f'Error: {excpt}')
        sys.exit(1)

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

def nfs_list(rc):
    exports = rc.nfs.nfs_list_exports()['entries']
    nfs_exports = []
    count = 0
    for export in exports:
        export_details = {}
        export_details = {
            "export_path" : export['export_path'],
            "tenant_name" : get_tenant_name(rc, export['tenant_id']),
            "fs_path" : export['fs_path'],
            "description" : export['description'],
            "restrictions" : export['restrictions'],
            "allow_fs_path_create" : True,
            "fields_to_present_as_32_bit" : export['fields_to_present_as_32_bit']
            }
        nfs_exports.append(export_details)
        logging.info(f'{export["export_path"]} configurations was listed')
        count +=1
    logging.info(f'Totally {count} NFS exports were added into the JSON file')
    nfs_json_file = open('nfs.json', 'w')
    json.dump(nfs_exports, nfs_json_file, indent=4)
    nfs_json_file.close()

def nfs_define(rc, approve):
    approve = False
    nfs_json_file = open('nfs.json','r')
    nfs_json_data = nfs_json_file.read()
    nfs_json_object = json.loads(nfs_json_data)
    
    nfs_exports = nfs_json_object
    count = 0
    for export in nfs_exports:
        export_path = export['export_path']
        fs_path = export['fs_path']
        description = export['description']
        tenant_id = get_tenant_id(rc, export['tenant_name'])
        restrictions = []
        for r in export['restrictions']:
            restrictions.append(qumulo.rest.nfs.NFSExportRestriction(r))
        fields_to_present_as_32_bit = export['fields_to_present_as_32_bit']
        if (fields_to_present_as_32_bit == []):
            fields_to_present_as_32_bit = None

        nfs_exports = rc.nfs.nfs_list_exports()['entries']
        existing_export = jmespath.search(
            f"[?export_path == '{export_path}']", nfs_exports
        )
        if existing_export != []: 
            export_id = existing_export[0]["id"]
            logging.error(f'{export_path} NFS export is already defined.')

            if approve == False:
                update_confirm = input("Do you want to update "+ export_path +" NFS export?: [Y/n]")
            else:
                update_confirm = "Y"
                print(export_path + " export configuration is being updated...")

            if update_confirm in ["y","Y","Yes","yes"]:
                rc.nfs.nfs_modify_export(
                    id_ = export_id,
                    export_path = export_path,
                    fs_path = fs_path,
                    description = description,
                    restrictions = restrictions, 
                    tenant_id = tenant_id,
                    allow_fs_path_create=False, 
                    fields_to_present_as_32_bit=fields_to_present_as_32_bit
                    )
                logging.info(f'{export_path} export configuration was updated.')
            else:
                print(export_path + " export wasn't updated...")
                logging.info(f'{export_path} export wasn\'t updated.')
        
        else:
            if approve == False:
                create_confirm = input("Do you want to create "+ export_path +" NFS export?: [Y/n]")
            else:
                create_confirm = "Y"
                print(export_path + " export configuration is being created...")

            if create_confirm in ["y","Y","Yes","yes"]:
                rc.nfs.nfs_add_export(
                    export_path = export_path,
                    fs_path = fs_path,
                    description = description,
                    restrictions= restrictions, 
                    tenant_id = tenant_id,
                    allow_fs_path_create=True, 
                    fields_to_present_as_32_bit=fields_to_present_as_32_bit
                    )
                logging.info(f"A new NFS export was created for path: {fs_path} with export path: {export_path}")
        count +=1
    logging.info(f'Totally {count} NFS exports were added into the JSON file')

if __name__ == '__main__':
    main(sys.argv[1:])
