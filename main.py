import cv2, os, socketserver, http.server, urllib.parse, requests
import numpy as np

## ONLY FOR my stupid W5 but updatable to accept every cam ;)
def load_config():

    env_camera = {}

    for k, v in os.environ.items():
        if k[0:7] == 'CAMERA_':
            name, *rest = k[7:].split('_')
            name = name.lower()
            rest = '_'.join(rest).lower()

            if name not in env_camera:
                env_camera[name] = {}

            env_camera[name][rest] = v

    config = {}

    for name in env_camera:
        values = env_camera[name]

        SMALL_RTSP='rtsp://' + values['host'] + '/live/ch1'
        SMALL_JPG='http://' + values['host'] + '/api/v1/snap.cgi?chn=1'
        BIG_RTSP='rtsp://' + values['host'] + '/live/ch0'
        BIG_JPG='http://' + values['host'] + '/api/v1/snap.cgi?chn=0'

        if 'rtsp_token' in values != None:
            SMALL_RTSP += '?token=' + values['rtsp_token']
            BIG_RTSP += '?token=' + values['rtsp_token']


        config[name] = {
            'small_rtsp': SMALL_RTSP,
            'small_jpg': SMALL_JPG,
            'big_rtsp': BIG_RTSP,
            'big_jpg': BIG_JPG
        }

    return config

cameras = load_config()

BIG_SIZE=(1920, 1080) # W5 CH0
MEDIUM_SIZE=(1280, 720) # BETWEEN
SMALL_SIZE=(768, 432) # W5 CH1
JPG_COMPRESSION=75 # W5 compression

def capture_rtsp(url, raw = False):
    capture = cv2.VideoCapture(url)
    frame_width = int(capture.get(3))
    frame_height = int(capture.get(4))
    (status, frame) = capture.read()
    if raw == True:
        return frame
    cap = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPG_COMPRESSION])[1]
    capture.release()
    return cap

def capture_jpg(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def capture_fallbacks(lambdas):
    for _lambda in lambdas:
        try:
            return _lambda()
        except Exception as inst:
            print('WRN ' + str(inst))

def resize(capture, size, raw = False):
    if raw == True:
        image = capture
    else:
        image = cv2.imdecode(np.asarray(bytearray(capture), dtype="uint8"), cv2.IMREAD_COLOR)

    return cv2.imencode('.jpg', cv2.resize(image, size), [int(cv2.IMWRITE_JPEG_QUALITY), JPG_COMPRESSION])[1]

class InvalidPathException(Exception):
    pass

def capture_auto_route(camera, path):
    if path == 'raw/small-rtsp':
        return capture_rtsp(camera['small_rtsp'])
    if path == 'raw/big-rtsp':
        return capture_rtsp(camera['big_rtsp'])
    if path == 'raw/small-jpg':
        return capture_jpg(camera['small_jpg'])
    if path == 'raw/big-jpg':
        return capture_jpg(camera['big_jpg'])
    if path == 'auto/big':
        return capture_fallbacks([
            lambda: capture_jpg(camera['big_jpg']),
            lambda: resize(capture_jpg(camera['small_jpg']), BIG_SIZE),
            lambda: capture_rtsp(camera['big_rtsp'])
        ])
    if path == 'auto/small':
        return capture_fallbacks([
            lambda: capture_jpg(camera['small_jpg']),
            lambda: capture_rtsp(camera['small_rtsp'])
        ])
    if path == 'auto/medium':
        return capture_fallbacks([
            lambda: resize(capture_jpg(camera['big_jpg']), MEDIUM_SIZE),
            lambda: resize(capture_jpg(camera['small_jpg']), MEDIUM_SIZE),
            lambda: resize(capture_rtsp(camera['big_rtsp'], True), MEDIUM_SIZE, True)
        ])
    raise InvalidPathException('Invalid path')

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if (self.path == '/favicon.ico'):
            print('Skipped')
            return

        camera_name, *route_parts = urllib.parse.urlparse(self.path).path[1:].split('/')
        route = '/'.join(route_parts)

        if camera_name not in cameras:
            self.send_response(404)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes('Camera not found', 'utf8'))
            print('CAMERA NOT FOUND')
            return

        try:
            data = capture_auto_route(cameras[camera_name], route)
            self.send_response(200)
            self.send_header('Content-type','image/jpg')
            self.end_headers()
            self.wfile.write( data )
        except InvalidPathException as inst:
            self.send_response(404)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str('Invalid Path'), 'utf8'))
            print('InvalidPathException')
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            # Don't write exception in output as can be used as public proxy and can output credentials/tokens
            self.wfile.write(bytes(str('Internal Error'), 'utf8'))
            print('ERROR ' + str(inst))

httpd = socketserver.ThreadingTCPServer(('', 8080), Handler)
try:
   print('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
print('Ended')
