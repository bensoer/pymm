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

## Install
Execute the following commands:
1. `python install --use pipenv`
2. `pipenv install`
3. `pipenv run python ./pymm.py -h`

The help instructions will now display showing all options
