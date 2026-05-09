import asyncio
import os
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse

app = FastAPI(title="RocksBand Listener")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html not found!</h1>"

@app.post("/play/{instrument}")
async def play_instrument(instrument: str, request: Request):
    """
    Spawns a podman container for the specified instrument in the background.
    Fire-and-forget.
    """
    uid = os.getuid()
    # Construct the podman run command
    cmd = [
        "podman", "run", "--rm",
        "-v", f"/run/user/{uid}/pulse/native:/tmp/pulse-socket",
        "-e", "PULSE_SERVER=unix:/tmp/pulse-socket",
        f"localhost/{instrument}:1.0"
    ]
    
    # Spawn the process asynchronously
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    # We don't await process.wait() to ensure fire-and-forget latency
    return {"status": "playing", "instrument": instrument, "pid": process.pid}
