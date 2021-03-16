# snapshot-proxy-cam

Proxy Cam for (currently) shitty W5 (need fallbacked because doesnt support officialy snapshot endpoint and so don't want to fix repetitive E500)

Extended for funny features

See docker-compose.yml

For RTSP proxy, see https://github.com/aler9/rtsp-simple-server

## Routes

`/{camNames,...}/{sourceType}/{size}.{format}{?chg_cam_interval,chg_frame_interval}`

For example :
- `/cam1/auto/small.jpg` for an auto small JPG
- `/cam1/raw-rtsp/big.jpg` for an big JPG from rtsp stream
- `/cam1,cam2/auto/small.mjpg` for small motion JPG with cam1 and cam2
- `/*/raw-rtsp/small.mjpg` for small motion JPG with all cams using RTSP stream
