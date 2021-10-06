import cv2, os, socketserver, http.server, urllib.parse, requests, logging, time, re, sched, threading
import numpy as np
from multiprocessing import Process, Queue

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] [thread=%(threadName)s] %(message)s')

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

        enabled_jpg = True
        enabled_rtsp = True

        if 'enabled_jpg' in values and values['enabled_jpg'] in ['0', 'false']:
            enabled_jpg = False

        if 'enabled_rtsp' in values and values['enabled_rtsp'] in ['0', 'false']:
            enabled_rtsp = False

        SMALL_RTSP='rtsp://' + values['host'] + '/live/ch1'
        SMALL_JPG='http://' + values['host'] + '/api/v1/snap.cgi?chn=1'
        BIG_RTSP='rtsp://' + values['host'] + '/live/ch0'
        BIG_JPG='http://' + values['host'] + '/api/v1/snap.cgi?chn=0'

        if 'rtsp_token' in values != None:
            SMALL_RTSP += '?token=' + values['rtsp_token']
            BIG_RTSP += '?token=' + values['rtsp_token']


        config[name] = {
            'name': name,
            'small_rtsp': SMALL_RTSP if enabled_rtsp else None,
            'small_jpg': SMALL_JPG if enabled_jpg else None,
            'big_rtsp': BIG_RTSP if enabled_rtsp else None,
            'big_jpg': BIG_JPG if enabled_jpg else None
        }

    return config

cameras = load_config()

BIG_SIZE=(1920, 1080) # W5 CH0
MEDIUM_SIZE=(1280, 720) # BETWEEN
SMALL_SIZE=(768, 432) # W5 CH1
JPG_COMPRESSION=75 # W5 compression

def capture_rtsp(url, q, raw = False):
    logging.debug('Capturing RTSP')
    capture = None
    released = False

    try:
        capture = cv2.VideoCapture(url)
        frame_width = int(capture.get(3))
        frame_height = int(capture.get(4))
        (status, frame) = capture.read()
        capture.release()
        released = True
        if not status:
            raise Exception('Empty frame')
        if raw == True:
            return q.put(frame)
        cap = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPG_COMPRESSION])[1]
        return q.put(cap)
    except Exception as inst:
        q.put(inst)
    finally:
        if capture and not released:
            capture.release()

def capture_jpg(url):
    logging.debug('Capturing JPG')
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.content

def capture_fallbacks(lambdas):
    for _lambda in lambdas:
        try:
            return _lambda()
        except Exception as inst:
            logging.info('WRN ' + str(inst))

    raise Exception('No working fallback')

def resize(capture, size, raw = False):
    if raw == True:
        image = capture
    else:
        image = cv2.imdecode(np.asarray(bytearray(capture), dtype="uint8"), cv2.IMREAD_COLOR)

    return cv2.imencode('.jpg', cv2.resize(image, size), [int(cv2.IMWRITE_JPEG_QUALITY), JPG_COMPRESSION])[1]

