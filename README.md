# proxy-cam
Proxy Cam for (currently) shitty W5 (need fallbacked because doesnt support officialy snapshot endpoint and so don't want to fix repetitive E500)

```
env CAMERA_HOST=192.168.1.xxx CAMERA_RTSP_TOKEN=sdfsefsdsdfsf python3 main.py
```

## Routes

- RAW : only capture image
    - /snapshot/raw/small-rtsp
    - /snapshot/raw/big-rtsp
    - /snapshot/raw/small-jpg
    / /snapshot/raw/big-jpg
- Auto: Target-driven routes with fallbacked captures (faster as possible)
    - /snapshot/auto/big : big-jpg or resized small-jpg or big-rtsp
    - /snapshot/auto/small : small-jpg or small-rtsp
    - /snapshot/auto/medium : like big but resized to medium
