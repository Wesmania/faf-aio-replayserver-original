import os
import pytest
from replayserver.bookkeeping.database import Database
from replayserver.errors import BookkeepingError


# TODO - turn this into a fixture, add setting up faf-stack to docker
docker_db_config = {
    "config_db_host": os.environ.get("FAF_STACK_DB_IP", "172.19.0.2"),
    "config_db_port": 3306,
    "config_db_user": "root",
    "config_db_password": "banana",
    "config_db_name": "faf"
}


# TODO - no tests modifying the db just yet until we set up a db reset fixture
@pytest.mark.asyncio
async def test_database_ok_query():
    db = Database.build(**docker_db_config)

    await db.start()
    result = await db.execute('SELECT * FROM login')
    assert 1 in [r['id'] for r in result]
    await db.close()


@pytest.mark.asyncio
async def test_database_bad_query():
    db = Database.build(**docker_db_config)

    await db.start()
    with pytest.raises(BookkeepingError):
        await db.execute('SELECT * glablagradargh')
    await db.close()


@pytest.mark.asyncio
async def test_database_query_at_bad_time():
    db = Database.build(**docker_db_config)

    with pytest.raises(BookkeepingError):
        await db.execute('SELECT * FROM login')
    await db.start()
    await db.close()
    with pytest.raises(BookkeepingError):
        await db.execute('SELECT * FROM login')
