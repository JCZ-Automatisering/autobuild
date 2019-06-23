#!/bin/env python3

import os
import sys
import configparser

CONFIG_FILE = "autobuild.ini"
CONFIG_SECTION = "autobuild"


def error(msg):
    print("FATAL ERROR: %s" % msg)
    sys.exit(1)


if not os.path.exists(CONFIG_FILE):
    error("config file %s does not exist" % CONFIG_FILE)

cp = configparser.ConfigParser()
cp.read(CONFIG_FILE)
config = cp[CONFIG_SECTION]

docker_name = config['name']
docker_file = config['dockerfile']
docker_file_dir = os.path.dirname(docker_file)


def execute(command):
    print("EXEC: %s" % command)
    r = os.system(command)
    if not r == 0:
        print(" FAILURE! (r=%s)" % r)
        print(" COMMAND=\n\n%s\n" % command)
        sys.exit(r)


__tmp_name = "tmp/docker.sh"


def execute_in_docker(command):
    with open(__tmp_name, "w") as fp:
        fp.write("#!/bin/sh\n\n%s\n" % command)

    execute("cat %s | tail -n 1" % __tmp_name)

    command = "/bin/sh %s" % __tmp_name
    HOME = os.getenv("HOME")
    if not HOME:
        error("HOME not set!")

    HOME_VOL_AND_VAR = "-v %s:%s -e HOME=%s" % (HOME, HOME, HOME)
    docker_base = "docker run --rm -it --name %s %s" % (docker_name, HOME_VOL_AND_VAR)
    docker_cmd = "%s -v $PWD:$PWD -w $PWD -u $(id -u) %s %s" % \
                 (docker_base, docker_name, command)
    execute(docker_cmd)

    os.unlink(__tmp_name)


execute("cd %s && docker build -t %s ." % (docker_file_dir, docker_name))
execute("mkdir -p tmp")

if len(sys.argv) > 1:
    if "SHELL" in str(sys.argv[1]).upper():
        execute_in_docker("bash --login")
        exit(0)

steps = []

with open("Jenkinsfile", "r") as jf:
    stage = ""
    line = jf.readline()
    while line:
        line = line.strip()
        if line.startswith("stage('"):
            split = line.split("'")
            stage = split[1]

        if line.startswith("dockerImage.inside("):
            line = jf.readline()    # get next line which contains shell command
            split = line.strip()[4:][:-2]
            steps.append({"name": stage, "command": split})
        line = jf.readline()


if os.getenv("NO_BUILD"):
    for item in steps:
        print("Step: %s" % item['name'])
    print("NO_BUILD set, stopping now")

for item in steps:
    print("Step: %s" % item['name'])
    execute_in_docker(item['command'])
