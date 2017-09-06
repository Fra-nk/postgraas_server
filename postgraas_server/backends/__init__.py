import ConfigParser

from .docker import DockerBackend

BACKENDS = {'docker': DockerBackend, 'azure': NotImplementedError}


def get_backend(config):
    try:
        backend = config.get('backend', 'type')
    except ConfigParser.NoSectionError:
        backend = 'docker'
    return BACKENDS[backend]()
