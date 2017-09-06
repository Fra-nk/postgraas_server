from . import postgres_instance_driver as pg


class DockerBackend(object):
    def __init__(self):
        pass

    def create(self, entity, connection_info):
        return pg.create_postgres_instance(entity.postgraas_instance_name, connection_info)

    def delete(self, entity):
        return pg.delete_postgres_instance(entity.container_id)

    def exists(self, entity):
        return pg.check_container_exists(entity.container_id)