from . import postgres_cluster_driver as pgcd


class PGClusterBackend(object):
    def __init__(self, config):
        self.config = config

    def create(self, entity, connection_info):
        pgcd.create_postgres_db(entity.db_name, connection_info, self.config)
        return entity.id

    def delete(self, entity):
        pgcd.delete_database(entity.db_name, self.config)
        pgcd.delete_user(entity.username, self.config)

    def exists(self, entity):
        return pgcd.check_db_exists(entity.db_name, self.config)

    @property
    def hostname(self):
        return self.config['host']

    @property
    def port(self):
        return self.config['port']

    @property
    def master_hostname(self):
        return self.hostname
