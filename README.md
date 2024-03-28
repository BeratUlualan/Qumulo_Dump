# Qumulo Dump

This script can help Qumulo customer who wants to dump an existing cluster settings or set them on another Qumulo cluster. 

## Requirements and Setup
- python 3.6+
- Qumulo API Python bindings `pip install -r requirements.txt`
- Qumulo cluster software version >= 6.3.1.1

## How it works
This script can help you to dump an existing cluster settings or set them on another Qumulo cluster.

Qumulo API capabilities allow you to write your own automation. 

Each script can use with below parameters:
- `-a, --auto_approve`  Sync all existing settings without confirmation. If you want to use it, please put it before other arguments.
- `-d, --dump`          Dump the settings.
- `-s, --set`           Set the settings.

You need to define cluster settings in **credentials.json** file. 
- The `primary` settings in the file is used for the cluster dump activity. 
- The `secondary` settings in the file is used for the cluster set activity. 

Python files:
- **nfs_exports.py** script for NFS exports.
- **smb_shares.py** script for SMB shares.
- **quotas.py** script for quotas.
- **users.py** script for users.
- **others.py** script for Network, NTP, AD, Snapshot policies.

For example: 
- Dump
`python3 nfs_exports.py -d`

- Set
`python3 nfs_exports.py -s`
or
`python3 nfs_exports.py -as` (auto approve)

