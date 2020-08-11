import platform
import sys
import re


OS_TYPE = platform.system()


def create_directory(directory):
    if "Windows" in OS_TYPE:
        pass


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

