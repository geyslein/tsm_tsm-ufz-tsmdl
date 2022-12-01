# tsmdl-api

Time series management decoupling layer



## Changes

see [CHANGELOG.md](CHANGELOG.md)

## OpenAPI Spec

see [openapi.json](openapi.json)

### Optional parts

The Observations endpoint is considered to be optional, as it is not
strictly needed to create mappings of the sms measured quantities to
tsm datastreams.

## Example implementation

```
cd exampleimplementation
docker-compose up
```

http://localhost:8000/docs
