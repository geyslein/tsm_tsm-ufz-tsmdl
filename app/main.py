"""
Prototype for an tsm mapping api.

The base purpose of this is to have a common interface
to query information about tsm datastreams in the SMS.

For each centre they are organized in datasources (db + server),
things & datastreams themselves.

It is also the question if we need the observations to be
accessible with this api - this depends on the sync mechanism
to the frost server.

The APIs here doesn't include pagination for now.
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg2
import psycopg2.extras
import psycopg2.sql
import psycopg2.errors
import uvicorn

app = FastAPI(version="0.2.0")


class Message(BaseModel):
    detail: str


class Datasource(BaseModel):
    id: str = Field(alias="@iot.id")
    name: str
    description: Optional[str]
    properties: dict

    class Config:
        allow_population_by_field_name = True


class DatasourceList(BaseModel):
    value: List[Datasource]


class Thing(BaseModel):
    id: str = Field(alias="@iot.id")
    name: str
    description: Optional[str]
    properties: dict

    class Config:
        allow_population_by_field_name = True


class ThingList(BaseModel):
    value: List[Thing]


class Datastream(BaseModel):
    id: str = Field(alias="@iot.id")
    name: str
    description: Optional[str]
    properties: dict

    class Config:
        allow_population_by_field_name = True


class DatastreamList(BaseModel):
    value: List[Datastream]


class Observation(BaseModel):
    id: str = Field(alias="@iot.id")
    result_time: datetime = Field(alias="resultTime")
    result: float

    class Config:
        allow_population_by_field_name = True


class ObservationList(BaseModel):
    value: List[Observation]


class DbConnection:
    conn = None

    def _init_connection(self):
        self.conn = psycopg2.connect(
            os.environ.get("DB_URL"),
            connect_timeout=3,
            # https://www.postgresql.org/docs/9.3/libpq-connect.html
            keepalives=1,
            keepalives_idle=20,
            keepalives_interval=2,
            keepalives_count=2
        )

    def get_cursor(self):
        if self.conn is None or self.conn.closed > 0:
            self._init_connection()
        try:
            # Rollback potentially previous transactions to prevent InFailedSqlTransaction exceptions
            self.conn.rollback()
        except BaseException as e:  # pylint: disable=W0718
            logger.warning(e)
            self._init_connection()
        return self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def __init__(self):
        # Open database connection on startup to fail when it's not successful
        self._init_connection()


logger = logging.getLogger(__name__)
conn = DbConnection()


@app.get("/Datasources", response_model=DatasourceList)
def get_datasources():
    """
    Return the datasources in that tsm instance.

    A datasource can be a database for example.
    """
    result = []

    with conn.get_cursor() as cur:
        cur.execute("""
        select schemaname          as id,
               ''                  as name,
               ''                  as description,
               json_build_object() as properties
        from pg_tables t
        where t.tablename = 'thing';
        """)
        for row in cur.fetchall():
            result.append(Datasource(
                id=row.get('id'),
                name=row.get('name'),
                description=row.get('description'),
                properties=row.get('properties')
            ))

    return DatasourceList(value=result)


@app.get(
    "/Datasources({datasource_id})/Things",
    response_model=ThingList,
    responses={"404": {"model": Message}},
)
def get_things(datasource_id: str):
    """
    Return the things of a tsm datasource.

    Things can be measurement configurations, stations, etc.
    """
    # Validate for a valid datasource id
    check_datasource_id(datasource_id)

    result = []

    with conn.get_cursor() as cur:
        cur.execute(psycopg2.sql.SQL("""
        select uuid        as id,
               name        as name,
               description as description,
               properties  as properties
        from {schema}.thing;
        """).format(schema=psycopg2.sql.Identifier(datasource_id)))

        for row in cur.fetchall():
            result.append(Thing(
                id=row.get('id'),
                name=row.get('name'),
                description=row.get('description'),
                properties=row.get('properties')
            ))

    return ThingList(value=result)


def check_datasource_id(datasource_id):
    with conn.get_cursor() as cur:
        cur.execute("""
        select t.schemaname
        from pg_tables t
        where t.tablename = 'thing' and t.schemaname = %(schema)s;
        """, {'schema': datasource_id})
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Datasource not found")


@app.get(
    "/Datasources({datasource_id})/Things({thing_id})/Datastreams",
    response_model=DatastreamList,
    responses={"404": {"model": Message}},
)
def get_datastreams(datasource_id: str, thing_id: str):
    """
    Get the datastreams of a thing.

    A datastream is the series of measurments.
    An example is airtemperature (datastream) of a station (thing).
    """
    # Validate datasource id
    check_datasource_id(datasource_id)

    # Validate thing id
    check_thing_id(datasource_id, thing_id)

    result = []

    with conn.get_cursor() as cur:
        cur.execute(psycopg2.sql.SQL("""
        select d.id,
               d.name,
               d.description,
               json_build_object(
                       'column_headers', json_agg(distinct o.parameters ->> 'column_header'),
                       'position', d.position,
                       'created_at', d.properties ->> 'created_at'
                   ) as properties
        from {schema}.thing t
                 join {schema}.datastream d on t.id = d.thing_id
                 left join {schema}.observation o on d.id = o.datastream_id
        where t.uuid = %(thing_id)s
        group by d.id, d.name, d.description
        order by d.id;
        """).format(schema=psycopg2.sql.Identifier(datasource_id)), {'thing_id': thing_id})

        for row in cur.fetchall():
            result.append(Datastream(
                id=row.get('id'),
                name=row.get('name'),
                description=row.get('description'),
                properties=row.get('properties')
            ))

    return DatastreamList(value=result)


def check_thing_id(datasource_id, thing_id):
    try:
        uuid.UUID(str(thing_id))
    except ValueError as exc:
        raise HTTPException(status_code=406, detail="Thing uuid format not properly") from exc

    with conn.get_cursor() as cur:
        try:
            cur.execute(psycopg2.sql.SQL("""
            select uuid from {schema}.thing where uuid = %(thing_id)s;
            """).format(schema=psycopg2.sql.Identifier(datasource_id)),
                        {'thing_id': thing_id})
        except psycopg2.errors.InvalidTextRepresentation as exc:
            raise HTTPException(status_code=406, detail="Thing uuid format not properly") from exc

        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Thing not found")


def check_datastream_id(datasource_id, thing_id, datastream_id):  # pylint: disable=unused-argument
    pass  # pylint: disable=unnecessary-pass

@app.get(
    "/Datasources({datasource_id})/Things({thing_id})/Datastreams({datastream_id})/Observations",
    response_model=ObservationList,
    responses={"404": {"model": Message}, "501": {"model": Message}},
)
def get_observations(
    datasource_id: str,
    thing_id: str,
    datastream_id: str,
):
    """
    Return the observations of a datastream.

    An observation contains a measured value associated with a timestamp.
    """
    check_datasource_id(datasource_id)
    check_thing_id(datasource_id, thing_id)
    check_datastream_id(datasource_id, thing_id, datastream_id)

    raise HTTPException(status_code=501, detail="Not yet implemented")

    # return ObservationList(value=result_list)


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


if __name__ == "__main__":
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=8000,
                reload=strtobool(os.environ.get("RELOAD", "False"))
                )
