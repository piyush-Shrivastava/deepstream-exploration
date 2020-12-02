import cv2
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GObject
import argparse

# Create parser
input_file_parser = argparse.ArgumentParser(description="Path to file")

# add arguments
input_file_parser.add_argument("-path",
                                dest='path',
                                type=str,
                                help='the path to file')

input_file_parser.add_argument("-width",
                                dest='width',
                                type=int,
                                help='width of image')
                        
input_file_parser.add_argument("-height",
                                dest='height',
                                type=int,
                                help='height of image')

args = input_file_parser.parse_args()

input_path = args.path
width = args.width
height = args.height

print("Input file", input_path)
print("Width", width)
print("height", height)

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, **properties):
        super(SensorFactory, self).__init__(**properties)
        self.cap = cv2.VideoCapture(input_path)
        self.number_frames = 0
        self.fps = 30
        self.duration = 1 / self.fps * Gst.SECOND  # duration of a frame in nanoseconds
        self.launch_string = 'appsrc name=source block=true format=GST_FORMAT_TIME ' \
                             'caps=video/x-raw,format=BGR,width={},height={},framerate={}/1 ' \
                             '! videoconvert ! video/x-raw,format=I420 ' \
                             '! x264enc speed-preset=ultrafast tune=zerolatency ! queue ' \
                             '! rtph264pay config-interval=1 name=pay0 pt=96 '.format(width, height, self.fps)
        # streams to gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/test latency=50 ! decodebin ! autovideosink

    def on_need_data(self, src, lenght):
        if self.cap.isOpened() or True:
            ret, frame = self.cap.read()
            if ret:
                data = frame.tostring()
                #print(data)
                buf = Gst.Buffer.new_allocate(None, len(data), None)
                buf.fill(0, data)
                buf.duration = self.duration
                timestamp = self.number_frames * self.duration
                buf.pts = buf.dts = int(timestamp)
                buf.offset = timestamp
                self.number_frames += 1
                retval = src.emit('push-buffer', buf)
                print('pushed buffer, frame {}, duration {} ns, durations {} s'.format(self.number_frames,
                                                                                       self.duration,
                                                                                       self.duration / Gst.SECOND))
                if retval != Gst.FlowReturn.OK:
                    print(retval)
        else:
            self.cap = cv2.VideoCapture(input_path)



    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        self.number_frames = 0
        appsrc = rtsp_media.get_element().get_child_by_name('source')
        appsrc.connect('need-data', self.on_need_data)


class GstServer(GstRtspServer.RTSPServer):
    def __init__(self, **properties):
        super(GstServer, self).__init__(**properties)
        self.factory = SensorFactory()
        self.factory.set_shared(True)
        self.get_mount_points().add_factory("/input", self.factory)
        self.attach(None)


GObject.threads_init()
Gst.init(None)

server = GstServer()

loop = GObject.MainLoop()
loop.run()