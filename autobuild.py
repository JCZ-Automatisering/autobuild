#!/usr/bin/env python3

import helpers
from config import Config

# shortcuts:
from helpers import execute as execute
from helpers import execute_in_docker as execute_in_docker

import os
import sys
import configparser
import tempfile


VERSION = 28

AUTOBUILD_LOCAL_FILE = "autobuild.local"
CONFIG_FILE = "autobuild.ini"
CONFIG_SECTION = "autobuild"

INSIDE_DOCKER_ITEMS = (
    "docker",
    ".inside("
)

the_config = Config()


print("Running autobuild v%d" % VERSION)


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


env_step = os.getenv("STEP")
if env_step and "," in env_step:
    env_steps = env_step.split(",")
else:
    env_steps = None
env_until = os.getenv("UNTIL")
env_skip_data = os.getenv("SKIP", None)
if env_skip_data:
    env_skip = env_skip_data.split(",")
else:
    env_skip = []

the_config.hostname = None
the_config.docker_image = None
the_config.extra_docker_run_args = None


if not os.path.exists(CONFIG_FILE):
    helpers.error("config file %s does not exist" % CONFIG_FILE)

cp = configparser.ConfigParser()
cp.read(CONFIG_FILE)
config = cp[CONFIG_SECTION]

the_config.docker_name = os.getenv("CONTAINER_NAME", config['name'])
the_config.docker_file = os.getenv("DOCKERFILE", config['dockerfile'])
the_config.jenkins_file = os.getenv("JENKINSFILE", config['jenkinsfile'])
if 'extra_docker_args' in config:
    the_config.extra_docker_run_args = config['extra_docker_args']

if 'skip' in config:
    the_config.skip = config['skip'].split(',')
    if len(env_skip) == 0:
        env_skip = the_config.skip

EVP = "environment_variables"
if EVP in config:
    the_config.environment_variables_pass_through = config[EVP].split(",")

SEV = "set_environment_variables"
if SEV in config:
    the_items = config[SEV].split(";")
    for item in the_items:
        split = item.split("=")
        if len(split) == 2:
            name = split[0]
            value = split[1]
            the_config.set_environment_variables[name] = value

VOLS = "extra_volumes"
if VOLS in config:
    the_config.extra_volumes = config[VOLS].split(",")

DI = "dockerimage"
if DI in config:
    the_config.docker_image = config[DI]

if "hostname" in config:
    the_config.hostname = config["hostname"]

VOU = "volume_one_up"
if VOU in config:
    the_config.volume_one_up = helpers.string_to_bool(config[VOU])


# docker_file_dir = os.path.dirname(the_config.docker_file)

if not os.getenv("QUIET"):
    the_config.dump_config()


with tempfile.NamedTemporaryFile() as tmp_file:
    __tmp_name = tmp_file.name

    if the_config.docker_image:
        print("Using configured Docker image %s\n" % the_config.docker_image)
        cmd = "docker pull {docker_image}".format(docker_image=the_config.docker_image)
        execute(cmd)
    else:
        if os.getenv("NO_DOCKER"):
            print("Not building the docker image\n")
        else:
            print("Using locally build Docker image %s\n" % the_config.docker_file)
            cmd = "docker build -t {docker_name} -f {docker_file_name} .".format(
                docker_name=the_config.docker_name, docker_file_name=the_config.docker_file
            )
            execute(cmd)

    if len(sys.argv) > 1:
        the_args = sys.argv[1:]
        the_arg = " ".join(the_args)
        if "SHELL" in str(the_arg).upper():
            execute_in_docker(command="bash --login", the_config=the_config, interactive=True)
            exit(0)
        else:
            execute_in_docker(command=the_arg, the_config=the_config, interactive=False)
            exit(0)

    steps = []

    with open(the_config.jenkins_file, "r") as jf:
        in_script_tag = False
        stage = ""
        while True:
            input_line = jf.readline()
            if not input_line:
                break   # eof
            stripped_line = input_line.strip()

            # print("stage: %s input_line: %s" % (stage, stripped_line))

            line = helpers.strip_comments(stripped_line)
            if line.startswith("#") or line.startswith("//"):
                continue
            if line.startswith("stage('"):
                split = line.split("'")
                stage = split[1]
                in_script_tag = False       # reset
                continue

            if "script {" in line:
                in_script_tag = True
                continue

            if "post {" in line:
                # eof interesting area reached, break the loop.
                break

            # only continue adding any content/commands if we found a script { tag
            if in_script_tag:
                # if line.startswith("dockerImage.inside("):
                if helpers.line_contains_all(line, INSIDE_DOCKER_ITEMS):
                    # run in docker:
                    step_counter = 0
                    while True:
                        input_line = jf.readline()    # get next line which contains shell command
                        stripped_line = input_line.strip()
                        line = helpers.strip_comments(stripped_line)
                        if not line:
                            continue        # empty line, no command here...
                        if "}" in line:
                            break
                        split = line.strip()[4:][:-2]
                        steps.append({"name": "%s:%d" % (stage, step_counter), "stage": stage, "command": split})
                        step_counter += 1
                elif line.startswith("sh("):
                    # interesting line. check
                    sh_line = line[4:-2]        # skip sh(' at the start and ') at the end
                    steps.append({"name": stage, "command_no_docker": sh_line})

    if os.getenv("NO_BUILD"):
        for item in steps:
            the_name = item['name']
            if "command" in item:
                cmd = item['command']
            else:
                cmd = item['command_no_docker']
            print("Step: %s \t\tCommand: %s" % (the_name, cmd))
        print("NO_BUILD set, stopping now")
        exit(0)

    for item in steps:
        execute_this_step = True
        name = item['name']
        if 'stage' in item:
            stage = item['stage']
        else:
            stage = ""
        optional_error_message = "step: {} failed".format(name)

        print("Step: %s" % name)

        if env_steps:
            if stage not in env_steps:
                execute_this_step = False
        else:
            if env_step:
                if env_step.upper() in name.upper():
                    print("Step: %s" % name)
                    execute_in_docker(item['command'], the_config, optional_error_message=optional_error_message)
                else:
                    execute_this_step = False

        for skip_item in env_skip:
            if skip_item and skip_item in name:
                execute_this_step = False
                break

        if execute_this_step:
            if "command_no_docker" in item:
                execute(item["command_no_docker"], optional_error_message=optional_error_message)
            else:
                execute_in_docker(item['command'], the_config, optional_error_message=optional_error_message)
        else:
            print(" skipping step %s as requested" % name)
        if env_until:
            if env_until in name:
                print("Until %s reached. Stopping." % env_until)
                exit(0)

        os.system("sync")

    print("\nautobuild success: ran successfully")
    open(__tmp_name, "w").write("")     # make sure the tmpfile resource manager is able to delete the file
