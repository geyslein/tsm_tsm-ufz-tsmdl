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

from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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


# FakeDB
db = {
    "influxdb_01": {
        "altPlestlin": {
            "AirTemp": [
                (datetime(year=2022, month=1, day=1), 1.0),
                (datetime(year=2022, month=1, day=2), 2.0),
            ],
            "AirHumidity": [],
            "LeafWetness": [],
            "SoilMosture_0.1m": [],
        },
        "altTellin": {},
        "beestland": {},
        "zeitlow-BF1": {},
    },
    "influxdb_02": {},
    "influxdb_03": {},
    "timescaleDB__db01": {},
    "timescaleDB__db02": {},
}


@app.get("/Datasources", response_model=DatasourceList)
def get_datasources():
    """
    Return the datasources in that tsm instance.

    A datasource can be a database for example.
    """
    result = []
    for key in db.keys():
        result.append(Datasource(id=key, name=key, properties={}))
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
    if not datasource_id in db.keys():
        raise HTTPException(status_code=404, detail="Datasource not found")
    result = []
    for key in db[datasource_id].keys():
        result.append(Thing(id=key, name=key, properties={}))
    return ThingList(value=result)



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
    if not datasource_id in db.keys():
        raise HTTPException(status_code=404, detail="Datasource not found")
    things = db[datasource_id]
    if not thing_id in things.keys():
        raise HTTPException(status_code=404, detail="Thing not found")
    thing = things[thing_id]
    result = []
    for key in thing.keys():
        result.append(Datastream(id=key, name=key, properties={}))
    return DatastreamList(value=result)


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
    if not datasource_id in db.keys():
        raise HTTPException(status_code=404, detail="Datasource not found")
    things = db[datasource_id]
    if not thing_id in things.keys():
        raise HTTPException(status_code=404, detail="Thing not found")
    thing = things[thing_id]
    if not datastream_id in thing.keys():
        raise HTTPException(status_code=404, detail="Datastream not found")
    datastream = thing[datastream_id]

    result_list = []
    idx = 0
    for result_time, result in datastream:
        idx += 1
        include = True
        # TODO Add filters STA style
        if include:
            result_list.append(
                Observation(
                    id=idx,
                    result_time=result_time,
                    result=result,
                )
            )

    return ObservationList(value=result_list)