class Handler(http.server.BaseHTTPRequestHandler):

    def capture(self, camera, source_type, size, format):
        invalids = []
        if format not in ['jpg']:
            invalids.append('Invalid format')
        if size not in ['small', 'medium', 'big']:
            invalids.append('Invalid size')
        if source_type not in ['auto', 'raw-jpg', 'raw-rtsp']:
            invalids.append('Invalid source type')
        if size == 'medium' and source_type != 'auto':
            invalids.append('Medium size only available in auto source type')

        if invalids:
            self.send_response(400)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str('Invalid Request : ' + ','.join(invalids)), 'utf8'))
            logging.info('Invalid Request')
            return

        try :
            if format == 'jpg':
                self.capture_jpg(camera, source_type, size)
            else:
                raise Exception('To handle ?')
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            # Don't write exception in output as can be used as public proxy and can output credentials/tokens
            self.wfile.write(bytes(str('Internal Error'), 'utf8'))
            logging.info('ERROR ' + str(inst))

    def capture_jpg(self, camera, source_type, size):
        image = self.get_image(camera, source_type, size)
        self.send_response(200)
        self.send_header('Content-type','image/jpg')
        self.end_headers()
        self.wfile.write(image)
        logging.info('ENDED')

    def assert_avail(self, camera, what):
        if not self.is_avail(camera, what):
            raise Exception('%s not handled on camera %s' % what % camera['name'])

    def is_avail(self, camera, what):
        if camera[what]:
            return True

        return False

    def build_capture_fallbacks(self, camera, mapping):
        ls = []
        for item in mapping:
            if self.is_avail(camera, item[0]):
                ls.append(item[1])

        if len(ls) == 0:
            raise Exception('Nothing is handled on camera %s' % camera['name'])

        if len(ls) == 1:
            logging.info('No fallback available for camera %s on this mapping' % camera['name'])

        return ls

    def get_image(self, camera, source_type, size):
        def process_capture_rtsp(url, raw=False):
            q = Queue()
            p = Process(target=capture_rtsp, args=(url, q, raw,))
            p.start()

            result = q.get()

            if isinstance(result, Exception):
                raise result

            return result

        if source_type == 'raw-rtsp' and size == 'small':
            self.assert_avail(camera, 'small_rtsp')
            return process_capture_rtsp(camera['small_rtsp'])
        if source_type == 'raw-rtsp' and size == 'big':
            self.assert_avail(camera, 'big_rtsp')
            return process_capture_rtsp(camera['big_rtsp'])
        if source_type == 'raw-jpg' and size == 'small':
            self.assert_avail(camera, 'small_jpg')
            return capture_jpg(camera['small_jpg'])
        if source_type == 'raw-jpg' and size == 'big':
            self.assert_avail(camera, 'big_jpg')
            return capture_jpg(camera['big_jpg'])
        if source_type == 'auto' and size == 'big':
            return capture_fallbacks(
                self.build_capture_fallbacks(
                    camera,
                    [
                        ['big_jpg',   lambda: capture_jpg(camera['big_jpg'])],
                        ['small_jpg', lambda: resize(capture_jpg(camera['small_jpg']), BIG_SIZE)],
                        ['big_rtsp',  lambda: process_capture_rtsp(camera['big_rtsp'])]
                    ]
                )
            )
        if source_type == 'auto' and size == 'small':
            return capture_fallbacks(
                self.build_capture_fallbacks(
                    camera,
                    [
                        ['small_jpg',  lambda: capture_jpg(camera['small_jpg'])],
                        ['small_rtsp', lambda: process_capture_rtsp(camera['small_rtsp'])],
                    ]
                )
            )
        if source_type == 'auto' and size == 'medium':
            return capture_fallbacks(
                self.build_capture_fallbacks(
                    camera,
                    [
                        ['big_jpg',   lambda: resize(capture_jpg(camera['big_jpg']), MEDIUM_SIZE)],
                        ['small_jpg', lambda: resize(capture_jpg(camera['small_jpg']), MEDIUM_SIZE)],
                        ['big_rtsp',  lambda: resize(process_capture_rtsp(camera['big_rtsp'], True), MEDIUM_SIZE, True)]
                    ]
                )
            )

    def do_GET(self):
        if (self.path == '/favicon.ico'):
            logging.info('Skipped')
            return

        logging.info('RECEIVE REQUEST');
        parsed = urllib.parse.urlparse(self.path)
        route_match = re.match(r'^/([^/]+)/([^/]+)/([^/]+)\.(.+)', parsed.path)
        opts = urllib.parse.parse_qs(parsed.query)

        if not route_match:
            self.send_response(404)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str('Invalid Path'), 'utf8'))
            logging.info('Invalid Path')
            return

        camera_name, source_type, size, format = route_match.groups()

        try:
            req_camera = cameras[camera_name]
        except Exception as inst:
            self.send_response(404)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes('Camera not found', 'utf8'))
            logging.info('CAMERA NOT FOUND')
            return

        capture_config = {
            'camera': req_camera,
            'source_type': source_type, #'raw-jpg',
            'size': size, #'big'
            'format': format, # 'jpg'
        }

        self.capture(**capture_config)

# class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
#     pass

# httpd = ThreadingHTTPServer(('', 8080), Handler)
port = int(os.environ.get('PORT', 80))
httpd = socketserver.ThreadingTCPServer(('', port), Handler)
try:
   logging.info('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
logging.info('Ended')
