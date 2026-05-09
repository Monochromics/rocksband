import asyncio
import json
import os
import re
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, HTTPException
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

import pathlib

BUILD_KIT_DIR = pathlib.Path(__file__).parent / "build-kit"

async def get_available_instruments():
    """Queries Podman for loaded localhost images, filtered to only those with a matching build-kit directory."""
    process = await asyncio.create_subprocess_exec(
        "podman", "images", "--format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    podman_instruments = set()
    if process.returncode == 0 and stdout:
        try:
            images = json.loads(stdout.decode())
            for img in images:
                names = img.get("Names", [])
                for name in names:
                    # Match localhost/<instrument>:1.0
                    match = re.match(r"^localhost/([^:]+):1\.0$", name)
                    if match:
                        podman_instruments.add(match.group(1))
        except Exception:
            pass

    # Only include instruments that still have a build-kit subdirectory
    build_dirs = {d.name for d in BUILD_KIT_DIR.iterdir() if d.is_dir()} if BUILD_KIT_DIR.is_dir() else set()
    valid = podman_instruments & build_dirs

    return sorted(list(valid))

@app.get("/instruments")
async def list_instruments():
    """Returns a list of all currently loaded rock instruments"""
    instruments = await get_available_instruments()
    return {"instruments": instruments}

@app.post("/play/{instrument}")
async def play_instrument(instrument: str, request: Request):
    """
    Spawns a podman container for the specified instrument in the background.
    Fire-and-forget. Includes security validation.
    """
    # SECURITY: Validate the instrument strictly against loaded images to prevent arbitrary execution
    valid_instruments = await get_available_instruments()
    if instrument not in valid_instruments:
        raise HTTPException(status_code=400, detail="Invalid or unloaded instrument")

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
