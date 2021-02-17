# snapshot-proxy-cam
Proxy Cam for (currently) shitty W5 (need fallbacked because doesnt support officialy snapshot endpoint and so don't want to fix repetitive E500)

See docker-compose.yml

## Routes

- RAW : only capture image
    - /:cam/raw/small-rtsp
    - /:cam/raw/big-rtsp
    - /:cam/raw/small-jpg
    - /:cam/raw/big-jpg
- Auto: Target-driven routes with fallbacked captures (faster as possible)
    - /:cam/auto/big : big-jpg or resized small-jpg or big-rtsp
    - /:cam/auto/small : small-jpg or small-rtsp
    - /:cam/auto/medium : like big but resized to medium
