# BasicStream-WebRTC

WebRTC comparison variant of `BasicStream/` (HLS).

## Architecture

- `streamer_webrtc.py`: `picamera2` + hardware `H264Encoder` → `ffmpeg` remux (copy) → RTSP publish
- `mediamtx`: RTSP server + WebRTC gateway + built-in WebRTC viewer page

This typically delivers **lower latency** than HLS without re-encoding.

## Setup (Raspberry Pi)

```bash
sudo apt update
sudo apt install -y ffmpeg python3-pip
python3 -m pip install -r requirements.txt
cp config.example.json config.json
```

## Install `mediamtx`

Download the `mediamtx` binary for your Raspberry Pi and place it at:

- `bin/mediamtx`

Then:

```bash
chmod +x bin/mediamtx
```

## Run

```bash
python3 start_webrtc.py --config config.json
```

Open the WebRTC viewer page:

- `http://<pi-ip>:8889`

Then select/play the `basicstream` path.

# hedgework-ps20-streaming-WebRTC
