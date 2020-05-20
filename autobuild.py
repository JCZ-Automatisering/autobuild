#!/usr/bin/env python3

import os
import sys
import configparser
import time
import tempfile


VERSION = 5

AUTOBUILD_LOCAL_FILE = "autobuild.local"
CONFIG_FILE = "autobuild.ini"
CONFIG_SECTION = "autobuild"


print("Running autobuild v%d" % VERSION)


def error(msg):
    print("FATAL ERROR: %s" % msg)
    sys.exit(1)


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
    extra_docker_run_args = None

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
    extra_docker_run_args = config['extra_docker_args']

    EVP = "environment_variables"
    if EVP in config:
        environment_variables_pass_through = config[EVP].split(",")

    DI = "dockerimage"
    if DI in config:
        docker_image = config[DI]
    else:
        docker_image = None


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

    return result


with tempfile.NamedTemporaryFile() as tmp_file:

    __tmp_name = tmp_file.name

    def execute_in_docker(command):
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
            other_volumes = "-v /etc/localtime:/etc/localtime -v /usr/share/zoneinfo:/user/share/zoneinfo -v /tmp:/tmp "
            if sys.stdout.isatty():
                it_flag = "-it"
            else:
                it_flag = ""
            docker_base = "docker run --rm %s --name %s %s" % (it_flag, docker_name, home_vol_and_var)
            verbose_var = os.getenv("VERBOSE", "")
            docker_cmd = "%s {variables} -v $PWD:$PWD -e VERBOSE={verbose} {other_volumes} -v /etc/passwd:/etc/passwd " \
                         "%s " \
                         "-w $PWD " \
                         "-u $(id -u) %s %s" % \
                         (docker_base, (extra_docker_run_args if extra_docker_run_args else ""), docker_name, command)
            docker_cmd = docker_cmd.format(verbose=verbose_var,
                                           other_volumes=other_volumes,
                                           variables=__generate_variables_string())
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
            execute_in_docker("bash --login")
            exit(0)

    steps = []

    with open(jenkins_file, "r") as jf:
        stage = ""
        line = jf.readline()
        while line:
            line = line.strip()
            if line.startswith("#") or line.startswith("//"):
                line = jf.readline()
                continue
            if line.startswith("stage('"):
                split = line.split("'")
                stage = split[1]

            # if line.startswith("dockerImage.inside("):
            if line.find("docker") != -1 and line.find(".inside(") != -1:
                step_counter = 0
                while True:
                    line = jf.readline()    # get next line which contains shell command
                    if "}" in line:
                        break
                    split = line.strip()[4:][:-2]
                    steps.append({"name": "%s:%d" % (stage, step_counter), "command": split})
                    step_counter += 1
            line = jf.readline()

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
