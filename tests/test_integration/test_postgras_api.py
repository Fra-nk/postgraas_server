import os
import json
import uuid

import docker
import pytest
from mock import patch, MagicMock, Mock

import postgraas_server.backends.docker.postgres_instance_driver as pid
import postgraas_server.backends.postgres_cluster.postgres_cluster_driver as pgcd
import postgraas_server.configuration as configuration
from postgraas_server.backends.exceptions import PostgraasApiException
from postgraas_server.create_app import create_app
from .utils import wait_for_postgres_listening

DOCKER_CONFIG = """
[metadb]
db_name = postgraas
db_username = postgraas
db_pwd = postgraas12
host = localhost
port = 54321

[backend]
type = docker
"""

CLUSTER_CONFIG = """
[metadb]
db_name = postgraas
db_username = postgraas
db_pwd = postgraas12
host = localhost
port = 54321

[backend]
type = pg_cluster
host = localhost
port = 5432
database = {database}
username = {username}
password = {password}
""".format(
    database=os.environ.get('PGDATABASE', 'postgres'),
    username=os.environ.get('PGUSER', 'postgres'),
    password=os.environ.get('PGPASSWORD', 'postgres')
)

CONFIGS = {
    'docker': DOCKER_CONFIG,
    'pg_cluster': CLUSTER_CONFIG,
}


def remove_digits(s):
    return ''.join(c for c in s if not c.isdigit())


def delete_all_test_postgraas_container():
    c = pid._docker_client()
    for container in c.containers.list():
        if container.name.startswith("tests_postgraas_"):
            container.remove(force=True)


def delete_test_database_and_user(db_name, username, config):
    pgcd.delete_database(db_name, config)
    pgcd.delete_user(username, config)


@pytest.fixture(params=['docker', 'pg_cluster'])
def parametrized_setup(request, tmpdir):
    from postgraas_server.management_resources import db
    cfg = tmpdir.join('config')
    cfg.write(CONFIGS[request.param])
    config = configuration.get_config(cfg.strpath)
    this_app = create_app(config)
    this_app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite://"
    this_app.use_reloader = False
    this_app.config['TESTING'] = True
    ctx = this_app.app_context()
    ctx.push()
    db.create_all()
    username, db_name = str(uuid.uuid4()).replace('-', '_'), str(uuid.uuid4()).replace('-', '_')
    yield this_app.test_client(), remove_digits(db_name), remove_digits(username)
    if request.param == 'docker':
        delete_all_test_postgraas_container()
    elif request.param == 'pg_cluster':
        try:
            delete_test_database_and_user(db_name, username, dict(config.items('backend')))
        except Exception:
            pass
    db.drop_all()
    ctx.pop()


@pytest.fixture()
def setup(tmpdir):
    from postgraas_server.management_resources import db
    cfg = tmpdir.join('config')
    cfg.write(CONFIGS['docker'])
    this_app = create_app(configuration.get_config(cfg.strpath))
    this_app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite://"
    this_app.use_reloader = False
    this_app.config['TESTING'] = True
    ctx = this_app.app_context()
    ctx.push()
    db.create_all()
    yield this_app.test_client()
    delete_all_test_postgraas_container()
    db.drop_all()
    ctx.pop()


