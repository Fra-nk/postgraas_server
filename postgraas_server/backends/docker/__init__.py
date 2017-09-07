from docker.errors import APIError
from . import postgres_instance_driver as pg
from ..exceptions import PostgraasApiException


class DockerBackend(object):
    def __init__(self, config=None):
        self.config = config

    def create(self, entity, connection_info):
        try:
            return pg.create_postgres_instance(entity.postgraas_instance_name, connection_info)
        except APIError as e:
            raise PostgraasApiException(str(e))

    def delete(self, entity):
        try:
            return pg.delete_postgres_instance(entity.container_id)
        except APIError as e:
            raise PostgraasApiException(str(e))

    def exists(self, entity):
        return pg.check_container_exists(entity.container_id)

    @property
    def hostname(self):
        return pg.get_hostname()

    @property
    def port(self):
        return pg.get_open_port()

    @property
    def master_hostname(self):
        return '127.0.0.1'