#!/bin/sh

cd /app
uvicorn main:app --host 0.0.0.0 $UVICORN_ARGS
