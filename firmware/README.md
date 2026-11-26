# Device ↔ API contract

This file is the contract the backend promises to keep.

## 1. Register a device (once)

On the dashboard, "Register a device" registers it for the signed-in user and shows its token once. The location and the device belong to the user who creates them, and only that user sees or changes them.

Or with curl, which needs a user token (`$USER_TOKEN`, see "Getting a user token"). An `ambient` device needs the room it measures. Create the location once (`GET /api/v1/locations` lists yours), then register the device with its `id`:

```sh
curl -X POST http://<server>:8000/api/v1/locations \
  -H "Authorization: Bearer $USER_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "garage"}'

curl -X POST http://<server>:8000/api/v1/devices \
  -H "Authorization: Bearer $USER_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "esp32-room-1", "kind": "ambient", "location_id": 1}'
```

`in_vessel` devices may omit `location_id`. Rename or move a device later with `PATCH /api/v1/devices/{id}`. Cut a lost device off with "Revoke" on its device page, or with `POST /api/v1/devices/{id}/revoke`; its readings stay. Re-key a lost or reflashed device with "Re-key" on its device page, or with `POST /api/v1/devices/{id}/rotate`: the new token is shown once, the old one stops working, and a revoked device is re-enabled. Then reflash.

Response contains `token`. It is shown **once**; flash it into the device config (not into git).

### Getting a user token

#### Local provider (default)

With the `.env` from `make setup`, `make dev` / `make up` start a local sign-in provider. Sign in as the username you use on the dashboard, so the devices you register are yours there:

```sh
loc=$(curl -s -o /dev/null -w '%{redirect_url}' -X POST \
  "http://oidc.localhost:9400/default/authorize?client_id=brew-local&response_type=code&redirect_uri=http://localhost:3000/auth/callback&scope=openid&state=x" \
  --data-urlencode username=<name> --data-urlencode claims=)
code=$(printf '%s' "$loc" | sed -n 's/.*[?&]code=\([^&]*\).*/\1/p')
curl -s http://oidc.localhost:9400/default/token -d grant_type=authorization_code -d code="$code" \
  -d redirect_uri=http://localhost:3000/auth/callback -d client_id=brew-local -d client_secret=any
```

`export USER_TOKEN=<access_token>`. `GET /api/v1/me` with it should return your user id.

A dashboard session for scripted checks (PR evidence), with a cookie jar: `curl -c jar -b jar -o /dev/null -w '%{redirect_url}' 'http://localhost:3000/auth/login?returnTo=%2F'` gives the authorize URL; POST `username=<name>&claims=` to it (`curl -c jar -b jar -o /dev/null -w '%{redirect_url}' -d username=<name> -d claims= '<authorize URL>'`), which gives the callback URL; `curl -c jar -b jar -o /dev/null '<callback URL>'`. Then `curl -b jar http://localhost:3000/` is signed in. In a browser, type the username in the form.

#### Auth0 tenant

Use the Auth0 [Device Authorization flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/device-authorization-flow) (check that page if a step below stops working). It gives you a token for your own login, so the devices you register are yours when you later sign in to the frontend. `<tenant>` is the host of the backend's `AUTH_ISSUER`.

1. In the Auth0 dashboard, enable the **Device Code** grant on your application (Application → Settings → Advanced → Grant Types). It is off by default and the request below fails with `unauthorized_client` without it.
2. Ask for a code. `scope` can be `openid`; `audience` is the backend's `AUTH_AUDIENCE`:

   ```sh
   curl -X POST https://<tenant>/oauth/device/code \
     -d client_id=<client id> -d scope=openid -d audience=<AUTH_AUDIENCE>
   ```

   The response has `verification_uri_complete`, `device_code` and `interval`. Open the URI in a browser and approve.
3. Poll every `interval` seconds until it returns an `access_token` (`authorization_pending` and `slow_down` mean wait):

   ```sh
   curl -X POST https://<tenant>/oauth/token \
     -d grant_type=urn:ietf:params:oauth:grant-type:device_code \
     -d device_code=<device_code> -d client_id=<client id>
   ```

4. `export USER_TOKEN=<access_token>`. It expires; repeat the steps for a new one. `GET /api/v1/me` with it should return your user id.

Never use the API's **Test** tab token: it identifies the application, not a person, so what you register with it belongs to nobody who can sign in.

## 2. Send readings

```http
POST /api/v1/readings
Authorization: Bearer <device token>
Content-Type: application/json

{"readings": [
  {"metric": "temperature_c", "value": 19.4, "recorded_at": "2026-10-28T14:00:00Z"},
  {"metric": "humidity_pct", "value": 58.2}
]}
```

- `metric`: one of the names below, and only for a device kind that may send it. Any other kind → 422.

| metric | allowed kinds | range (inclusive) |
|---|---|---|
| `temperature_c` | `ambient`, `in_vessel` | −40 … 125 |
| `humidity_pct` | `ambient` | 0 … 100 |
| `pressure_hpa` | `ambient` | 300 … 1100 |
| `specific_gravity` | `in_vessel` | 0.980 … 1.200 |
| `battery_v` | `ambient`, `in_vessel` | 0 … 5.5 |

Clamp `humidity_pct` to 0–100 before sending (raw SHT4x output can exceed it); out-of-range values reject the whole batch.

- `recorded_at`: optional ISO-8601 **with offset**. Omit if the device has no NTP/RTC; the server uses receive time. More than 5 minutes in the future → 422.
- 1–500 readings per request. Batch and send every few minutes rather than one request per sample (saves battery).
- **Retries are safe.** A reading with `recorded_at` is stored once per device, metric and `recorded_at`, so resending a batch after a lost response adds nothing, and a batch that only partly overlaps stored readings still stores the new ones. A second reading with the same metric and `recorded_at` (a probe pair, or a clock coarser than the sample rate) is dropped, and the response is still 201: keep `recorded_at` unique per metric.
- **Buffering offline:** send `recorded_at` on every buffered reading (sync NTP over the hotspot, keep the RTC running). Readings without it get the receive time and are never deduplicated. Send a backlog larger than 500 readings as several batches; each is safe to retry.

## Responses
| Status | Meaning | Device should |
|---|---|---|
| 201 | stored | drop from buffer |
| 401 | bad, revoked or rotated-out token | stop, signal error (LED) |
| 422 | invalid payload, a metric not allowed for this device's kind, or a value outside its metric's range | drop the batch (retrying won't help), log it |
| 5xx / network error | server down | keep buffer, retry with backoff |

## Hardware notes
- ESP32 + SHT31/SHT4x (temp/humidity) or BME280 (+ pressure). Avoid DHT11/22 for accuracy.
- In-vessel capsules: iSpindel-style devices can post custom HTTP, so they can target this API or a small adapter route. BLE-only devices (e.g. Tilt) need an ESP32 bridge. Add an adapter endpoint only when a real device needs it.
