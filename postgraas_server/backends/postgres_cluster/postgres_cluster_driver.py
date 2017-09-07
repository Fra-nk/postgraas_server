import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def _create_pg_connection(config):
    return psycopg2.connect(
        database=config['database'],
        user=config['username'],
        host=config['host'],
        port=config['port'],
        password=config['password'],
    )


def check_db_exists(db_name, config):
    con = _create_pg_connection(config)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='{}';".format(db_name))
    return cur.fetchone() is not None


def create_postgres_db(postgraas_instance_name, connection_dict, config):
    con = _create_pg_connection(config)
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    create_role = "CREATE USER {db_username} WITH PASSWORD '{db_pwd}';".format(**connection_dict)
    create_database = "CREATE DATABASE {db_name}".format(**connection_dict)
    try:
        cur.execute(create_role)
        cur.execute(create_database)
    except psycopg2.ProgrammingError as e:
        raise ValueError(e.args[0])


def delete_database(db_name, config):
    con = _create_pg_connection(config)
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute("DROP DATABASE {};".format(db_name))


def delete_user(username, config):
    con = _create_pg_connection(config)
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()
    cur.execute("DROP USER {};".format(username))
