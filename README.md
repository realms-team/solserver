This repo contains the software to run on the server. This server:
* runs a JSON API for managers in the field to report data
* stores that data in a database
* runs a web interface for users to see sensor/health data

# JSON API

The server offers a JSON API for managers to report data.

The JSON API is available over HTTP, secured using SSL.

## Base URI

The base URI of the JSON API is:

```
https://<ip address>/api/v1/
```

Only `v1` of the API is defined in this document. Future revisions of this document MIGHT define new API versions.

## API endpoints

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

### verifying connectivity

To verify the API is up and running, one can a `GET` command to the API endpoint:

```
/echo
```

Any data passed in the payload of body of that request is echoed back untouched

One of the following HTTP status codes is returned:

| Code |               Meaning | Action required                                                             |
|------|-----------------------|-----------------------------------------------------------------------------|
| 200  |                    OK | Success. The body contains the same body as the request                     |
| 500  | Internal Server Error | Server error. The body MIGHT contain a description.                         |

# Database

TODO

# Web Interface

TODO