class TestPostgraasApi:
    def get_postgraas_by_name(self, name, client):
        headers = {'Content-Type': 'application/json'}
        list = client.get('/api/v2/postgraas_instances', headers=headers)
        for instance in json.loads(list.data):
            if instance["postgraas_instance_name"] == name:
                return instance["id"]

    def delete_instance_by_name(self, db_credentials, client):
        id = self.get_postgraas_by_name(db_credentials["postgraas_instance_name"], client)
        db_pwd = db_credentials["db_pwd"]
        headers = {'Content-Type': 'application/json'}
        client.delete(
            '/api/v2/postgraas_instances/' + str(id),
            data=json.dumps({
                'db_pwd': db_pwd
            }),
            headers=headers
        )

    def test_create_postgres_instance(self):
        db_credentials = {
            "db_name": 'test_db_name',
            "db_username": 'test_db_username',
            "db_pwd": 'test_db_pwd',
            "host": pid.get_hostname(),
            "port": pid.get_open_port()
        }
        mock_c = MagicMock()
        mock_c.id = 'fy8rfsufusgsufbvluluivhhvsbr'
        mock_create = Mock(return_value=mock_c)
        with patch.object(docker.models.containers.ContainerCollection, 'create', mock_create):
            result = pid.create_postgres_instance(
                'tests_postgraas_test_instance_name', db_credentials
            )
        assert result == 'fy8rfsufusgsufbvluluivhhvsbr'

    def test_create_postgres_instance_api(self, setup):
        db_credentials = {
            "postgraas_instance_name": "tests_postgraas_test_create_postgres_instance_api",
            "db_name": "test_create_postgres_instance",
            "db_username": "db_user",
            "db_pwd": "secret"
        }
        self.delete_instance_by_name(db_credentials, setup)
        headers = {'Content-Type': 'application/json'}
        result = setup.post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        created_db = json.loads(result.data)
        assert created_db["db_name"] == 'test_create_postgres_instance'
        self.delete_instance_by_name(db_credentials, setup)

    def test_create_docker_fails(self, setup):
        db_credentials = {
            "postgraas_instance_name": "tests_postgraas_test_create_postgres_instance_api",
            "db_name": "test_create_postgres_instance",
            "db_username": "db_user",
            "db_pwd": "secret"
        }
        self.delete_instance_by_name(db_credentials, setup)
        headers = {'Content-Type': 'application/json'}

        def raise_apierror(*args, **kwargs):
            raise PostgraasApiException('let create fail')

        with patch.object(docker.models.containers.ContainerCollection, 'create', raise_apierror):
            result = setup.post(
                '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
            )
        created_db = json.loads(result.data)
        assert 'let create fail' in created_db[
            "msg"
        ], 'unexpected error message for docker create failure'

    def test_delete_postgres_instance_api(self, parametrized_setup):
        db_credentials = {
            "postgraas_instance_name": "tests_postgraas_test_delete_postgres_instance_api",
            "db_name": parametrized_setup[1].decode(),
            "db_username": parametrized_setup[2].decode(),
            "db_pwd": "secret"
        }
        self.delete_instance_by_name(db_credentials, parametrized_setup[0])
        headers = {'Content-Type': 'application/json'}
        result = parametrized_setup[0].post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        created_db = json.loads(result.data)
        # xxx (pmuehlbauer) fix this ugly handling
        try:
            wait_success = wait_for_postgres_listening(created_db['container_id'])
            assert wait_success is True, 'postgres did not come up within 10s (or unexpected docker image log output)'
        except docker.errors.NullResource:
            pass
        delete_result = parametrized_setup[0].delete(
            '/api/v2/postgraas_instances/' + str(created_db["postgraas_instance_id"]),
            data=json.dumps({
                'db_pwd': 'wrong_password'
            }),
            headers=headers
        )
        deleted_db = json.loads(delete_result.data)

        assert deleted_db["status"] == 'failed'
        assert 'password authentication failed' in deleted_db[
            'msg'
        ], 'unexpected message for wrong password'

        def raise_apierror(*args, **kwargs):
            raise PostgraasApiException('let remove fail')

        with patch.object(docker.models.containers.Container, 'remove', raise_apierror):
            with patch.object(pgcd, 'delete_database', raise_apierror):
                delete_result = parametrized_setup[0].delete(
                    '/api/v2/postgraas_instances/' + str(created_db["postgraas_instance_id"]),
                    data=json.dumps({
                        'db_pwd': db_credentials['db_pwd']
                    }),
                    headers=headers
                )
                deleted_db = json.loads(delete_result.data)
                assert deleted_db["status"] == 'failed'
                assert 'let remove fail' in deleted_db[
                    'msg'
                ], 'unexpected error message on docker rm failure'

        delete_result = parametrized_setup[0].delete(
            '/api/v2/postgraas_instances/' + str(created_db["postgraas_instance_id"]),
            data=json.dumps({
                'db_pwd': db_credentials['db_pwd']
            }),
            headers=headers
        )
        deleted_db = json.loads(delete_result.data)
        assert deleted_db["status"] == 'success'

    def test_delete_docker_notfound(self, setup):
        db_credentials = {
            "postgraas_instance_name": "tests_postgraas_test_delete_docker_notfound",
            "db_name": "test_create_postgres_instance",
            "db_username": "db_user",
            "db_pwd": "secret"
        }
        self.delete_instance_by_name(db_credentials, setup)
        headers = {'Content-Type': 'application/json'}
        result = setup.post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        created_db = json.loads(result.data)
        wait_success = wait_for_postgres_listening(created_db['container_id'])
        assert wait_success is True, 'postgres did not come up within 10s (or unexpected docker image log output)'

        def raise_not_found(*args, **kwargs):
            raise docker.errors.NotFound('raise for testing from mock')

        with patch.object(docker.models.containers.ContainerCollection, 'get', raise_not_found):
            res = setup.delete(
                '/api/v2/postgraas_instances/' + str(created_db["postgraas_instance_id"]),
                data=json.dumps({
                    'db_pwd': db_credentials['db_pwd']
                }),
                headers=headers
            )
            res = json.loads(res.data)
        assert res['status'] == 'success'
        assert 'deleted postgraas instance, but container was not found' in res['msg']

    def test_delete_notfound(self, parametrized_setup):
        headers = {'Content-Type': 'application/json'}
        res = parametrized_setup[0].delete(
            '/api/v2/postgraas_instances/123456789',
            data=json.dumps({
                'db_pwd': '123'
            }),
            headers=headers
        )
        res = json.loads(res.data)
        assert res['status'] == 'failed'
        assert "123456789" in res['msg'], 'unexpected error message'

    def test_driver_name_exists(self, setup):
        db_credentials = {
            "db_name": 'test_db_name',
            "db_username": 'test_db_username',
            "db_pwd": 'test_db_pwd',
            "host": pid.get_hostname(),
            "port": pid.get_open_port()
        }
        if pid.check_container_exists('test_instance_name'):
            pid.delete_postgres_instance('test_instance_name')
        id0 = pid.create_postgres_instance('test_instance_name', db_credentials)
        with pytest.raises(ValueError):
            pid.create_postgres_instance('test_instance_name', db_credentials)

        pid.delete_postgres_instance(id0)
        assert pid.check_container_exists(id0) is False, "container exists after it was deleted"

    def test_create_postgres_instance_name_exists(self, parametrized_setup):
        db_credentials = {
            "postgraas_instance_name": "tests_postgraas_my_postgraas_twice",
            "db_name": parametrized_setup[1].decode(),
            "db_username": parametrized_setup[2].decode(),
            "db_pwd": "secret"
        }
        self.delete_instance_by_name(db_credentials, parametrized_setup[0])
        headers = {'Content-Type': 'application/json'}
        parametrized_setup[0].post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        second = parametrized_setup[0].post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        assert second.data == json.dumps(
            {
                "msg": "postgraas_instance_name already exists tests_postgraas_my_postgraas_twice"
            }
        ) + "\n"

        self.delete_instance_by_name(db_credentials, parametrized_setup[0])

    def test_return_postgres_instance_api(self, parametrized_setup):
        db_credentials = {
            u"postgraas_instance_name": u"tests_postgraas_test_return_postgres_instance_api",
            u"db_name": parametrized_setup[1].decode(),
            u"db_username": parametrized_setup[2].decode(),
            u"db_pwd": u"secret"
        }
        self.delete_instance_by_name(db_credentials, parametrized_setup[0])
        headers = {'Content-Type': 'application/json'}
        result = parametrized_setup[0].post(
            '/api/v2/postgraas_instances', headers=headers, data=json.dumps(db_credentials)
        )
        created_db = json.loads(result.data)
        created_db_id = created_db['postgraas_instance_id']
        actual = parametrized_setup[0].get(
            'api/v2/postgraas_instances/{}'.format(created_db_id), headers=headers
        )
        assert actual.status_code == 200
        actual_data = json.loads(actual.data)
        actual_data.pop('container_id')
        actual_data.pop('port')
        actual_data.pop('creation_timestamp')
        expected = {
            u'postgraas_instance_name': u'tests_postgraas_test_return_postgres_instance_api',
            u'db_name': parametrized_setup[1].decode(),
            u'username': parametrized_setup[2].decode(),
            u'password': u'',
            u'hostname': parametrized_setup[0].application.postgraas_backend.hostname,
            u'id': created_db_id,
        }
        assert actual_data == expected

        self.delete_instance_by_name(db_credentials, parametrized_setup[0])
