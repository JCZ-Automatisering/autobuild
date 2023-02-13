import platform
import sys
import re
import os
import tempfile
import subprocess

import config


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


__TRUE_LIST = ("yes", "true", "1")


def string_to_bool(data: str):
    """
    Try to convert a string to a boolean, defaults to False
    :param data: The data to "scan"
    :return: True if detected true, False otherwise
    """
    if data.lower() in __TRUE_LIST:
        return True
    return False


def strip_comments(text):
    """
    Strip comments from input text
    :param text:
    :return: Stripped text
    """
    result = re.sub('//.*?\n|/\*.*?\*/', '', text, flags=re.S)
    if result.startswith("//"):
        return ""
    return result


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


def execute(command, optional_error_message=None, ignore_error=False):
    """
    Execute a command and exit with a fatal error (message) when it fails
    :param command: The command to execute
    :param optional_error_message: The optional error message to print when the command fails
    :param ignore_error: If true, ignore any non 0 return code and continue
    :return:
    """
    print("EXEC: %s" % command)
    r = os.system(command)
    if not r == 0:
        print(" FAILURE! (r=%s)" % r)
        print(" COMMAND=\n\n%s\n" % command)
        if optional_error_message:
            print(optional_error_message)
        if ignore_error:
            return
        sys.exit(1)


def run_command_get_output(command):
    """
    Execute command and return output (as string)
    :param command: The command to execute
    :return: Result as string
    """
    result = subprocess.run(command.split(" "), stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8').strip()


def __generate_variables_string(environment_variables_pass_through=(),
                                environment_variables_set={},
                                hostname=None):
    """
    Helper function to generate a variables string to pass to Docker. Variables defined in the configuration but not
    set in the environment are not added.
    :param environment_variables_pass_through: The list of environment variable which should be relayed
    :param environment_variables_set: The dict of variables to set if not yet present in environment
    :param hostname: Optional hostname to add
    :return: String with all variables & hostname set (of applicable)
    """
    result = ""

    for var_item in environment_variables_pass_through:
        var_item_content = os.getenv(var_item)
        if var_item_content:
            result += "-e %s=%s " % (var_item, var_item_content)

    for var_item in environment_variables_set:
        check = "%s=" % var_item
        if check not in result:
            result += "-e %s=%s " % (var_item, environment_variables_set[var_item])

    # special variable: hostname
    if hostname:
        result += "-h %s" % hostname

    return result


def __escape_local_volume(the_volume):
    """
    Escape the local volume if running on Windows, otherwise, just return it as is.
    :param the_volume: Volume
    :return: Escaped volume
    """
    if OS_TYPE_WINDOWS in OS_TYPE:
        return str(the_volume).replace("\"", "/")
    return the_volume


def get_user_id():
    return run_command_get_output("id -u")


def get_group_id():
    return run_command_get_output("id -g")


__script_name = "/tmp/the_script"


def execute_in_docker(command, the_config: config.Config, interactive=False, optional_error_message=None,
                      ignore_error=False):
    """
    Execute a command in a Docker container
    :param command: The command to execute in the Docker container
    :param the_config: Instance of Config()
    :param interactive: Run with interactive flag (True) or not
    :param optional_error_message: Optional error message to print when command fails
    :param ignore_error: If true, ignore step error and continue
    :return:
    """
    __tmp_name = ""
    __tmp_fp = None
    try:
        __tmp_fp, __tmp_name = tempfile.mkstemp()
        with open(__tmp_name, "w+", newline="\n") as fp:
            fp.write("#!/bin/sh\n\n%s\n" % command)

        print("command: %s" % command)

        command = "/bin/sh %s" % __tmp_name
        if os.getenv("NO_DOCKER"):
            # just run it without docker...
            execute(command, optional_error_message=optional_error_message)
        else:
            if OS_TYPE_WINDOWS not in OS_TYPE:
                home = os.getenv("HOME")
                if not home:
                    error("HOME not set!")

                home_vol_and_var = "-v {home}:{home} -v /tmp:{home}/.local -e HOME={home}".format(home=home)
            else:
                home_vol_and_var = ""

            other_volumes = ""
            try_volumes = ("/etc/localtime", "/usr/share/zoneinfo", "/etc/passwd", "/etc/group", "/tmp")
            for vol_item in try_volumes:
                if os.path.exists(vol_item):
                    other_volumes = "-v %s:%s %s" %\
                                    (__escape_local_volume(vol_item), vol_item, other_volumes)

            # script "volume":
            other_volumes = "%s -v %s:%s" % (other_volumes, __escape_local_volume(__tmp_name), __script_name)

            for vol_item in the_config.extra_volumes:
                if os.path.exists(vol_item):
                    other_volumes = "-v %s:%s %s" % (__escape_local_volume(vol_item), vol_item, other_volumes)
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

            local_dir = os.getcwd()
            if OS_TYPE_WINDOWS in OS_TYPE:
                # because we are running on windows, we cannot use our path in the container; use something different
                # in that case, /code
                if the_config.volume_one_up:
                    print("Volume one up not yet supported on windows, skipping...")
                remote_dir = "/code"
                work_dir = remote_dir
                # and we also do not specify user settings -u
                user_settings = ""
            else:
                work_dir = local_dir
                if the_config.volume_one_up:
                    remote_dir = os.path.dirname(local_dir)     # one up
                    local_dir = remote_dir
                else:
                    remote_dir = local_dir
                user_id = get_user_id()
                group_id = get_group_id()
                user_settings = f"-u {user_id}:{group_id}"

            if the_config.extra_docker_run_args:
                extra_args = the_config.extra_docker_run_args
            else:
                extra_args = ""
            variables = __generate_variables_string(the_config.environment_variables_pass_through,
                                                    the_config.set_environment_variables)
            docker_cmd = f"{docker_base} {extra_args} {variables} -v {local_dir}:{remote_dir} {verbose_var} " \
                         f"{other_volumes} -w {work_dir} " \
                         f"{user_settings} {the_config.docker_name} /bin/sh {__script_name}"

            if os.getenv("WAIT"):
                print("\npress any key to continue...\n")
                input()
            execute(docker_cmd, optional_error_message=optional_error_message, ignore_error=ignore_error)
    except Exception as e:
        error("Exception during docker assembling/run")
    finally:
        os.close(__tmp_fp)
        os.unlink(__tmp_name)

