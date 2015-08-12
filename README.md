This repo contains the software to run on the server. This server:
* runs a JSON API for managers in the field to report data
* stores that data in a database
* runs a web interface for users to see sensor/health data

# JSON API

The server offers a JSON API for managers to report data.

The JSON API is available over HTTP, secured using SSL.

## Security

Mutual authentication using SSL is REQUIRED. Prior to communicating between a basestation and the server:
* the certificate of the server MUST be installed on the basestation
* the certificate of the basestation MUST be installed on the server

## Base URI

The base URI of the JSON API is:

```
https://<ip address>/api/v1/
```

Only `v1` of the API is defined in this document. Future revisions of this document MIGHT define new API versions.

## API endpoints

### verifying connectivity

To verify the API is up and running, one can a `GET` command to the API endpoint:

```
/echo.json
```

Any data passed in the payload of body of that request is echoed back untouched

One of the following HTTP status codes is returned:

| Code |               Meaning | Action required                                                             |
|------|-----------------------|-----------------------------------------------------------------------------|
| 200  |                    OK | Success. The body contains the same body as the request                     |
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
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

The HTTP reply contains the following body:

```
{
    'software version': '1.0.2.3' 
    'uptime':           '21:01:36 up 21:49,  2 users,  load average: 0.04, 0.08, 0.05',
    'date':             'Wed Aug 12 21:02:06 UTC 2015',
    'last reboot':      'wtmp begins Wed Aug 12 21:01:33 2015',
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
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

# Database

TODO

# Web Interface

TODO
