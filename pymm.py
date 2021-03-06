import digitalocean
from digitalocean import SSHKey
from Crypto.PublicKey import RSA
import os
from datetime import datetime
import requests
import paramiko
import time
import argparse
import zipfile
import shutil
import hashlib
from github import Github
import json

from urllib.request import urlopen
from shutil import copyfileobj
from tempfile import NamedTemporaryFile

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
DO_API_TOKEN = None
# '64gb','48gb','32gb','16gb','2gb','1gb','512mb'
DO_RESOURCE_DIC = { '64gb': '64g', '48gb': '48g', '32gb': '32g', '16gb': '16g', '2gb': '2g', '1gb': '1024m', '512mb':'512m'}


def teardown_server():
    global DO_API_TOKEN
    global ROOT_DIR

    print("Checking For Any pymm Keys")
    manager = digitalocean.Manager(token=DO_API_TOKEN)
    all_ssh_keys = manager.get_all_sshkeys()

    for ssh_key in all_ssh_keys:
        print(ssh_key.name + " -> " + str(ssh_key.id))
        if ssh_key.name == 'pymm-ssh-key':
            print("Found A Duplicate Key. Removing It")

            # delete the ssh key
            url = "https://api.digitalocean.com/v2/account/keys/" + str(ssh_key.id)

            response = requests.delete(url=url, headers={"content-type": "application/json",
                                                         "Authorization": "Bearer " + DO_API_TOKEN})
            print(response.content)

    print("Checking For Any pymm DO Servers")
    all_droplets = manager.get_all_droplets()
    for droplet in all_droplets:
        print(droplet)
        if "pymm-server" in droplet.name:
            print("Found A Duplicate Droplet. Removing It")

            url = "https://api.digitalocean.com/v2/droplets/" + str(droplet.id)

            response = requests.delete(url=url, headers={"content-type": "application/json",
                                                         "Authorization": "Bearer " + DO_API_TOKEN})
            print(response.content)


