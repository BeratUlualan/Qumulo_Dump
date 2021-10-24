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
    logging.basicConfig(filename='others.log', level=logging.INFO,
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

def others_list(rc):
    ########### NTP ###########
    ntp=rc.time_config.get_time()
    ntp_json_file = open('ntp.json', 'w')
    json.dump(ntp, ntp_json_file, indent=4)
    ntp_json_file.close()

    ########### AD ########### 
    ad=rc.ad.poll_ad()
    ad_json_file = open('ad.json', 'w')
    json.dump(ad, ad_json_file, indent=4)
    ad_json_file.close()

    ########### SNAPSHOT POLICIES ########### 
    snapshot_policies = rc.snapshot.list_policies()['entries']
    snap_policies = []
    for snapshot_policy in snapshot_policies:
        name = snapshot_policy['name']
        directory_id = snapshot_policy['source_file_ids']
        directory_path = rc.fs.resolve_paths(directory_id)[0]['path']
        del snapshot_policy['schedules'][0]['id']
        schedule_info = snapshot_policy['schedules']
        enabled_state = snapshot_policy['enabled']
        snap_policy = {'name':name, 'directory_path':directory_path, 'schedules': schedule_info, 'enabled': enabled_state}
        snap_policies.append(snap_policy)
    snap_policy_json_file = open('snap_policy.json', 'w')
    json.dump(snap_policies, snap_policy_json_file, indent=4)
    snap_policy_json_file.close()

    ########### NETWORK ########### 
    interface = rc.network.list_interfaces()
    networks = rc.network.list_networks(1)
    network_settings = {
        'interface' : interface,
        'networks' : networks
    }
    network_json_file = open('network.json', 'w')
    json.dump(network_settings, network_json_file, indent=4)
    network_json_file.close()

def others_define(rc, approve):
    approve = False

    ########### NTP ########### 
    ntp_json_file = open('ntp.json','r')
    ntp_json_data = ntp_json_file.read()
    ntp_json_object = json.loads(ntp_json_data)
    
    ntp = ntp_json_object
    rc.time_config.set_time(
        use_ad_for_primary=ntp['use_ad_for_primary'], 
        ntp_servers=ntp['ntp_servers'])

    ########### AD ########### 
    ad_json_file = open('ad.json','r')
    ad_json_data = ad_json_file.read()
    ad_json_object = json.loads(ad_json_data)

    ad = ad_json_object
    print("Please enter below details for AD join operations.")
    username = input("AD Username: ")
    password = getpass("AD Password: ")
    rc.ad.join_ad(
        ad['domain'], 
        username, 
        password, 
        ou=ad['ou'], 
        domain_netbios=ad['domain_netbios'], 
        enable_ldap=ad['use_ad_posix_attributes'], 
        base_dn=ad['base_dn'])

    ########### SNAPSHOT POLICIES ########### 
    snap_policy_json_file = open('snap_policy.json','r')
    snap_policy_json_data = snap_policy_json_file.read()
    snap_policy_json_object = json.loads(snap_policy_json_data)
    
    for snap_policy in snap_policy_json_object:
        name = snap_policy['name']
        directory_path = snap_policy['directory_path']
        directory_id = rc.fs.get_file_attr(directory_path)['id']
        schedule_info = snap_policy['schedules'][0]
        enabled_state = snap_policy['enabled']
        rc.snapshot.create_policy(
            name=name, 
            schedule_info=schedule_info, 
            enabled=enabled_state,
            directory_id=directory_id)

    ########### NETWORK ########### 
    network_json_file = open('network.json','r')
    network_json_data = network_json_file.read()
    network_json_object = json.loads(network_json_data)

    interface = network_json_object['interface']
    rc.network.modify_interface(
        interface_id=int(interface['id']), 
        default_gateway=interface['default_gateway'], 
        bonding_mode=interface['bonding_mode'], 
        mtu=interface['mtu'])

    networks = network_json_object['networks']
    if len(networks) > 1:
        for network in networks:
            if network['id'] == 1:
                rc.network.modify_network(
                    interface_id=interface['id'], 
                    network_id=network['id'], 
                    name= network['name'], 
                    floating_ip_ranges=network['floating_ip_ranges'], 
                    dns_servers=network['dns_servers'], 
                    dns_search_domains=network['dns_search_domains'],
                    ip_ranges=network['ip_ranges'],
                    netmask=network['netmask'],
                    mtu=network['mtu'],
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
                    mtu=network['mtu'],
                    vlan_id=network['vlan_id'])

if __name__ == '__main__':
    main(sys.argv[1:])