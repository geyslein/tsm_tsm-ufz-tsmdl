FROM python:3.11-alpine

RUN mkdir /buildapp
COPY requirements.txt /buildapp/requirements.txt
RUN mkdir /app
COPY app /app

ENV PGSSLROOTCERT=/etc/ssl/certs/ca-certificates.crt

RUN pip3 install -r /buildapp/requirements.txt
