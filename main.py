import cv2, os, socketserver, http.server, urllib.parse, requests
import numpy as np

## ONLY FOR my stupid W5 but updatable to accept every cam ;)

CAMERA_HOST=os.environ['CAMERA_HOST'] # Can be authority (with user pass)
CAMERA_RTSP_TOKEN=os.environ['CAMERA_RTSP_TOKEN'] if 'CAMERA_RTSP_TOKEN' in os.environ else None

SMALL_RTSP='rtsp://' + CAMERA_HOST + '/live/ch1'
SMALL_JPG='http://' + CAMERA_HOST + '/api/v1/snap.cgi?chn=1'
BIG_RTSP='rtsp://' + CAMERA_HOST + '/live/ch0?token=21a39285884a268d6458e3fdeb08beac'
BIG_JPG='http://' + CAMERA_HOST + '/api/v1/snap.cgi?chn=0'

if CAMERA_RTSP_TOKEN != None:
    SMALL_RTSP += '?token=' + CAMERA_RTSP_TOKEN
    BIG_RTSP += '?token=' + CAMERA_RTSP_TOKEN

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
    return requests.get(url).content

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

def capture_auto_route(path):
    if path == 'snapshot/raw/small-rtsp':
        return capture_rtsp(SMALL_RTSP)
    if path == 'snapshot/raw/big-rtsp':
        return capture_rtsp(BIG_RTSP)
    if path == 'snapshot/raw/small-jpg':
        return capture_jpg(SMALL_JPG)
    if path == 'snapshot/raw/big-jpg':
        return capture_jpg(BIG_JPG)
    if path == 'snapshot/auto/big':
        return capture_fallbacks([
            lambda: capture_jpg(BIG_JPG),
            lambda: resize(capture_jpg(SMALL_JPG), BIG_SIZE),
            lambda: capture_rtsp(BIG_RTSP)
        ])
    if path == 'snapshot/auto/small':
        return capture_fallbacks([
            lambda: capture_jpg(SMALL_JPG),
            lambda: capture_small_rtsp()
        ])
    if path == 'snapshot/auto/medium':
        return capture_fallbacks([
            lambda: resize(capture_jpg(BIG_JPG), MEDIUM_SIZE),
            lambda: resize(capture_jpg(SMALL_JPG), MEDIUM_SIZE),
            lambda: resize(capture_rtsp(BIG_RTSP, True), MEDIUM_SIZE, True)
        ])
    raise Exception('Hum ?')

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        sMac = urllib.parse.urlparse(self.path).path[1:]
        print('Requested ' + sMac)

        if (sMac == 'favicon.ico'):
            print('Skipped')
            return

        try:
            data = capture_auto_route(sMac)
            self.send_response(200)
            self.send_header('Content-type','image/jpg')
            self.end_headers()
            self.wfile.write( data )
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str(inst), 'utf8'))
            print('ERROR ' + str(inst))

httpd = socketserver.TCPServer(('', 8080), Handler)
try:
   print('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
print('Ended')
