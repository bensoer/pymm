# pymm
A Python Minecraft Manager.

pymm allows for the automated creation, teardown and saving of a minecraft server
hosted on digital ocean. The intent is to be able to easily save server state
information upon removal, migration or crashing of the digital ocean server.

Digital Ocean in addition charges per active droplet. To counter this pymm 
is a solution for users to only pay-as-they-play. But not have to deal with
the hassles of continually building and recreating servers.

## Prerequisites
`python3`, with `pipenv` are needed to setup the project

## QuickStart
Execute the following commands:
1. `python install --use pipenv`
2. `pipenv install`
3. `pipenv run python ./pymm.py -h`

The help instructions will now display showing all options

## Setup Server
At minimum execute the following parameters to setup a minecraft server on digital ocean:
```bash
pyenv run python pymm.py --token <digital-ocean-api-token> install
```
This will create a digital ocean droplet with the latest version of 
minecraft on the smallest server size (512mb). Note that it is recommended
by minecraft to has at least 1g (1024mb) of memory when running the server.
You can adjust the size being used with the `--size` parameter. This maps
to digital ocean ram sizes. See help by passing the `-h` for all possible values.
```bash
pyenv run python pymm.py --token <digital-ocean-api-token> install --size 2gb
```
The above example will do the same as the first except create a digital ocean
server with 2 gigs of ram. During initialization of the minecraft server,
the pymm adjusts for the available space and makes sure it can all be possibly
allocated by the minecraft server.

## Teardown Server
After playing the server can be easily torn down with the following command
```bash
pyenv run python pymm.py --token <digital-ocean-api-token> teardown
```
This will deallocate the digital ocean droplet and remove the SSH keys
from the digital ocean account. NOTE this step does not do ANY saving. Any
unsaved content will be lost with the teardown command execution

## Saving and Restoring Content
To keep your content for future executions, execute the download command
to download localy a copy of all the config information the minecraft
server will need to rebuild itself at a later point. Execute the following
command
```bash
pyend run python pymm.py --token <digital-ocean-api-token> download
```
Your data is downloaded and stored in the pymm `conf` directory which is
created upon installing the minecraft server. You can simply leave the data
there or move it to wherever you prefer. NOTE to restore properly the minecraft
server next time - the `conf` directory must be exactly as it is after executing
the download command.

To build a minecraft server using your save data, make sure the `conf` directory
is intact as it was after executing the download command. Then simply execute the
install command from earlier. pymm will check the conf folder for save data
and will make sure it is uploaded and in place when the server is started.

## Coming Soon
- Github Support. Store your save data in a github repo. Simply supply the repo
during install or download and your data will be saved and restored from those
locations! Using Github will also give you the ability to save at multiple points
of your game progression. During install you can specify which restore data to use.