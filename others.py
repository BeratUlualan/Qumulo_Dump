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
            others_list(prc)
        elif opt in ("-a","--auto_approve"):
            approve = True
        else:            
            if opt in ("-s","--set"):
                src = login('secondary')
                print ()
                others_define(src, approve)

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
    
    logging.info(f'Connection established with {cluster_address}')

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

def others_list(rc):
    ########### NTP ###########
    ntp=rc.time_config.get_time()
    ntp_json_file = open('ntp.json', 'w')
    json.dump(ntp, ntp_json_file, indent=4)
    ntp_json_file.close()
    logging.info(f'The NTP configurations were added into the JSON file')
    
    ########### LDAP ########### 
    ldap=rc.ldap.settings_get_v2()
    ldap_json_file = open('ldap.json', 'w')
    json.dump(ldap, ldap_json_file, indent=4)
    ldap_json_file.close()
    logging.info(f'The LDAP configurations were added into the JSON file')

    ########### USER MAPPINGS ########### 
    maps=rc.auth.user_defined_mappings_get()
    maps_json_file = open('maps.json', 'w')
    json.dump(maps, maps_json_file, indent=4)
    maps_json_file.close()
    logging.info(f'The user mappings were added into the JSON file')

    ########### AD ########### 
    ad=rc.ad.poll_ad()
    ad_json_file = open('ad.json', 'w')
    json.dump(ad, ad_json_file, indent=4)
    ad_json_file.close()
    logging.info(f'The AD configurations were added into the JSON file')
    
    ########### TENANTS ########### 
    # ad=rc.ad.poll_ad()
    # ad_json_file = open('ad.json', 'w')
    # json.dump(ad, ad_json_file, indent=4)
    # ad_json_file.close()
    # logging.info(f'The multi-tenancy configurations were added into the JSON file')

    ########### SNAPSHOT POLICIES ########### 
    snapshot_policies = rc.snapshot.list_policies()['entries']
    snap_policies = []
    for policy in snapshot_policies:
        directory_id = policy['source_file_id']
        policy['directory_path'] = rc.fs.resolve_paths(ids=[directory_id])[0]['path']
        snap_policies.append(policy)
    snap_policy_json_file = open('snap_policy.json', 'w')
    json.dump(snap_policies, snap_policy_json_file, indent=4)
    snap_policy_json_file.close()
    logging.info(f'The snapshot policy configurations were added into the JSON file')

    ########### NETWORK ########### 
    interface = rc.network.list_interfaces()
    networks = rc.network.list_networks(1)
    networks_w_tn = []
    for network in networks:
        network['tenant_name'] = get_tenant_name(rc, network['tenant_id'])
        networks_w_tn.append(network)
    network_settings = {
        'interface' : interface,
        'networks' : networks_w_tn
    }
    network_json_file = open('network.json', 'w')
    json.dump(network_settings, network_json_file, indent=4)
    network_json_file.close()
    logging.info(f'The network configurations were added into the JSON file')

