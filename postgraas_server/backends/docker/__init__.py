from . import postgres_instance_driver as pg


class DockerBackend(object):
    def __init__(self):
        pass

    def create(self, instance_name, connection_info):
        return pg.create_postgres_instance(instance_name, connection_info)

    def delete(self, container_id):
        return pg.delete_postgres_instance(container_id)

    def exists(self, container_id):
        return pg.check_container_exists(container_id)