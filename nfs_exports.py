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
    logging.basicConfig(filename='nfs.log', level=logging.INFO,
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

def nfs_list(rc):
    nfs_exports = rc.nfs.nfs_list_exports()
    nfs_json_file = open('nfs.json', 'w')
    json.dump(nfs_exports, nfs_json_file, indent=4)
    nfs_json_file.close()
      

def nfs_define(rc, approve):
    approve = False
    nfs_json_file = open('nfs.json','r')
    nfs_json_data = nfs_json_file.read()
    nfs_json_object = json.loads(nfs_json_data)
    
    nfs_exports = nfs_json_object
    for x in range(len(nfs_exports)):
        export_path = nfs_exports[x]['export_path']
        fs_path = nfs_exports[x]['fs_path']
        description = nfs_exports[x]['description']
        restrictions = []
        for r in nfs_exports[x]['restrictions']:
            restrictions.append(qumulo.rest.nfs.NFSExportRestriction(r))
        present_64_bit_fields_as_32_bit = nfs_exports[x]['present_64_bit_fields_as_32_bit']
        if (present_64_bit_fields_as_32_bit == []):
            present_64_bit_fields_as_32_bit = None
        fields_to_present_as_32_bit = nfs_exports[x]['fields_to_present_as_32_bit']
        if (fields_to_present_as_32_bit == []):
            fields_to_present_as_32_bit = None

        try: 
            rc.nfs.nfs_get_export(export_path)
            print (export_path + " nfs export is already defined... ")
            logging.info('{} NFS export is already defined.'.format(export_path))

            if approve == False:
                update_confirm = input("Do you want to update "+ export_path +" NFS export?: [Y/n]")
            else:
                update_confirm = "Y"
                print(export_path + " export configuration is being updated...")

            if update_confirm == "y" or update_confirm == "Y" or update_confirm == "Yes" or update_confirm == "yes":
                existing_export = rc.nfs.nfs_get_export(export_path=nfs_exports[x]['export_path'])
                rc.nfs.nfs_modify_export(
                    id_ = existing_export['id'],
                    export_path = export_path,
                    fs_path = fs_path,
                    description = description,
                    restrictions= restrictions, 
                    allow_fs_path_create=False, 
                    present_64_bit_fields_as_32_bit=present_64_bit_fields_as_32_bit, 
                    fields_to_present_as_32_bit=fields_to_present_as_32_bit
                    )
                logging.info('{} export configuration was updated.'.format(export_path))
            else:
                print(export_path + " export wasn't updated...")
                logging.info('{} export wasn\'t updated.'.format(export_path))
        
        except:
            try: 
                if approve == False:
                    create_confirm = input("Do you want to create "+ export_path +" NFS export?: [Y/n]")
                else:
                    create_confirm = "Y"
                    print(export_path + " export configuration is being created...")

                if create_confirm == "y" or create_confirm == "Y" or create_confirm == "Yes" or create_confirm == "yes":
                    rc.nfs.nfs_add_export(
                        export_path = export_path,
                        fs_path = fs_path,
                        description = description,
                        restrictions= restrictions, 
                        allow_fs_path_create=True, 
                        #present_64_bit_fields_as_32_bit=present_64_bit_fields_as_32_bit, 
                        fields_to_present_as_32_bit=fields_to_present_as_32_bit
                        )
                    print("A new NFS export was created for path:" + fs_path + " with export path: " + export_path)
                    logging.info('{} export configuration was created.'.format(export_path))

            except qumulo.lib.request.RequestError as excpt:
                if (excpt.status_code == 404):
                    print ("Directory '" + fs_path + "' does not exist on destination...")
                    logging.info('Directory {} does not exist on destination.'.format(fs_path))

                else:
                    print ("Error: %s" % excpt)
        print()

if __name__ == '__main__':
    main(sys.argv[1:])

  