# Qumulo-Shift-Incremental-Sync

This script can help Qumulo customer who wants to copy incremental data changes to AWS S3 with Qumulo Shift feature. 

## Installation
1. Copy **s3Rep.sh** and **s3Rep.json** files into one of the Qumulo nodes in your cluster. 
2. Put the files in **/history** folder.
3. Edit **s3Rep.json** file according to your S3 bucket details with your AWS account Access key ID and Secret access key. 
4. Add entry into both **/etc/crontab** and **/config/persist/etc/crontab** to make it persist during reboots.

## How it works
This script can help you to copy incremental data changes to your AWS S3 bucket from Qumulo with Shift capabilities. Qumulo Shift copies only changed files not whole files again and again. However, currently, Qumulo Shift doesn't have a scheduler mechanism to send incrementals automatically. 

Qumulo API capabilities allow you to write your own automation until Qumulo announces native automation for this purpose. 

**s3Rep.sh** script creates an object replication for a directory and copies the files and subfolders inside this directory according to your definitions inside ***s3Rep.json*** file.

As a rule of Qumulo, any files you might need to create, even temporarily, should be placed in /history instead. Because of that, you need to put **s3Rep.sh** and **s3Rep.json** files in /history directory.

Also, you need to add your crontab entry into both **/etc/crontab** and **/config/persist/etc/crontab** to make it persist during reboots.

Crontab entry example for hourly run:

`0 * * * * /bin/bash /history/s3Rep.sh > /history/s3Rep.log`

You can create your own definition by using https://crontab-generator.org/

**s3Rep.sh** also delete your previous object replications for defined directories. 

If there is an ongoing object replication for the defined directories, the script won't create a new object replication at that time. 
