from . import postgres_cluster_driver as pgcd


class PGClusterBackend(object):
    def __init__(self):
        pass

    def create(self, entity, connection_info):
        return pgcd.create_postgres_db(entity.db_name, connection_info)

    def delete(self, entity):
        return pgcd.delete_postgres_db(entity.db_name)

    def exists(self, entity):
        return pgcd.check_db_exists(entity.db_name)