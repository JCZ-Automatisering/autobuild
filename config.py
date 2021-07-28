class Config:
    def __init__(self):
        self.hostname = None
        self.docker_image = None
        self.extra_docker_run_args = None

        self.docker_file = "Dockerfile"
        self.jenkins_file = "Jenkinsfile"

        self.docker_name = "autobuild"

        self.extra_volumes = []

        self.skip = []

        self.set_environment_variables = {}
        self.environment_variables_pass_through = ()

        self.volume_one_up = False

    def dump_config(self):
        print("Configuration:\n")
        for item in self.__dict__.keys():
            print("\t%s = %s" % (item, getattr(self, item)))

    def load_config(self, section):
        pass
