# backend

Weather monitoring backend: devices send weather readings (temperature, pressure, humidity) to a FastAPI service, which stores them in Redis. Grafana reads the data from the REST API and shows it on a dashboard.

## Services

| Service         | URL                        | Description                                  |
|-----------------|----------------------------|----------------------------------------------|
| `web`           | http://localhost:3033      | FastAPI REST API (docs: http://localhost:3033/docs) |
| `redis`         | internal only              | Data storage                                 |
| `redis-insight` | http://localhost:5540      | Web console for browsing Redis data          |
| `grafana`       | http://localhost:3000      | Dashboards (login: `admin` / `admin`)        |

## Running

```bash
docker compose up --build -d
```

Stop everything with `docker compose down`. Add `-v` to also delete the stored data.

## Sending a reading

```bash
curl -X POST http://localhost:3033/readings \
  -H "Content-Type: application/json" \
  -d '{"device_id": "device-123", "temperature": 22.5, "pressure": 1013.25, "humidity": 45.0}'
```

Allowed ranges: `temperature` -100..100, `pressure` 300..1100, `humidity` 0..100. Any other field is rejected with `422`.

To generate some test data from three devices:

```bash
for i in $(seq 1 20); do
  curl -s -X POST http://localhost:3033/readings \
    -H "Content-Type: application/json" \
    -d "{\"device_id\": \"device-$((RANDOM % 3 + 1))\", \"temperature\": $((RANDOM % 15 + 15)).$((RANDOM % 10)), \"pressure\": $((RANDOM % 30 + 995)), \"humidity\": $((RANDOM % 40 + 30))}"
  echo
  sleep 1
done
```

## Grafana

Grafana uses the [Infinity](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) plugin, which reads JSON from any HTTP API. It calls `GET /readings` on the `web` service, so the backend needs no changes.

### What is configured automatically

Everything below is provisioned on startup from the `grafana/` directory, so after `docker compose up` it works without any clicking:

```
grafana/
├── provisioning/
│   ├── datasources/weather-api.yml   # "Weather API" data source -> http://web:3033
│   └── dashboards/weather.yml        # loads dashboards from grafana/dashboards
└── dashboards/
    └── weather.json                  # "Weather readings" dashboard
```

1. Open http://localhost:3000 and log in as `admin` / `admin` (Grafana asks you to change the password, you can skip it).
2. Go to **Dashboards → Weather readings**.

The dashboard has charts for temperature, pressure and humidity (one line per device) and a table with all readings. It refreshes every 5 seconds and shows the last hour by default. Change the time range in the top right corner if you don't see older data.

### Configuring it manually

Use these steps if you want to understand the setup or build your own panels.

**1. Add the data source**

1. Go to **Connections → Data sources → Add data source** and choose **Infinity**.
2. In **URL, Headers & Params**, set **Base URL** to `http://web:3033`.
   Use the service name `web`, not `localhost`: Grafana runs in its own container and reaches the API over the Docker network.
3. In **Security → Allowed hosts**, add `http://web:3033`.
4. Click **Save & test**.

**2. Create a chart**

1. Go to **Dashboards → New → New dashboard → Add visualization** and choose the Infinity data source.
2. Set the query:
   - **Type**: `JSON`
   - **Parser**: `Backend`
   - **Source**: `URL`
   - **Format**: `Table`
   - **Method**: `GET`, **URL**: `/readings`
3. Under **Columns**, add:

   | Selector      | Title       | Format    |
   |---------------|-------------|-----------|
   | `recorded_at` | Time        | Timestamp |
   | `device_id`   | Device      | String    |
   | `temperature` | Temperature | Number    |

4. Open the **Transformations** tab, add **Partition by values** and pick the `Device` field. This splits the data into one series per device.
5. Choose the **Time series** visualization, set the unit (e.g. *Temperature → Celsius (°C)*) and save the dashboard.

Repeat with `pressure` or `humidity` to chart the other values.

### Saving dashboard changes

Changes made in the UI are stored in the `grafana-data` volume. To keep them in the repository, open the dashboard, go to **Edit → Settings → JSON Model**, and copy the JSON into `grafana/dashboards/weather.json`.

### Limitations

`GET /readings` always returns all readings, and Grafana filters them by time on its side. This is fine for testing but will get slow with many thousands of readings. At that point, add filters to the API (e.g. `?since=...&device_id=...`) or store the data in a time-series database such as RedisTimeSeries, InfluxDB or TimescaleDB.
