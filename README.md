| Master branch  | Develop branch |
| -------------- | -------------- |
| [![Code Health](https://landscape.io/github/realms-team/solserver/master/landscape.svg?style=flat)](https://landscape.io/github/realms-team/solserver/master) | [![Code Health](https://landscape.io/github/realms-team/solserver/develop/landscape.svg?style=flat)](https://landscape.io/github/realms-team/solserver/develop) |

This repo contains the software to run on the solserver. This server:
* runs a JSON API for managers in the field to report data
* stores that data in a database
* runs a web interface for users to see sensor/health data

# Installing and Running

* download a release of this repo as well as a release from the https://github.com/realms-team/sol repo side by side
* Generate a private key `solserver.ppk` and associated (self-signed) certification `solserver.cert` for SSL protection:
    * `openssl genrsa -out solserver.ppk 1024`
    * `openssl req -new -x509 -key solserver.ppk -out solserver.cert -days 1825` (you MUST enter the hostname in the entry "Common Name")
* place both `solserver.ppk` and `solserver.cert` files in the `solserver` directory
* copy `solserver.cert` in the `solmanager` directory as well
* make sure InfluxDB is running on your computer
* double-click/run on `solserver.py` to start the server

* periodic database backup can be done using the following line (every hour)
   * `0 * * * * /path/to/influxd backup -database realms /path/to/backup_dir/$(date +\%y.\%m.\%d-\%H)`

# JSON API documentation

The server offers a JSON API for managers to report data.

The JSON API is available over HTTP, secured using SSL.

Notes: If you want to access the data manually, you need to forge HTTP messages. You can use a plugin
such as [PostMan](http://www.getpostman.com).

## Security

Access over HTTPS is REQUIRED (i.e. non-encrypted HTTP access is not allowed). HTTPS ensures that the communication is encrypted. To authenticate, the client connecting to this API MUST provide a token in each JSON API command. This token (a string) is passed as the custom HTTP header `X-REALMS-Token`.

Before taking any action, the server `MUST` verify that this token is authorized, and issue a 401 "Unauthorized" HTTP status code with no body.

## Compression

The basestation MAY compress the HTTP body before sending it to the server, resulting in reduced bandwidth utilization. When doing so, the basestation MUST use the `gzip` utility and add the `Content-Encoding: gzip` HTTP header to the request.

## Base URI

The base URI of the JSON API is:

```
https://<ip address>/api/v1/
```

Only `v1` of the API is defined in this document. Future revisions of this document MIGHT define new API versions.

## API endpoints

### verifying connectivity

To verify the API is up and running, one can a `POST` command to the API endpoint:

```
/echo.json
```

Any data passed in the payload of body of that request is echoed back untouched

One of the following HTTP status codes is returned:

| Code |               Meaning | Action required                                                             |
|------|-----------------------|-----------------------------------------------------------------------------|
| 200  |                    OK | Success. The body contains the same body as the request                     |
| 401  |          Unauthorized | Invalid `X-REALMS-Token` passed                                             |
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

The body of the reply contains the same contents as the body of the request.

### retrieve status

To retrieve the status of the server, issue a `GET` command to the API endpoint:

```
/status.json
```

No HTTP body is required. A HTTP body can be present, but will be ignored.

One of the following HTTP status codes is returned:

| Code |               Meaning | Action required                                                             |
|------|-----------------------|-----------------------------------------------------------------------------|
| 200  |                    OK | Request received successfully, snapshot is started.                         |
| 401  |          Unauthorized | Invalid `X-REALMS-Token` passed                                             |
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

The HTTP reply contains the following body:

```
{
    "version server":   [1,0,0,0],
    "version Sol":      [1,0,0,0],
    "uptime computer":  "21:01:36 up 21:49,  2 users,  load average: 0.04, 0.08, 0.05",
    "last reboot":      'wtmp begins Wed Aug 12 21:01:33 2015',
    "date":             "Tue, 18 Aug 2015 11:57:56"
    "utc":              1439899076,
    "stats": {
        "NUM_REQ_RX":   1
    },    
}
```

With:
* `software version` is read from the version file of the server Python script.
* `uptime` is the output of the `uptime` Linux command.
* `date` is the output of the `date` Linux command.
* `last reboot` is the output of the `last reboot` Linux command.

### reporting data

To report a new set of objects, issue a `PUT` HTTP request on the API endpoint:

```
/o.json
```

With as body the JSON representation of the objects.

One of the following HTTP status codes is returned:

| Code |               Meaning | Action required                                                             |
|------|-----------------------|-----------------------------------------------------------------------------|
| 200  |                    OK | Objects received successfully. Thank you.                                   |
| 400  |           Bad Request | Something is wrong with your request. The body MIGHT contain a description. |
| 401  |          Unauthorized | Invalid `X-REALMS-Token` passed                                             |
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

# Database

The script uses a mongoDB data on which it will insert JSON objects.
If a database called "realms" does not exists, it will be created.

The data can be obtained either from shell or via the REST API.

## Shell
* Run the mongo script (Ex: C:\mongodb\bin\mongod.exe or /usr/bin/mongo)
* Select the database: ``use realms``
* List all the documents in the *object* collection: ``db.objects.find()``

## REST
* Enable the REST API when starting the mongodb deamon (use ``--rest``)
* Query the server: http://\<server_ip\>:\<REST_port\> (Ex: http://localhost:28017/realms/objects/)

Note: To enable the REST API at statup in Linux, add the following line to the mongodb
configuration: `rest = true`.

# Web Interface

TODO
