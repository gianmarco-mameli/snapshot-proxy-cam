import cv2, os, socketserver, http.server, urllib.parse, requests, logging, time, re, sched, threading
import numpy as np

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

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

def capture_rtsp(url, raw = False):
    logging.debug('Capturing RTSP')
    capture = cv2.VideoCapture(url)
    frame_width = int(capture.get(3))
    frame_height = int(capture.get(4))
    (status, frame) = capture.read()
    if not status:
        raise Exception('Empty frame')
    if raw == True:
        return frame
    cap = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPG_COMPRESSION])[1]
    capture.release()
    return cap

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

class Handler(http.server.SimpleHTTPRequestHandler):

    def capture(self, cameras, source_type, size, format, mpg_opts):
        invalids = []
        if format not in ['jpg', 'mjpg']:
            invalids.append('Invalid format')
        if size not in ['small', 'medium', 'big']:
            invalids.append('Invalid size')
        if source_type not in ['auto', 'raw-jpg', 'raw-rtsp']:
            invalids.append('Invalid source type')
        if size == 'medium' and source_type != 'auto':
            invalids.append('Medium size only available in auto source type')
        if len(cameras) > 1 and format != 'mjpg':
            invalids.append('Only 1 camera if not mjpg')

        if invalids:
            self.send_response(400)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str('Invalid Request : ' + ','.join(invalids)), 'utf8'))
            logging.info('Invalid Request')
            return

        try :
            if format == 'jpg':
                self.capture_jpg(cameras[0], source_type, size)
            else:
                self.capture_mpg(cameras, source_type, size, mpg_opts)
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

    def capture_mpg(self, cameras, source_type, size, mpg_opts):
        self.send_response(200)
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
        self.end_headers()

        change_cam_interval = mpg_opts.get('chg_cam_interval') or 5
        image_interval = mpg_opts.get('chg_frame_interval') or 1

        context = {
            'camera': cameras[0],
            'run': True
        }
        def next_camera():
            scheduler = sched.scheduler(time.time)
            def do_next(i):
                if not context['run']:
                    return
                i += 1
                if i >= len(cameras):
                    i = 0
                scheduler.enter(10, 1, do_next, (i,))
                context['camera'] = cameras[i]
            do_next(0)
            scheduler.run()

        next_cam_thread = threading.Thread(target=next_camera)
        next_cam_thread.start()

        last_image_time = time.time()

        while True:
            try:
                img = self.get_image(context['camera'], source_type, size)
                self.wfile.write(bytes(str("--jpgboundary"), 'utf8'))
                self.send_header('Content-type','image/jpeg')
                #self.send_header('Content-length',str(img.len))
                self.end_headers()
                self.wfile.write( img )
                sleep = last_image_time - time.time() + image_interval
                if sleep > 0:
                    time.sleep(sleep)
                last_image_time = time.time()
            except BrokenPipeError as inst:
                logging.info('Disconnected')
                context['run'] = False
                break
            except Exception as inst:
                time.sleep(5)
        return

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
        if source_type == 'raw-rtsp' and size == 'small':
            assert_avail(camera, 'small_rtsp')
            return capture_rtsp(camera['small_rtsp'])
        if source_type == 'raw-rtsp' and size == 'big':
            assert_avail(camera, 'big_rtsp')
            return capture_rtsp(camera['big_rtsp'])
        if source_type == 'raw-jpg' and size == 'small':
            assert_avail(camera, 'small_jpg')
            return capture_jpg(camera['small_jpg'])
        if source_type == 'raw-jpg' and size == 'big':
            assert_avail(camera, 'big_jpg')
            return capture_jpg(camera['big_jpg'])
        if source_type == 'auto' and size == 'big':
            return capture_fallbacks(
                self.build_capture_fallbacks(
                    camera,
                    [
                        ['big_jpg',   lambda: capture_jpg(camera['big_jpg'])],
                        ['small_jpg', lambda: resize(capture_jpg(camera['small_jpg']), BIG_SIZE)],
                        ['big_rtsp',  lambda: capture_rtsp(camera['big_rtsp'])]
                    ]
                )
            )
        if source_type == 'auto' and size == 'small':
            return capture_fallbacks(
                self.build_capture_fallbacks(
                    camera,
                    [
                        ['small_jpg',  lambda: capture_jpg(camera['small_jpg'])],
                        ['small_rtsp', lambda: capture_rtsp(camera['small_rtsp'])],
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
                        ['big_rtsp',  lambda: resize(capture_rtsp(camera['big_rtsp'], True), MEDIUM_SIZE, True)]
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

        camera_names, source_type, size, format = route_match.groups()

        if camera_names == '*':
            camera_names = dict.keys(cameras)
        else:
            camera_names = camera_names.split(',')

        try:
            req_cameras = list(map(lambda camera_name: cameras[camera_name], camera_names))
        except Exception as inst:
            self.send_response(404)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes('Camera not found', 'utf8'))
            logging.info('CAMERA NOT FOUND')
            return

        capture_config = {
            'cameras': req_cameras,
            'source_type': source_type, #'raw-jpg',
            'size': size, #'big'
            'format': format, # 'mjpg'
            'mpg_opts': {
                'chg_cam_interval': int(opts['chg_cam_interval'][0]) if 'chg_cam_interval' in opts else None,
                'chg_frame_interval': float(opts['chg_frame_interval'][0]) if 'chg_frame_interval' in opts else None,
            }
        }

        self.capture(**capture_config)

# class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
#     pass

# httpd = ThreadingHTTPServer(('', 8080), Handler)
httpd = socketserver.ThreadingTCPServer(('', 8080), Handler)
try:
   logging.info('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
logging.info('Ended')
