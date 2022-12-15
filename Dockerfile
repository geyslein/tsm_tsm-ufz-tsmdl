FROM python:3.11-alpine

RUN mkdir /buildapp
COPY requirements.txt /buildapp/requirements.txt
RUN mkdir /app
COPY app /app

RUN pip3 install -r /buildapp/requirements.txt