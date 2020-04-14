# Autobuild

This script/piece of software can be used to parse a Jenkinsfile and run certain steps from it locally in a Docker container based on a dockerfile which can be automatically build.

This tool is created to support testing your work locally before committing and/or pushing it to a remote (server).

## Configuration

The script needs an `autobuild.ini` configuration file. The file looks like this (example):

```ini
[autobuild]
name=<name-of-the-docker-container>
dockerfile=<location-of-the-Dockerfile>
jenkinsfile=<location-of-the-Jenkinsfile>
```

## Suggested usage

Create a git submodule `autobuild` in your archive which contains a Jenkinsfile & Dockerfile and you want to be able to test/execute locally;
Symlink the `autobuild/autobuild.py` to (the root of) your own archive;
Add an `autobuild.ini` file as seen above
Run `./autobuild.py` to execute the steps in a Docker container without Jenkins


## Environment flags

<tbd>