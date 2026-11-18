"""
Example 11 – A REST API with FastAPI that stores data in Redis

FastAPI builds web APIs from ordinary Python functions with type hints:
  - type hints + Pydantic models  -> automatic validation of input data
  - `async def` endpoints         -> many requests handled concurrently (example 7)
  - interactive documentation     -> http://localhost:3033/docs

Endpoints:
    GET    /                 -> "OK"
    GET    /health           -> checks the connection to Redis
    POST   /readings         -> create a reading
    GET    /readings         -> list all readings
    GET    /readings/{reading_id}  -> get one reading
    PUT    /readings/{reading_id}  -> replace a reading
    DELETE /readings/{reading_id}  -> delete a reading

How the data is stored in Redis:
    readings:next_id   STRING  a counter used to generate new reading ids
    readings           HASH    field = reading id, value = the reading as a JSON string
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

READINGS_KEY = "readings"
NEXT_ID_KEY = "readings:next_id"

db = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

DeviceId = Annotated[
    str, 
    Field(min_length=1, max_length=100, examples=["device-123"])
]

class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # forbid extra fields in the input JSON
    device_id: DeviceId
    temperature: float = Field(ge=-100, le=100, examples=[22.5])  # ge = "greater or equal", le = "less or equal"
    pressure: float = Field(ge=300, le=1100, examples=[1013.25])
    humidity: float = Field(ge=0, le=100, examples=[45.0])

class Reading(ReadingIn):
    id: int
    recorded_at: datetime = Field(default_factory=datetime.utcnow, examples=["2024-06-01T12:34:56Z"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.ping()             # fail fast if Redis is not reachable
    yield
    await db.aclose()           # close the connections cleanly

app = FastAPI(
    title="Weather Monitoring System API",
    description="Python + FastAPI + Redis",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/", response_class=PlainTextResponse)
async def root() -> str:
    return "OK"


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await db.ping()
    except redis.RedisError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Redis unavailable: {error}")
    return {"status": "ok", "redis": "ok"}

@app.post("/readings", response_model=Reading, status_code=status.HTTP_201_CREATED)
async def create_reading(reading_in: ReadingIn) -> Reading:
    # Example:
    #   curl -X POST http://localhost:3033/readings \
    #     -H "Content-Type: application/json" \
    #     -d '{"device_id": "device-123", "temperature": 22.5, "pressure": 1013.25, "humidity": 45.0}'
    reading_id = await db.incr(NEXT_ID_KEY)                  # atomic: no two items get the same id
    reading = Reading(id=reading_id, **reading_in.model_dump())
    await db.hset(READINGS_KEY, str(reading_id), reading.model_dump_json())
    return reading

@app.get("/readings", response_model=list[Reading])
async def list_readings() -> list[Reading]:
    stored = await db.hgetall(READINGS_KEY)                   # {"1": "{...json...}", "2": ...}
    readings = [Reading.model_validate_json(value) for value in stored.values()]
    return sorted(readings, key=lambda reading: reading.id)

@app.get("/readings/{reading_id}", response_model=Reading)
async def get_reading(reading_id: int) -> Reading:
    stored = await db.hget(READINGS_KEY, str(reading_id))
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Reading {reading_id} not found")
    return Reading.model_validate_json(stored)

@app.put("/readings/{reading_id}", response_model=Reading)
async def update_reading(reading_id: int, reading_in: ReadingIn) -> Reading:
    if not await db.hexists(READINGS_KEY, str(reading_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Reading {reading_id} not found")
    reading = Reading(id=reading_id, **reading_in.model_dump())
    await db.hset(READINGS_KEY, str(reading_id), reading.model_dump_json())
    return reading

@app.delete("/readings/{reading_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reading(reading_id: int) -> None:
    deleted = await db.hdel(READINGS_KEY, str(reading_id))      # number of removed fields: 0 or 1
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Reading {reading_id} not found")