#!/usr/bin/env python3

import os
import sys
import configparser
import time
import tempfile
import re


VERSION = 11

AUTOBUILD_LOCAL_FILE = "autobuild.local"
CONFIG_FILE = "autobuild.ini"
CONFIG_SECTION = "autobuild"


print("Running autobuild v%d" % VERSION)


def error(msg):
    print("FATAL ERROR: %s" % msg)
    sys.exit(1)


def strip_comments(text):
    return re.sub('//.*?\n|/\*.*?\*/', '', text, flags=re.S)


if os.path.exists(AUTOBUILD_LOCAL_FILE):
    lines = open(AUTOBUILD_LOCAL_FILE, "r").readlines()
    for line in lines:
        split = line.strip().split("=")
        if len(split) == 2:
            var = split[0]
            value = split[1]
            if os.getenv(var):
                print("Not overriding existing environment variable %s" % var)
            else:
                print("Configuring environment variable %s from %s" % (var, AUTOBUILD_LOCAL_FILE))
                os.environ[var] = value


env_dockerfile = os.getenv("DOCKERFILE")
env_jenkinsfile = os.getenv("JENKINSFILE")
env_step = os.getenv("STEP")
env_until = os.getenv("UNTIL")
env_skip = os.getenv("SKIP", "").split(",")

environment_variables_pass_through = []
extra_volumes = []

hostname = None

docker_image = None
extra_docker_run_args = None


if env_dockerfile and not env_jenkinsfile or \
        env_jenkinsfile and not env_dockerfile:
    print("WARNING: you have to specify both DOCKERFILE and JENKINSFILE for this functionality to work!")
    print(" continue in 1 second...")
    time.sleep(1)

if env_dockerfile and env_jenkinsfile:
    print("Using environment settings Dockerfile = %s and Jenkinsfile = %s" %
          (env_dockerfile, env_jenkinsfile))

    docker_file = env_dockerfile
    jenkins_file = env_jenkinsfile
    docker_name = "autobuild_manual"

else:
    print("Using settings from configuration")

    if not os.path.exists(CONFIG_FILE):
        error("config file %s does not exist" % CONFIG_FILE)

    cp = configparser.ConfigParser()
    cp.read(CONFIG_FILE)
    config = cp[CONFIG_SECTION]

    docker_name = config['name']
    docker_file = config['dockerfile']
    jenkins_file = config['jenkinsfile']
    if 'extra_docker_args' in config:
        extra_docker_run_args = config['extra_docker_args']

    EVP = "environment_variables"
    if EVP in config:
        environment_variables_pass_through = config[EVP].split(",")

    VOLS = "extra_volumes"
    if VOLS in config:
        extra_volumes = config[VOLS].split(",")

    DI = "dockerimage"
    if DI in config:
        docker_image = config[DI]

    if "hostname" in config:
        hostname = config["hostname"]


docker_file_dir = os.path.dirname(docker_file)


def execute(command):
    print("EXEC: %s" % command)
    r = os.system(command)
    if not r == 0:
        print(" FAILURE! (r=%s)" % r)
        print(" COMMAND=\n\n%s\n" % command)
        sys.exit(r)


def __generate_variables_string():
    result = ""

    for var_item in environment_variables_pass_through:
        var_item_content = os.getenv(var_item)
        if var_item_content:
            result += "-e %s=%s " % (var_item, var_item_content)

    # special variable: hostname
    if hostname:
        result += "-h %s" % hostname

    return result