def install_server(do_size, do_region, github=None):
    global DO_API_TOKEN
    global ROOT_DIR
    global DO_RESOURCE_DIC

    java_max_heap = DO_RESOURCE_DIC[do_size]

    manager = digitalocean.Manager(token=DO_API_TOKEN)

    # generate SSH keys
    print("Generating New SSH Keys")
    priv_key = RSA.generate(1024)
    priv_key_fp = open(ROOT_DIR + "/conf/privkey.pem", "wb")
    priv_key_fp.write(priv_key.exportKey('PEM'))
    priv_key_fp.close()

    pub_key = priv_key.publickey()
    pub_key_fp = open(ROOT_DIR + "/conf/pubkey.pem", "wb")
    pub_key_fp.write(b'' + pub_key.exportKey('OpenSSH'))
    pub_key_fp.close()

    print("Uploading New SSH Key")
    # add the ssh key to the digital ocean account
    local_ssh_key = open(ROOT_DIR + "/conf/pubkey.pem").read()
    print("Read In Key:")
    print(local_ssh_key)
    do_key = SSHKey(token=DO_API_TOKEN,
                    name='pymm-ssh-key',
                    public_key=local_ssh_key)
    do_key.create()

    print("Fetching Updated SSH Keys")
    do_ssh_keys = manager.get_all_sshkeys()
    print(do_ssh_keys)

    for do_ssh_key in do_ssh_keys:
        print("Checking If Key Named: " + do_ssh_key.name + " Is The Pymm Key")
        if do_ssh_key.name == 'pymm-ssh-key':
            print("It Is The Pymm Key! Generating DO Droplet")

            now = datetime.now()
            nowstring = now.strftime("%Y%m%dT%H.%M.%S")

            '''
            Valid DO Sizes names (based on RAM):
            64gb, 48gb, 32gb, 16gb, 2gb, 1gb, 512mb
            Valid Region Slugs:
            sfo1 - SanFransciso
            nyc1, nyc2 - New York City
            ams1, ams2 - Amsterdam
            lon1 - London
            * note that not all DO images are available in all regions
            '''

            # we have found our key. include it with generating our droplet
            droplet = digitalocean.Droplet(token=DO_API_TOKEN,
                                           name='pymm-server-' + nowstring,
                                           region=do_region,
                                           size=do_size,
                                           image='ubuntu-16-04-x64',
                                           ssh_keys=[do_ssh_key],
                                           backups=False)
            droplet.create()
            print("Droplet Creation Request Complete")

            print("Waiting For Server Provision To Complete")
            prov_status = "Haven't Even Checked Yet"
            while not prov_status == "completed":
                actions = droplet.get_actions()
                for action in actions:
                    action.load()
                    print(action.status)
                    prov_status = action.status

            print("Sleeping For A Minute To Let Everything Settle")
            time.sleep(60)

            print("Connecting via SSH to the DO Server")
            droplet.load()
            print("IP Address Of DO Server: " + droplet.ip_address)
            ip_address = droplet.ip_address

            priv_key = paramiko.RSAKey.from_private_key_file(ROOT_DIR + "/conf/privkey.pem")
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=droplet.ip_address, username="root", pkey=priv_key)
            print("Successfully Connected To DO Server. Now Executing Commands")

            print("Updating And Upgrading The System")
            command1 = "DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:webupd8team/java \n" \
                       "DEBIAN_FRONTEND=noninteractive apt-get -y update \n" \
                       "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade \n" \
                       "DEBIAN_FRONTEND=noninteractive apt-get install -y python-software-properties debconf-utils " \
                       "zip unzip\n"
            response1 = ssh_client.exec_command(command1)
            print(response1[1].read())  # stdout
            print(response1[2].read())  # stderr

            print("Configuring Minecraft Dependency PreRequisits")
            command2 = "echo debconf shared/accepted-oracle-license-v1-1 select true | sudo debconf-set-selections \n" \
                       "echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections \n"

            response2 = ssh_client.exec_command(command2)
            print(response2[1].read())
            print(response2[2].read())

            print("Installing Minecraft Dependencies")
            command3 = "DEBIAN_FRONTEND=noninteractive apt-get install " \
                       "oracle-java8-installer " \
                       "screen " \
                       "oracle-java8-set-default -y \n"
            response3 = ssh_client.exec_command(command3)
            print(response3[1].read())
            print(response3[2].read())

            print("Determing Appropriate Minecraft Version")
            url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

            vm_response = requests.get(url, verify=False, stream=True)
            with open(ROOT_DIR + "/conf/version_manifest.json", 'wb') as f:
                for chunk in vm_response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)


            json_data = json.load(open(ROOT_DIR + "/conf/version_manifest.json"))
            print(json_data["latest"])

            minecraft_url = "https://s3.amazonaws.com/Minecraft.Download/versions/" + \
                            json_data["latest"]["release"] + \
                            "/minecraft_server." + json_data["latest"]["release"] + ".jar"

            minecraft_file_name = "minecraft_server." + json_data["latest"]["release"] + ".jar"

            print("Downloading Minecraft Server")
            print("Download URL: " + minecraft_url)
            command4 = "DEBIAN_FRONTEND=noninteractive \n cd / \n mkdir minecraft \n cd /minecraft \n" + \
                        "wget -O " + minecraft_file_name + " " + minecraft_url + "\n chmod -R 777 *\n"

            response4 = ssh_client.exec_command(command4)
            print(response4[1].read())
            print(response4[2].read())

            print("Starting Initial Run Of Minecraft Server")
            command5 = "cd /minecraft\n java -Xmx" + java_max_heap + " -Xms512M -jar ./" + minecraft_file_name + " nogui"
            response5 = ssh_client.exec_command(command5)
            print(response5[1].read())
            print(response5[2].read())

            print("Agreeing To EULA")
            command6 = "cd /minecraft\n sed -i -e 's/eula=false/eula=true/g' eula.txt\n"
            response6 = ssh_client.exec_command(command6)
            print(response6[1].read())
            print(response6[2].read())

            print("Configuring Default Settings")
            command7 = "cd /minecraft\n " \
                       "sed -i -e 's/online-mode=true/online-mode=false/g' server.properties\n " \
                       "sed -i -e 's/motd=A Minecraft Server/motd=pymm Minecraft Server/g' server.properties\n " \
                       "sed -i -e 's/snooper-enabled=true/snooper-enabled=false/g' server.properties\n " \
                       "sed -i -e 's/difficulty=1/difficulty=2/g' server.properties\n "

            response7 = ssh_client.exec_command(command7)
            print(response7[1].read())
            print(response7[2].read())

            # "kill $(ps -aux | grep \"minecraft_server\"| awk '{print $2}')\n" \
            print("Loading For Sure Now")
            command8 = "cd /minecraft\n " \
                       "screen -dmS minecraft java -Xmx" + java_max_heap + " -Xms512M -jar ./" + minecraft_file_name + " nogui\n"
            response8 = ssh_client.exec_command(command8)
            print(response8[1].read())
            print(response8[2].read())

            ssh_client.close()

            return ip_address

