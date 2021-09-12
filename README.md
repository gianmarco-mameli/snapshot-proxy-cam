# snapshot-proxy-cam

Proxy Cam for (currently) shitty W5 (need fallbacked because doesnt support officialy snapshot endpoint and so don't want to fix repetitive E500)

Ensure a standart, unique endpoint, and stable as possible API to get cams snapshots thanks to the fallbacks (the main idea is to try to fetch a jpg on the cam jpg API and then extract image from RTSP if error => What happened a LOT with Wanswiew, and now they have removed the jpg endpoint ...).

See docker-compose.yml

For RTSP proxy, see https://github.com/aler9/rtsp-simple-server

## Routes

`/{camName}/{sourceType}/{size}.{format}`

For example :
- `/cam1/auto/small.jpg` for an auto small JPG
- `/cam1/raw-rtsp/big.jpg` for an big JPG from rtsp stream
