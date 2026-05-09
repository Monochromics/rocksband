# RocksBand

A containerized drum machine built on [Canonical Rocks](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/). Each drum sound is packaged as its own minimal OCI image using a chiseled `bare` base, then triggered on demand through a FastAPI service. Multiple containers can fire simultaneously, mixing audio through the host's PulseAudio socket.

## Architecture

```
rocksband/
├── main.py                          # FastAPI listener service
├── index.html                       # Browser-based drum pad UI
├── requirements.txt                 # Python dependencies
└── build-kit/
    ├── rockcraft.yaml.template      # Shared build template
    ├── build_rocks.sh               # Build orchestrator
    ├── snare-1/
    │   └── snare-1.wav
    ├── kick-1/
    │   └── kick-1.wav
    └── ...
```

Each instrument directory contains a single `.wav` file. The build script generates a `rockcraft.yaml` from the shared template, packs it into a `.rock` archive, and imports it into Podman as `localhost/<instrument>:1.0`.

The rocks use a `bare` base with Chisel slices and `pulseaudio-utils` to keep the image as small as possible. The entrypoint calls `paplay` directly against the `.wav` file, bypassing Pebble entirely for minimal startup latency.

## Prerequisites

- Ubuntu 24.04 (or compatible)
- [Rockcraft](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/how-to/get-started/)
- [Podman](https://podman.io/)
- Python 3.10+
- PulseAudio or PipeWire (with PulseAudio compatibility)

## Building the Rocks

Place `.wav` files into named subdirectories under `build-kit/`. The directory name becomes the instrument name.

```
cd build-kit
mkdir hi-hat
cp /path/to/hi-hat.wav hi-hat/
```

Generate configs only (no packing):

```
./build_rocks.sh
```

Pack all instruments and import them into Podman:

```
./build_rocks.sh --pack
```

The script will skip any instrument whose `.rock` file is already newer than both the `.wav` source and the template.

## Running the Listener

Set up a virtual environment and install dependencies:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Start the server:

```
uvicorn main:app --host 127.0.0.1 --port 5050
```

Open `http://localhost:5050` in a browser. The drum pad UI will display a button for each instrument that is both built in Podman and present in `build-kit/`.

## API

| Method | Endpoint              | Description                              |
|--------|-----------------------|------------------------------------------|
| GET    | `/`                   | Serves the drum pad HTML interface       |
| GET    | `/instruments`        | Lists available instruments as JSON      |
| POST   | `/play/{instrument}`  | Triggers a container for the instrument  |

The `/play` endpoint validates the instrument name against loaded Podman images before execution. Requests are fire-and-forget; the API returns immediately while the container plays audio in the background.

## Running a Container Manually

If you want to trigger a sound outside of the API:

```
podman run --rm \
  -v /run/user/$(id -u)/pulse/native:/tmp/pulse-socket \
  -e PULSE_SERVER=unix:/tmp/pulse-socket \
  localhost/snare-1:1.0
```

## How the Rocks Work

The chiseled images use a `bare` base with only the slices and packages needed to run `paplay`:

- `base-files_base` and `libc6_libs` for the minimal runtime
- `pulseaudio-utils` for the `paplay` binary
- Manual `usrmerge` symlinks so the dynamic linker resolves correctly
- A minimal `/etc/group` with the `audio` group for ALSA IPC

Audio is routed through the host's PulseAudio socket rather than raw ALSA, which allows multiple containers to play concurrently without exclusive hardware access.

## License

Apache-2.0