def download_server_info(git_repo=None, git_username=None, git_password=None):
    #  downloads the server information so that restores can occur

    # find the server
    print("Connecting To DO And Searching For pymm Server")
    manager = digitalocean.Manager(token=DO_API_TOKEN)
    all_droplets = manager.get_all_droplets()
    found = False
    for droplet in all_droplets:
        print(droplet)
        if "pymm-server" in droplet.name:
            found = True
            print("Found pymm Server. Now Connecting")
            droplet.load()

            priv_key = paramiko.RSAKey.from_private_key_file(ROOT_DIR + "/conf/privkey.pem")

            #ssh in and save contents
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=droplet.ip_address, username="root", pkey=priv_key)
            command1 = "cd /minecraft\n" \
                       "screen -S minecraft -X stuff '/save-all\\r'\n"
            response1 = ssh_client.exec_command(command1)
            print(response1[1].read())
            print(response1[2].read())

            command2 = "cd /minecraft\n" \
                       "zip -r world.zip world;" \
                       "zip minecraft_save.zip banned-ips.json banned-players.json server.properties " \
                       "usercache.json whitelist.json ops.json world.zip\n"
            response2 = ssh_client.exec_command(command2)
            print(response2[1].read())
            print(response2[2].read())

            sftp_client = ssh_client.open_sftp()

            print("Authentication And Connection Via SFTP Successful, Now Transferring Files")
            sftp_client.get("/minecraft/minecraft_save.zip", ROOT_DIR + "/conf/minecraft_save.zip")
            sftp_client.close()

            # download the files

            # if a github repo was provided encrypt and send the data to there
            if git_repo is not None and git_username is not None and git_password is not None:
                now = datetime.now()
                nowstring = now.strftime("%Y%m%dT%H.%M.%S")
                if not os.path.isdir(ROOT_DIR + "/tmp"):
                    os.mkdir(ROOT_DIR + "/tmp")

                # compress all the data
                zip_fp = zipfile.ZipFile(ROOT_DIR + "/tmp/pymmdat-" + nowstring + ".zip", mode='w')
                # use a password that is a hash from the git username and password
                hasher = hashlib.sha512()
                hasher.update(b'' + git_username + git_password)
                encrypt_password = hasher.hexdigest()

                for file in os.listdir(ROOT_DIR + "/conf"):
                    if "pymmdat" not in file:
                        zip_fp.write(filename=ROOT_DIR + "/conf/" + file,
                                     compress_type=zipfile.ZIP_DEFLATED,
                                     arcname=os.path.basename(ROOT_DIR + "/conf/" + file))
                zip_fp.close()
                if os.path.isfile(ROOT_DIR + "/tmp/pymmdat-" + nowstring + ".zip"):
                    shutil.move(ROOT_DIR + "/tmp/pymmdat-" + nowstring + ".zip", ROOT_DIR + "/conf/pymmdat-" + nowstring + ".zip")
                shutil.rmtree(ROOT_DIR + "/tmp")

                github_client = Github(git_username, git_password)
                repo_found = False
                for repo in github_client.get_user().get_repos():
                    #print("Repo Name: " + repo.full_name + " (" + repo.clone_url + ")")
                    if repo.clone_url == git_repo:
                        print("Found Repo To Upload File To!")
                        repo_found = True
                        with open(ROOT_DIR + "/conf/pymmdat-" + nowstring + ".zip", mode='rb') as file:
                            fileContent = file.read()
                            repo.create_file("/pymmdat-" + nowstring + ".zip", "pymmexport " + nowstring, fileContent)
                        return

                if not repo_found:
                    print("The specified Repo could not be found! Can't upload save data. Is it a github repo ? "
                          "Are you sure it exists ?")


            # else its stored localy - we do nothing






    if not found:
        print("Could not Find pymm Server!. Could not download information!")


if __name__ == '__main__':
    # 64gb, 48gb, 32gb, 16gb, 2gb, 1gb, 512mb

    parser = argparse.ArgumentParser(description="Python Minecraft Manager. Manage Digital Ocean Minecraft Server")
    parser.add_argument("--token", "-t", required=True, help="The digital ocean API token")
    parser.add_argument('command', help="How pymm.py should execute", choices=["install", "teardown", "download"])
    parser.add_argument('--size', '-s', help='Specify Digital Ocean Server Size',
                        choices=['64gb','48gb','32gb','16gb','2gb','1gb','512mb'], default='512mb')
    parser.add_argument('--region', '-r', help='Specify Digital Ocean Server Region',
                        choices=['sfo1', 'nyc1', 'nyc2', 'ams1', 'ams2', 'lon1'], default='sfo1')
    #parser.add_argument('--github-repo', help='Specify Github repo for storing and fetching save data', default=None)
    #parser.add_argument('--github-username', help='Username for accessing github', default=None)
    #parser.add_argument('--github-password', help='Password for accessing github', default=None)
    #parser.add_argument('--github-filename', help='Specify which file in the repo to fetch when loading save data.'
    #                                              ' By default the most recent will be selected', default=None)

    args = vars(parser.parse_args())

    # get absolute path to us
    DO_API_TOKEN = args['token']


    # check our conf folder exists and is fine
    print("Validating Configuration Directory")
    if not os.path.isdir(ROOT_DIR + "/conf"):
        os.mkdir(ROOT_DIR + "/conf", 777)

    if args['command'] == 'teardown':
        teardown_server()
    elif args['command'] == 'install':
        teardown_server()
        ip_address = install_server(do_size=args['size'], do_region=args['region'],
                       github=None)
        print("The Server Setup Has Successfully Completed. Connect To The Following IP To Join The Server:")
        print(ip_address)

    elif args['command'] == 'download':
        download_server_info()

    print("Script Execution Complete. Terminating")