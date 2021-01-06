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

The following environment variables can be used to control certain behaviour of the autobuild script:

|name|Purpose|Explanation|Example
|----|-------|-----------|-------
|DOCKERFILE<br>JENKINSFILE|Specify different Dockerfile<br>Specify different Jenkinsfile|Use these variables combined (mandatory) to skip the values from the `autobuild.ini` config file|DOCKERFILE=directory/Dockerfile \ JENKINSFILE=directory/Jenkinsfile \ ./autobuild.py
|STEP|Run just one Jenkinsfile step|Allow the operator to run just one step from the Jenkinsfile|STEP=doxygen ./autobuild.py
|UNTIL|Run until a certain step from the Jenkinsfile|Run all steps until (including) a certain step is found|UNTIL=build ./autobuild.py
|SKIP|Skip one or more steps from the Jenkinsfile|Allow skipping certain steps while executing all others|SKIP=doxygen,cppcheck \ ./autobuild.py
|CONTAINER_NAME|Name of the container|Allow to specify a different name for the container while running instead of the default name|CONTAINER_NAME=my_local_build_container|
|NO_DOCKER|Disable use of docker|Allows disabling Docker integration; in that case every command from the Jenkinsfile is executed locally instead of in a container|NO_DOCKER=yes|


## More configuration

The configuration file `autobuild.ini` can also contain the following lines

### dockerimage

When the file contains the line `dockerimage=<image>` the `<image>` is used and pulled using docker without building the `dockerfile=<file>` line.

### environment_variables

When the file contains the line `environment_variables=<list>` the names in this list (, separated) are "relayed" to the Docker instance.
