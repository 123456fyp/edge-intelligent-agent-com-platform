# Deployment Notes

Sync check: verified from the deployment workstation on 2026-07-01.

This project has two processes:

- `data_comm_pc`: ground station GUI and receiver.
- `data_comm_drone`: drone sender. It can run without ROS installed; in that case it sends default disconnected telemetry.

## Windows Local Demo

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe data_comm_pc\main.py
```

Open another PowerShell window in the same directory:

```powershell
.\.venv\Scripts\python.exe data_comm_drone\main.py
```

The PC process listens on:

- UDP `9000` for heartbeat packets.
- TCP `9001` for telemetry packets.

## Real Drone Deployment

Run the PC ground station on the ground-station computer:

```powershell
.\.venv\Scripts\python.exe data_comm_pc\main.py
```

On the drone computer, set the ground-station IP before starting the drone process:

```powershell
$env:GROUND_STATION_IP="192.168.1.117"
.\.venv\Scripts\python.exe data_comm_drone\main.py
```

Optional environment variables:

- `GROUND_STATION_HEARTBEAT_PORT`
- `GROUND_STATION_DATA_PORT`
- `GROUND_STATION_LISTEN_IP`
- `GROUND_STATION_HEARTBEAT_TIMEOUT`
- `DRONE_ID`
- `DRONE_BIND_IP`
- `DRONE_HEARTBEAT_INTERVAL`
- `DRONE_DATA_INTERVAL`

## Stop Processes

Close the ground-station window, or stop by PID:

```powershell
Stop-Process -Id <PID>
```