def others_define(rc, approve):
    approve = False

    ########### NTP ########### 
    ntp_json_file = open('ntp.json','r')
    ntp_json_data = ntp_json_file.read()
    ntp_json_object = json.loads(ntp_json_data)
    
    try:
        ntp = ntp_json_object
        rc.time_config.set_time(
            use_ad_for_primary=ntp['use_ad_for_primary'], 
            ntp_servers=ntp['ntp_servers'])
        logging.info(f'The NTP configurations are done.')
    except Exception as excpt:
        logging.error(f'Error: {excpt}')
        
    ########### NETWORK ########### 
    network_json_file = open('network.json','r')
    network_json_data = network_json_file.read()
    network_json_object = json.loads(network_json_data)

    try:
        interface = network_json_object['interface'][0]
        rc.network.modify_interface(
            interface_id=int(interface['id']), 
            default_gateway=interface['default_gateway'], 
            bonding_mode=interface['bonding_mode'], 
            mtu=interface['mtu'])
    except Exception as excpt:
        logging.error(f'Error: {excpt}')    

    try:
        networks = network_json_object['networks']
        for network in networks:
            tenant_id = get_tenant_id(rc, network['tenant_name'])
            if network['id'] == 1:
                rc.network.modify_network(
                    interface_id=interface['id'], 
                    assigned_by = network['assigned_by'],
                    network_id=network['id'], 
                    name= network['name'], 
                    floating_ip_ranges=network['floating_ip_ranges'], 
                    dns_servers=network['dns_servers'], 
                    dns_search_domains=network['dns_search_domains'],
                    ip_ranges=network['ip_ranges'],
                    netmask=network['netmask'],
                    # mtu=network['mtu'],
                    tenant_id = tenant_id,
                    vlan_id=network['vlan_id'])
            else:
                rc.network.add_network(
                    interface_id=interface['id'],  
                    name= network['name'], 
                    floating_ip_ranges=network['floating_ip_ranges'], 
                    dns_servers=network['dns_servers'], 
                    dns_search_domains=network['dns_search_domains'],
                    ip_ranges=network['ip_ranges'],
                    netmask=network['netmask'],
                    # mtu=network['mtu'],
                    tenant_id = tenant_id,
                    vlan_id=network['vlan_id'])
        logging.info(f'The network configurations are done.')
    except Exception as excpt:
        logging.error(f'Error: {excpt}')
        
    ########### LDAP ########### 
    ldap_json_file = open('ldap.json','r')
    ldap_json_data = ldap_json_file.read()
    ldap_json_object = json.loads(ldap_json_data)
    
    ldap = ldap_json_object
    print("Please enter below details for LDAP join operations.")
    username = input("LDAP Bind Username: ")
    password = getpass("LDAP Bind Password: ")
    try: 
        rc.ldap.settings_set_v2(
            use_ldap = ldap['use_ldap'],
            bind_uri = ldap['bind_uri'],
            user = username,
            password = password,
            base_distinguished_names = ldap['base_distinguished_names'],
            ldap_schema = ldap['ldap_schema'],
            #ldap_schema_description = ldap['ldap_schema_description'],
            encrypt_connection = ldap['encrypt_connection']
            )
        logging.info(f'The AD configurations are done.')
    except Exception as excpt:
        logging.error(f'Error: {excpt}')


    ########### AD ########### 
    ad_json_file = open('ad.json','r')
    ad_json_data = ad_json_file.read()
    ad_json_object = json.loads(ad_json_data)

    ad = ad_json_object
    print("Please enter below details for AD join operations.")
    username = input("AD Username: ")
    password = getpass("AD Password: ")
    try:
        rc.ad.join_ad(
            ad['domain'], 
            username, 
            password, 
            ou=ad['ou'], 
            domain_netbios=ad['domain_netbios'], 
            enable_ldap=ad['use_ad_posix_attributes'], 
            base_dn=ad['base_dn'])
        logging.info(f'The AD configurations are done.')
    except Exception as excpt:
        logging.error(f'Error: {excpt}')

    ########### SNAPSHOT POLICIES ########### 
    snap_policy_json_file = open('snap_policy.json','r')
    snap_policy_json_data = snap_policy_json_file.read()
    snap_policy_json_object = json.loads(snap_policy_json_data)
    try:
        for snap_policy in snap_policy_json_object:
            policy_name = snap_policy['policy_name']
            snapshot_name_template = snap_policy['snapshot_name_template']
            directory_path = snap_policy['directory_path']
            directory_id = rc.fs.get_file_attr(directory_path)['id']
            del snap_policy['schedule']['id']
            schedule_info = snap_policy['schedule']
            enabled_state = snap_policy['enabled']
            lock_key_ref = snap_policy['lock_key_ref']
            rc.snapshot.create_policy(
                policy_name = policy_name, 
                snapshot_name_template = snapshot_name_template,
                schedule_info=schedule_info, 
                enabled=enabled_state,
                directory_id=directory_id,
                lock_key_ref = lock_key_ref
                )
        logging.info(f'The snapshot policy configurations are done.')
    except Exception as excpt:
        logging.error(f'Error: {excpt}')

if __name__ == '__main__':
    main(sys.argv[1:])