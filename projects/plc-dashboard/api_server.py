"""
FastAPI Backend for Automation Dashboard
Bridges PLC simulator data to Supabase and provides REST API.
"""

import os
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from plc_simulator import SimplePLC, build_motor_control_plc, build_conveyor_plc, build_traffic_light_plc, SignalState

app = FastAPI(title="Automation Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global PLC instances
plcs = {
    "motor": build_motor_control_plc(),
    "conveyor": build_conveyor_plc(),
    "traffic": build_traffic_light_plc(),
}


class PLCScanRequest(BaseModel):
    cycles: int = 10


class InputToggle(BaseModel):
    name: str
    state: bool


@app.get("/")
def read_root():
    return {"status": "running", "plcs": list(plcs.keys())}


@app.get("/plc/{plc_name}/status")
def get_plc_status(plc_name: str):
    if plc_name not in plcs:
        raise HTTPException(status_code=404, detail="PLC not found")
    
    plc = plcs[plc_name]
    return {
        "name": plc_name,
        "scan_count": plc.scan_count,
        "inputs": {k: v.state.value for k, v in plc.inputs.items()},
        "outputs": {k: v.state.value for k, v in plc.outputs.items()},
    }


@app.post("/plc/{plc_name}/scan")
def scan_plc(plc_name: str, request: PLCScanRequest):
    if plc_name not in plcs:
        raise HTTPException(status_code=404, detail="PLC not found")
    
    plc = plcs[plc_name]
    plc.run(cycles=request.cycles)
    
    return get_plc_status(plc_name)


@app.post("/plc/{plc_name}/input")
def toggle_input(plc_name: str, toggle: InputToggle):
    if plc_name not in plcs:
        raise HTTPException(status_code=404, detail="PLC not found")
    
    plc = plcs[plc_name]
    state = SignalState.ON if toggle.state else SignalState.OFF
    plc.set_input(toggle.name, state)
    
    return get_plc_status(plc_name)


@app.get("/plcs")
def list_plcs():
    return {
        name: {
            "inputs": list(plc.inputs.keys()),
            "outputs": list(plc.outputs.keys()),
        }
        for name, plc in plcs.items()
    }


# Simulated sensor data endpoint (for dashboard demo)
@app.get("/api/sensors")
def get_sensor_data():
    """Generate simulated sensor readings for the dashboard."""
    import random
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "temperature": round(20 + random.uniform(-2, 5), 1),
        "pressure": round(101.3 + random.uniform(-1, 2), 2),
        "motor_rpm": random.randint(1450, 1550),
        "conveyor_speed": round(random.uniform(0.8, 1.2), 2),
        "batch_count": random.randint(0, 10),
        "status": "running" if random.random() > 0.1 else "warning",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