with tempfile.NamedTemporaryFile() as tmp_file:

    __tmp_name = tmp_file.name

    def execute_in_docker(command, interactive=False):
        with open(__tmp_name, "w") as fp:
            fp.write("#!/bin/sh\n\n%s\n" % command)

        execute("cat %s | tail -n 1" % __tmp_name)

        command = "/bin/sh %s" % __tmp_name
        if os.getenv("NO_DOCKER"):
            # just run it without docker...
            execute(command)
        else:
            home = os.getenv("HOME")
            if not home:
                error("HOME not set!")

            home_vol_and_var = "-v %s:%s -e HOME=%s" % (home, home, home)
            other_volumes = ""
            try_volumes = ("/etc/localtime", "/usr/share/zoneinfo", "/etc/passwd", "/etc/group", "/tmp")
            for vol_item in try_volumes:
                if os.path.exists(vol_item):
                    other_volumes = "-v %s:%s %s" % (vol_item, vol_item, other_volumes)

            for vol_item in extra_volumes:
                if os.path.exists(vol_item):
                    other_volumes = "-v %s:%s %s" % (vol_item, vol_item, other_volumes)
                else:
                    print("WARNING: requested to add volume %s to container, but directory/file not found!" % vol_item)

            docker_base = "docker run --rm --name {docker_name} {home_vol_and_var}".format(
                docker_name=docker_name,
                home_vol_and_var=home_vol_and_var
            )
            if interactive:
                docker_base = "%s -it" % docker_base
            verbose_var = os.getenv("VERBOSE", None)
            if verbose_var:
                verbose_var = "-e VERBOSE=%s" % verbose_var
            else:
                verbose_var = ""
            docker_cmd = "%s {variables} -v $PWD:$PWD {verbose_var} {other_volumes} " \
                         "%s " \
                         "-w $PWD " \
                         "-u $(id -u):$(id -g) %s %s" % \
                         (docker_base, (extra_docker_run_args if extra_docker_run_args else ""), docker_name, command)
            docker_cmd = docker_cmd.format(verbose=verbose_var,
                                           other_volumes=other_volumes,
                                           variables=__generate_variables_string(),
                                           verbose_var=verbose_var)
            if os.getenv("WAIT"):
                input()
            execute(docker_cmd)


    if docker_image:
        print("Using configured Docker image %s\n" % docker_image)
        cmd = "docker pull {docker_image}".format(docker_image=docker_image)
        execute(cmd)
    else:
        if os.getenv("NO_DOCKER"):
            print("Not building the docker image\n")
        else:
            print("Using locally build Docker image %s\n" % docker_file)
            cmd = "docker build -t {docker_name} -f {docker_file_name} .".format(
                docker_name=docker_name, docker_file_name=docker_file
            )
            execute(cmd)

    execute("mkdir -p tmp")

    if len(sys.argv) > 1:
        if "SHELL" in str(sys.argv[1]).upper():
            execute_in_docker(command="bash --login", interactive=True)
            exit(0)

    steps = []

    with open(jenkins_file, "r") as jf:
        stage = ""
        while True:
            input_line = jf.readline()
            if not input_line:
                break   # eof
            stripped_line = input_line.strip()
            line = strip_comments(stripped_line)
            if line.startswith("#") or line.startswith("//"):
                continue
            if line.startswith("stage('"):
                split = line.split("'")
                stage = split[1]
                continue

            # if line.startswith("dockerImage.inside("):
            if line.find("docker") != -1 and line.find(".inside(") != -1:
                step_counter = 0
                while True:
                    input_line = jf.readline()    # get next line which contains shell command
                    stripped_line = input_line.strip()
                    line = strip_comments(stripped_line)
                    if not line:
                        continue        # empty line, no command here...
                    if "}" in line:
                        break
                    split = line.strip()[4:][:-2]
                    steps.append({"name": "%s:%d" % (stage, step_counter), "command": split})
                    step_counter += 1

    if os.getenv("NO_BUILD"):
        for item in steps:
            print("Step: %s \t\tCommand: %s" % (item['name'], item['command']))
        print("NO_BUILD set, stopping now")
        exit(0)

    for item in steps:
        name = item['name']
        if env_step:
            print('checking step %s' % name)
            if env_step.upper() in name.upper():
                print("Step: %s" % name)
                execute_in_docker(item['command'])
            # else: skip because we are only interested in on "STEP"
        else:
            print("Step: %s" % name)
            execute_this_step = True
            for skip_item in env_skip:
                if skip_item and skip_item in name:
                    execute_this_step = False
                    break
            if execute_this_step:
                execute_in_docker(item['command'])
            else:
                print(" skipping step %s as requested" % name)
            if env_until:
                if env_until in name:
                    print("Until %s reached. Stopping." % env_until)
                    exit(0)

        os.system("sync")

    print("\nautobuild success: ran successfully")
    open(__tmp_name, "w").write("")     # make sure the tmpfile resource manager is able to delete the file
