# Device ↔ API contract

Firmware lives here (one folder per device type, e.g. `esp32-ambient/`). This file is the contract the backend promises to keep.

## 1. Register a device (once, from your laptop)

```sh
curl -X POST http://<server>:8000/api/v1/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "esp32-room-1", "kind": "ambient", "location": "garage"}'
```

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

- `metric`: `temperature_c`, `humidity_pct`, `pressure_hpa`, `specific_gravity`, `battery_v`
- `recorded_at`: optional ISO-8601 **with offset**. Omit if the device has no NTP/RTC; the server uses receive time. More than 5 minutes in the future → 422.
- 1–500 readings per request. Batch and send every few minutes rather than one request per sample (saves battery).

## Responses
| Status | Meaning | Device should |
|---|---|---|
| 201 | stored | drop from buffer |
| 401 | bad/revoked token | stop, signal error (LED) |
| 422 | invalid payload | drop the batch (retrying won't help), log it |
| 5xx / network error | server down | keep buffer, retry with backoff |

## Hardware notes
- ESP32 + SHT31/SHT4x (temp/humidity) or BME280 (+ pressure). Avoid DHT11/22 for accuracy.
- In-vessel capsules: iSpindel-style devices can post custom HTTP, so they can target this API or a small adapter route. BLE-only devices (e.g. Tilt) need an ESP32 bridge. Add an adapter endpoint only when a real device needs it.
