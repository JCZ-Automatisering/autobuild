import platform
import sys
import re
import os
import tempfile


OS_TYPE = platform.system()
OS_TYPE_WINDOWS = "Windows"


def error(msg, return_code=1):
    """
    Print (fatal) error message and exit the process using return code
    :param msg: Message to print before exiting
    :param return_code: Optional return code to exit with
    :return:
    """
    print("FATAL ERROR: %s" % msg)
    sys.exit(return_code)


def strip_comments(text):
    """
    Strip comments from input text
    :param text:
    :return: Stripped text
    """
    return re.sub('//.*?\n|/\*.*?\*/', '', text, flags=re.S)


def line_contains_any_of(the_line, items):
    """
    Determine if any of the members of items is present in the string, if so, return True
    :param the_line: The input line to check against
    :param items: The (list of) check items
    :return: True if at least one item found, False otherwise
    """
    for the_item in items:
        if the_item in the_line:
            return True

    return False


def line_contains_all(the_line, items):
    """
    Determine if all of the members of items are present in the string, if so, return True
    :param the_line: The input line to check against
    :param items: The (list of) check items
    :return: True if all items found, False otherwise
    """
    for the_item in items:
        if the_item not in the_line:
            return False

    return True


def execute(command):
    """
    Execute a command and exit with a fatal error (message) when it fails
    :param command: The command to execute
    :return:
    """
    print("EXEC: %s" % command)
    r = os.system(command)
    if not r == 0:
        print(" FAILURE! (r=%s)" % r)
        print(" COMMAND=\n\n%s\n" % command)
        sys.exit(r)


def __generate_variables_string(environment_variables_pass_through=(),
                                hostname=None):
    result = ""

    for var_item in environment_variables_pass_through:
        var_item_content = os.getenv(var_item)
        if var_item_content:
            result += "-e %s=%s " % (var_item, var_item_content)

    # special variable: hostname
    if hostname:
        result += "-h %s" % hostname

    return result


def execute_in_docker(command, the_config, interactive=False):
    """
    Execute a command in a Docker container
    :param command: The command to execute in the Docker container
    :param the_config: Instance of Config()
    :param interactive: Run with interactive flag (True) or not
    :return:
    """
    with tempfile.NamedTemporaryFile() as tmp_file:
        __tmp_name = tmp_file.name
        with open(__tmp_name, "w") as fp:
            fp.write("#!/bin/sh\n\n%s\n" % command)

        print("command: %s" % command)

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

            for vol_item in the_config.extra_volumes:
                if os.path.exists(vol_item):
                    other_volumes = "-v %s:%s %s" % (vol_item, vol_item, other_volumes)
                else:
                    print("WARNING: requested to add volume %s to container, but directory/file not found!" % vol_item)

            docker_base = "docker run --rm --name {docker_name} {home_vol_and_var}".format(
                docker_name=the_config.docker_name,
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
                         (docker_base, (the_config.extra_docker_run_args if the_config.extra_docker_run_args else ""),
                          the_config.docker_name, command)
            docker_cmd = docker_cmd.format(verbose=verbose_var,
                                           other_volumes=other_volumes,
                                           variables=__generate_variables_string(),
                                           verbose_var=verbose_var)
            if os.getenv("WAIT"):
                input()
            execute(docker_cmd)

