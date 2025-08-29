class ExtensionNotValid(Exception):
    """Exception raised when an extension is not valid."""
    def __init__(self, message="extension not valid", extension_name=None,cause=None):
        self.message = message
        self.extension_name = extension_name
        self.cause = cause

class BuildFailedException(Exception):
    """Exception raised when a container build fails."""
    def __init__(self, message="build container image failed", container_name=None, cause=None):
        self.message = message
        self.container_name = container_name
        self.cause = cause
