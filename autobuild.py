#!/bin/env python3

import os
import sys
import configparser

CONFIG_FILE = "autobuild.ini"


def error(msg):
    print("FATAL ERROR: %s" % msg)
    sys.exit(1)


if not os.path.exists(CONFIG_FILE):
    error("config file %s does not exist" % CONFIG_FILE)


docker_name = "shared_c_build_local"


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
    docker_cmd = "docker run --rm -it --name %s -v $PWD:$PWD -w $PWD -u $(id -u) %s %s" % \
                 (docker_name, docker_name, command)
    execute(docker_cmd)

    os.unlink(__tmp_name)


execute("cd docker && docker build -t %s ." % docker_name)
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

        if line.startswith("dockerImage.inside()"):
            line = jf.readline()    # get next line which contains shell command
            split = line.strip()[4:][:-2]
            steps.append({"name": stage, "command": split})
        line = jf.readline()


for item in steps:
    print("Step: %s" % item['name'])
    execute_in_docker(item['command'])
