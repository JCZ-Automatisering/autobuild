class Config:
    def __init__(self):
        self.hostname = None
        self.docker_image = None
        self.extra_docker_run_args = None

        self.docker_file = "Dockerfile"
        self.jenkins_file = "Jenkinsfile"

        self.docker_name = "autobuild"

        self.extra_volumes = []

    def dump_config(self):
        print("Configuration:\n")
        for item in self.__dict__.keys():
            print("\t%s = %s" % (item, getattr(self, item)))
