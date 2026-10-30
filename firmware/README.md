# Device ↔ API contract

Firmware lives here (one folder per device type, e.g. `esp32-ambient/`). This file is the contract the backend promises to keep.

## 1. Register a device (once, from your laptop)

An `ambient` device needs the room it measures. Create the location once (`GET /api/v1/locations` lists existing ones), then register the device with its `id`:

```sh
curl -X POST http://<server>:8000/api/v1/locations \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "garage"}'

curl -X POST http://<server>:8000/api/v1/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "esp32-room-1", "kind": "ambient", "location_id": 1}'
```

`in_vessel` devices may omit `location_id`. Rename or move a device later with `PATCH /api/v1/devices/{id}`. Cut a lost device off with `POST /api/v1/devices/{id}/revoke`; its readings stay.

Response contains `token`. It is shown **once**; flash it into the device config (not into git).

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
| 401 | bad/revoked token | stop, signal error (LED) |
| 422 | invalid payload, a metric not allowed for this device's kind, or a value outside its metric's range | drop the batch (retrying won't help), log it |
| 5xx / network error | server down | keep buffer, retry with backoff |

## Hardware notes
- ESP32 + SHT31/SHT4x (temp/humidity) or BME280 (+ pressure). Avoid DHT11/22 for accuracy.
- In-vessel capsules: iSpindel-style devices can post custom HTTP, so they can target this API or a small adapter route. BLE-only devices (e.g. Tilt) need an ESP32 bridge. Add an adapter endpoint only when a real device needs it.
