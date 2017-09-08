#from . import postgres_instance_driver as pg
from ..exceptions import PostgraasApiException


class DockerBackend(object):
    def __init__(self, config=None):
        self.config = config

    def create(self, entity, connection_info):
        from docker.errors import APIError
        from . import postgres_instance_driver as pg
        try:
            return pg.create_postgres_instance(entity.postgraas_instance_name, connection_info)
        except APIError as e:
            raise PostgraasApiException(str(e))

    def delete(self, entity):
        from docker.errors import APIError
        from . import postgres_instance_driver as pg
        try:
            return pg.delete_postgres_instance(entity.container_id)
        except APIError as e:
            raise PostgraasApiException(str(e))

    def exists(self, entity):
        from . import postgres_instance_driver as pg
        return pg.check_container_exists(entity.container_id)

    @property
    def hostname(self):
        from . import postgres_instance_driver as pg
        return pg.get_hostname()

    @property
    def port(self):
        from . import postgres_instance_driver as pg
        return pg.get_open_port()

    @property
    def master_hostname(self):
        return '127.0.0.1'
