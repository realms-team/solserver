This repo contains the software to run on the server. This server:
* runs a JSON API for managers in the field to report data
* stores that data in a database
* runs a web interface for users to see sensor/health data

# JSON API

The server offers a JSON API for managers to report data.

The JSON API is available over HTTP, secured using SSL.

## Security

Access over HTTPS is REQUIRED (i.e. non-encrypted HTTP access is not allowed). HTTPS ensures that the communication is encrypted. To authenticate, the client connecting to this API MUST provide a token in each JSON API command. This token (a string) is passed as the custom HTTP header `X-REALMS-Token`.

Before taking any action, the server `MUST` verify that this token is authorized, and issue a 401 "Unauthorized" HTTP status code with no body.

## Compression

The basestation MAY compress the HTTP body before sending it to the server, resulting in reduce bandwidth utilization. When doing so, the basestation MUST use the `gzip` utility and add the `Content-Encoding: gzip` HTTP header to the request.

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

mongoDB, inserting JSON objects to database


# Web Interface

TODO
