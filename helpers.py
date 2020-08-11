import platform
import sys
import re
import os


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
