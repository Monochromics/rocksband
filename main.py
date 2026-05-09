import asyncio
import configparser
import json
import os
import pathlib
import re
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse

# Load configuration
CONFIG_PATH = pathlib.Path(__file__).parent / "rocksband.conf"
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

SERVER_HOST = config.get("server", "host", fallback="127.0.0.1")
SERVER_PORT = config.getint("server", "port", fallback=5050)
IMAGE_PREFIX = config.get("podman", "image_prefix", fallback="localhost")
IMAGE_TAG = config.get("podman", "image_tag", fallback="1.0")

BUILD_KIT_DIR = pathlib.Path(__file__).parent / "build-kit"

app = FastAPI(title="RocksBand Listener")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    try:
        with open("index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html not found!</h1>"

async def get_available_instruments():
    """Queries Podman for loaded images, filtered to only those with a matching build-kit directory."""
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
            prefix = IMAGE_PREFIX
            tag = IMAGE_TAG
            pattern = re.compile(rf"^{re.escape(prefix)}/([^:]+):{re.escape(tag)}$")
            for img in images:
                names = img.get("Names", [])
                for name in names:
                    match = pattern.match(name)
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
    image = f"{IMAGE_PREFIX}/{instrument}:{IMAGE_TAG}"
    # Construct the podman run command
    cmd = [
        "podman", "run", "--rm",
        "-v", f"/run/user/{uid}/pulse/native:/tmp/pulse-socket",
        "-e", "PULSE_SERVER=unix:/tmp/pulse-socket",
        image
    ]

    # Spawn the process asynchronously
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )

    # We don't await process.wait() to ensure fire-and-forget latency
    return {"status": "playing", "instrument": instrument, "pid": process.pid}

if __name__ == "__main__":
    # pyrefly: ignore [missing-import]
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
