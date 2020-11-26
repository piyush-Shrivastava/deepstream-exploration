#!/usr/bin/env python3

################################################################################
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################

import sys
sys.path.append('../')
import gi
import configparser
gi.require_version('GstRtspServer', '1.0')
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstRtspServer
from gi.repository import GLib
from ctypes import *
import time
import sys
import math
import platform
from common.is_aarch_64 import is_aarch64

sys.path.append('/opt/nvidia/deepstream/deepstream/lib')
# bindings 1.0 might cause some issue while running on Kubernetes. If so, kindly download 0.9 bindings and put it in python folder
# Which can be linked using the command below
#sys.path.append('../../bindings/' + ('jetson' if is_aarch64() else 'x86_64'))

from common.bus_call import bus_call
from common.utils import long_to_int
from common.FPS import GETFPS

import pyds

import argparse



# Global variables

fps_streams={}

MAX_DISPLAY_LEN=64
MAX_TIME_STAMP_LEN=32

PGIE_CLASS_ID_PERSON = 0
# PGIE_CLASS_ID_BICYCLE = 1
# PGIE_CLASS_ID_PERSON = 2
# PGIE_CLASS_ID_ROADSIGN = 3


GST_CAPS_FEATURES_NVMM="memory:NVMM"
pgie_classes_str= ["Face"]

frame_number = 0


# Callback function for deep-copying an NvDsEventMsgMeta struct
def meta_copy_func(data,user_data):
    # Cast data to pyds.NvDsUserMeta
    user_meta=pyds.NvDsUserMeta.cast(data)
    src_meta_data=user_meta.user_meta_data
    # Cast src_meta_data to pyds.NvDsEventMsgMeta
    srcmeta=pyds.NvDsEventMsgMeta.cast(src_meta_data)
    # Duplicate the memory contents of srcmeta to dstmeta
    # First use pyds.get_ptr() to get the C address of srcmeta, then
    # use pyds.memdup() to allocate dstmeta and copy srcmeta into it.
    # pyds.memdup returns C address of the allocated duplicate.
    dstmeta_ptr=pyds.memdup(pyds.get_ptr(srcmeta), sys.getsizeof(pyds.NvDsEventMsgMeta))
    # Cast the duplicated memory to pyds.NvDsEventMsgMeta
    dstmeta=pyds.NvDsEventMsgMeta.cast(dstmeta_ptr)

    # Duplicate contents of ts field. Note that reading srcmeat.ts
    # returns its C address. This allows to memory operations to be
    # performed on it.
    dstmeta.ts=pyds.memdup(srcmeta.ts, MAX_TIME_STAMP_LEN+1)

    # Copy the sensorStr. This field is a string property.
    # The getter (read) returns its C address. The setter (write)
    # takes string as input, allocates a string buffer and copies
    # the input string into it.
    # pyds.get_string() takes C address of a string and returns
    # the reference to a string object and the assignment inside the binder copies content.
    dstmeta.sensorStr=pyds.get_string(srcmeta.sensorStr)

    if(srcmeta.objSignature.size>0):
        dstmeta.objSignature.signature=pyds.memdup(srcmeta.objSignature.signature,srcMeta.objSignature.size)
        dstmeta.objSignature.size = srcmeta.objSignature.size;

    if(srcmeta.extMsgSize>0):
        if(srcmeta.objType==pyds.NvDsObjectType.NVDS_OBJECT_TYPE_VEHICLE):
            srcobj = pyds.NvDsVehicleObject.cast(srcmeta.extMsg);
            obj = pyds.alloc_nvds_vehicle_object();
            obj.type=pyds.get_string(srcobj.type)
            obj.make=pyds.get_string(srcobj.make)
            obj.model=pyds.get_string(srcobj.model)
            obj.color=pyds.get_string(srcobj.color)
            obj.license = pyds.get_string(srcobj.license)
            obj.region = pyds.get_string(srcobj.region)
            dstmeta.extMsg = obj;
            dstmeta.extMsgSize = sys.getsizeof(pyds.NvDsVehicleObject)
        if(srcmeta.objType==pyds.NvDsObjectType.NVDS_OBJECT_TYPE_PERSON):
            srcobj = pyds.NvDsPersonObject.cast(srcmeta.extMsg);
            obj = pyds.alloc_nvds_person_object()
            obj.age = srcobj.age
            obj.gender = pyds.get_string(srcobj.gender);
            obj.cap = pyds.get_string(srcobj.cap)
            obj.hair = pyds.get_string(srcobj.hair)
            obj.apparel = pyds.get_string(srcobj.apparel);
            dstmeta.extMsg = obj;
            dstmeta.extMsgSize = sys.getsizeof(pyds.NvDsVehicleObject);

    return dstmeta

# Callback function for freeing an NvDsEventMsgMeta instance
def meta_free_func(data,user_data):
    user_meta=pyds.NvDsUserMeta.cast(data)
    srcmeta=pyds.NvDsEventMsgMeta.cast(user_meta.user_meta_data)

    # pyds.free_buffer takes C address of a buffer and frees the memory
    # It's a NOP if the address is NULL
    pyds.free_buffer(srcmeta.ts)
    pyds.free_buffer(srcmeta.sensorStr)

    if(srcmeta.objSignature.size > 0):
        pyds.free_buffer(srcmeta.objSignature.signature);
        srcmeta.objSignature.size = 0

    if(srcmeta.extMsgSize > 0):
        if(srcmeta.objType == pyds.NvDsObjectType.NVDS_OBJECT_TYPE_VEHICLE):
            obj =pyds.NvDsVehicleObject.cast(srcmeta.extMsg)
            pyds.free_buffer(obj.type);
            pyds.free_buffer(obj.color);
            pyds.free_buffer(obj.make);
            pyds.free_buffer(obj.model);
            pyds.free_buffer(obj.license);
            pyds.free_buffer(obj.region);
        if(srcmeta.objType == pyds.NvDsObjectType.NVDS_OBJECT_TYPE_PERSON):
            obj = pyds.NvDsPersonObject.cast(srcmeta.extMsg);
            pyds.free_buffer(obj.gender);
            pyds.free_buffer(obj.cap);
            pyds.free_buffer(obj.hair);
            pyds.free_buffer(obj.apparel);
        pyds.free_gbuffer(srcmeta.extMsg);
        srcmeta.extMsgSize = 0;

def generate_person_meta(data):
    obj = pyds.NvDsPersonObject.cast(data)
    obj.age = 45
    obj.cap = "none"
    obj.hair = "black"
    obj.gender = "male"
    obj.apparel= "formal"
    return obj

def generate_event_msg_meta(data, class_id):
    meta =pyds.NvDsEventMsgMeta.cast(data)
    meta.sensorId = 0
    meta.placeId = 0
    meta.moduleId = 0
    meta.sensorStr = "sensor-0"
    meta.ts = pyds.alloc_buffer(MAX_TIME_STAMP_LEN + 1)
    pyds.generate_ts_rfc3339(meta.ts, MAX_TIME_STAMP_LEN)

    # This demonstrates how to attach custom objects.
    # Any custom object as per requirement can be generated and attached
    # like NvDsVehicleObject / NvDsPersonObject. Then that object should
    # be handled in payload generator library (nvmsgconv.cpp) accordingly.
    # if(class_id==PGIE_CLASS_ID_VEHICLE):
    #     meta.type = pyds.NvDsEventType.NVDS_EVENT_MOVING
    #     meta.objType = pyds.NvDsObjectType.NVDS_OBJECT_TYPE_VEHICLE
    #     meta.objClassId = PGIE_CLASS_ID_VEHICLE
    #     obj = pyds.alloc_nvds_vehicle_object()
    #     obj = generate_vehicle_meta(obj)
    #     meta.extMsg = obj
    #     meta.extMsgSize = sys.getsizeof(pyds.NvDsVehicleObject);
    if(class_id == PGIE_CLASS_ID_PERSON):
        meta.type =pyds.NvDsEventType.NVDS_EVENT_ENTRY
        meta.objType = pyds.NvDsObjectType.NVDS_OBJECT_TYPE_PERSON;
        meta.objClassId = PGIE_CLASS_ID_PERSON
        obj = pyds.alloc_nvds_person_object()
        obj=generate_person_meta(obj)
        meta.extMsg = obj
        meta.extMsgSize = sys.getsizeof(pyds.NvDsPersonObject)
    return meta


# tiler_sink_pad_buffer_probe  will extract metadata received on OSD sink pad
# and update params for drawing rectangle, object information etc.
def tiler_src_pad_buffer_probe(pad,info,u_data):
    frame_number=0

    obj_counter = {
    PGIE_CLASS_ID_PERSON:0
    }
    is_first_object=True

    num_rects=0
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    if not batch_meta:
        return Gst.PadProbeReturn.OK
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.NvDsFrameMeta.cast()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            continue

        '''
        print("Frame Number is ", frame_meta.frame_num)
        print("Source id is ", frame_meta.source_id)
        print("Batch id is ", frame_meta.batch_id)
        print("Source Frame Width ", frame_meta.source_frame_width)
        print("Source Frame Height ", frame_meta.source_frame_height)
        print("Num object meta ", frame_meta.num_obj_meta)
        '''
        frame_number=frame_meta.frame_num
        l_obj=frame_meta.obj_meta_list
        num_rects = frame_meta.num_obj_meta
        is_first_object=True

        while l_obj is not None:
            try: 
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                continue
            obj_counter[obj_meta.class_id] += 1

            # Ideally NVDS_EVENT_MSG_META should be attached to buffer by the
            # component implementing detection / recognition logic.
            # Here it demonstrates how to use / attach that meta data.
            # print("########################")
            # print("before entering is first object", is_first_object)
            if(is_first_object and  not (frame_number%30)) :
                # print("Entered is first object")
                # Frequency of messages to be send will be based on use case.
                # Here message is being sent for first object every 30 frames.

                # Allocating an NvDsEventMsgMeta instance and getting reference
                # to it. The underlying memory is not manged by Python so that
                # downstream plugins can access it. Otherwise the garbage collector
                # will free it when this probe exits.
                msg_meta=pyds.alloc_nvds_event_msg_meta()
                msg_meta.bbox.top =  obj_meta.rect_params.top
                msg_meta.bbox.left =  obj_meta.rect_params.left
                msg_meta.bbox.width = obj_meta.rect_params.width
                msg_meta.bbox.height = obj_meta.rect_params.height
                msg_meta.frameId = frame_number
                msg_meta.trackingId = long_to_int(obj_meta.object_id)
                msg_meta.confidence = obj_meta.confidence
                msg_meta = generate_event_msg_meta(msg_meta, obj_meta.class_id)
                user_event_meta = pyds.nvds_acquire_user_meta_from_pool(batch_meta)
                if(user_event_meta):
                    user_event_meta.user_meta_data = msg_meta;
                    user_event_meta.base_meta.meta_type = pyds.NvDsMetaType.NVDS_EVENT_MSG_META
                    # Setting callbacks in the event msg meta. The bindings layer
                    # will wrap these callables in C functions. Currently only one
                    # set of callbacks is supported.
                    pyds.set_user_copyfunc(user_event_meta, meta_copy_func)
                    pyds.set_user_releasefunc(user_event_meta, meta_free_func)
                    pyds.nvds_add_user_meta_to_frame(frame_meta, user_event_meta)
                else:
                    print("Error in attaching event meta to buffer\n")

                is_first_object = False


    
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break
        """display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        py_nvosd_text_params.display_text = "Frame Number={} Number of Objects={} Vehicle_count={} Person_count={}".format(frame_number, num_rects, vehicle_count, person)
        py_nvosd_text_params.x_offset = 10;
        py_nvosd_text_params.y_offset = 12;
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        py_nvosd_text_params.font_params.font_color.red = 1.0
        py_nvosd_text_params.font_params.font_color.green = 1.0
        py_nvosd_text_params.font_params.font_color.blue = 1.0
        py_nvosd_text_params.font_params.font_color.alpha = 1.0
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.red = 0.0
        py_nvosd_text_params.text_bg_clr.green = 0.0
        py_nvosd_text_params.text_bg_clr.blue = 0.0
        py_nvosd_text_params.text_bg_clr.alpha = 1.0
        #print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Vehicle_count=",vehicle_count,"Person_count=",person)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)"""

        # Get frame rate through this probe
        fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps()
        try:
            l_frame=l_frame.next
        except StopIteration:
            break
    print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Face=",obj_counter[PGIE_CLASS_ID_PERSON])
    return Gst.PadProbeReturn.OK



def cb_newpad(decodebin, decoder_src_pad,data):
    print("In cb_newpad\n")
    caps=decoder_src_pad.get_current_caps()
    gststruct=caps.get_structure(0)
    gstname=gststruct.get_name()
    source_bin=data
    features=caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=",gstname)
    if(gstname.find("video")!=-1):
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=",features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad=source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write("Failed to link decoder src pad to source bin ghost pad\n")
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")

def decodebin_child_added(child_proxy,Object,name,user_data):
    print("Decodebin child added:", name, "\n")
    if(name.find("decodebin") != -1):
        Object.connect("child-added",decodebin_child_added,user_data)   
    if(is_aarch64() and name.find("nvv4l2decoder") != -1):
        print("Seting bufapi_version\n")
        Object.set_property("bufapi-version",True)

def create_source_bin(index,uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name="source-bin-%02d" %index
    print(bin_name)
    nbin=Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin=Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri",uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added",cb_newpad,nbin)
    uri_decode_bin.connect("child-added",decodebin_child_added,nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin,uri_decode_bin)
    bin_pad=nbin.add_pad(Gst.GhostPad.new_no_target("src",Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin

def main(args):

    # Get all arguments
    input_file = args.input_file
    no_display = args.no_display

    # load config file

    config = configparser.ConfigParser()
    config.read('configs/plugin_properties.ini')

    number_sources = len(input_file)


    if number_sources < 1:
        sys.stderr.write("Please provide path for file input or rtsp streams")
        sys.exit(1)

    for i in range(0, number_sources):
        fps_streams["stream{0}".format(i)] = GETFPS(i)

    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    is_live = False

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    print("Creating streamux \n ")
    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    print("Loading streammux properties \n")
    streammux_prop = config['streammux']

    streammux.set_property('width', streammux_prop.getint('width'))
    streammux.set_property('height', streammux_prop.getint('height'))
    streammux.set_property('batch-size', number_sources)
    streammux.set_property('batched-push-timeout', streammux_prop.getint('batched-push-timeout'))

    pipeline.add(streammux)
    for i,uri in enumerate(input_file):
        print("Creating source_bin ",i," \n ")
        uri_name= uri
        if uri_name.find("rtsp://") == 0 :
            is_live = True

        source_bin=create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")

        pipeline.add(source_bin)
        padname="sink_%u" %i
        sinkpad= streammux.get_request_pad(padname) 
        if not sinkpad:
            sys.stderr.write("Unable to create sink pad bin \n")

        srcpad=source_bin.get_static_pad("src")
        if not srcpad:
            sys.stderr.write("Unable to create src pad bin \n")

        srcpad.link(sinkpad)


    print("Creating Pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    
    print("Loading Pgie properties \n")
    pgie_prop = config['primary-gie']

    pgie.set_property('config-file-path', pgie_prop['config-file'])
    pgie.set_property('model-engine-file', pgie_prop['model-engine-file'])
    pgie.set_property("batch-size",number_sources)
    # pgie_batch_size=pgie.get_property("batch-size")
    # if(pgie_batch_size != number_sources):
    #     print("WARNING: Overriding infer-config batch-size",pgie_batch_size," with number of sources ", number_sources," \n")
    #     pgie.set_property("batch-size",number_sources)

    print("Creating tracker \n")
    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        sys.stderr.write(" Unable to create tracker \n")

    # tracker properties
    print("Loading tracker properties \n")
    tracker_prop = config['tracker']

    tracker.set_property("tracker-width", tracker_prop.getint('tracker-width'))
    tracker.set_property("tracker-height", tracker_prop.getint('tracker-height'))
    tracker.set_property("ll-lib-file", tracker_prop['ll-lib-file'])
    tracker.set_property("ll-config-file", tracker_prop['ll-config-file'])
    tracker.set_property("enable-batch-process", tracker_prop.getint('enable-batch-process'))

    print("Creating tiler \n ")
    tiler=Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")

    print("Loading tiler properties \n")
    tiler_prop = config['tiled-display']

    tiler_rows=int(math.sqrt(number_sources))
    tiler_columns=int(math.ceil((1.0*number_sources)/tiler_rows))
    tiler.set_property("rows",tiler_rows)
    tiler.set_property("columns",tiler_columns)
    tiler.set_property("width", tiler_prop.getint('width'))
    tiler.set_property("height", tiler_prop.getint('height'))

    print("Creating nvvidconv \n ")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")

    print("Creating msconv \n ")
    msgconv = Gst.ElementFactory.make("nvmsgconv", "nvmsg-converter")
    if not msgconv:
        sys.stderr.write(" Unable to create msgconv \n")
    
    # msgconv properties
    print("Loading msgconv properties \n")
    msgconv_prop = config['message-converter']

    msgconv.set_property("config", msgconv_prop['msg-conv-config'])
    msgconv.set_property("payload-type", msgconv_prop.getint('msg-conv-payload-type'))

    print("Creating msgbroker \n ")
    msgbroker = Gst.ElementFactory.make("nvmsgbroker", "nvmsg-broker")
    if not msgconv:
        sys.stderr.write(" Unable to create msgbroker \n")

    print("Loading message broker properties \n")
    msgbroker_prop = config['message-broker']

    msgbroker.set_property("proto-lib", msgbroker_prop['proto-lib'])
    msgbroker.set_property("conn-str", msgbroker_prop['conn-str'])
    msgbroker_cfg_file = msgbroker_prop["msg-broker-config"]
    topic = msgbroker_prop["topic"]

    if msgbroker_cfg_file is not None:
        msgbroker.set_property("config", msgbroker_cfg_file)
    if topic is not None:
        msgbroker.set_property("topic", topic)

    msgbroker.set_property("sync", msgbroker_prop.getboolean("sync"))

    print("Creating tee \n ")
    tee = Gst.ElementFactory.make("tee", "nvsink-tee")
    if not tee:
        sys.stderr.write(" Unable to create tee \n")

    print("Creating queue1 \n ")
    queue1 = Gst.ElementFactory.make("queue", "nvtee-que1")
    if not tee:
        sys.stderr.write(" Unable to create queue1 \n")

    print("Creating queue2 \n ")
    queue2 = Gst.ElementFactory.make("queue", "nvtee-que2")
    if not tee:
        sys.stderr.write(" Unable to create queue2 \n")        

    print("Creating queue3 \n ")
    queue3 = Gst.ElementFactory.make("queue", "nvtee-que3")
    if not tee:
        sys.stderr.write(" Unable to create queue3 \n")


    if(is_aarch64()):
        print("Creating transform \n ")
        transform=Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
        if not transform:
            sys.stderr.write(" Unable to create transform \n")
    
    print("Creating nvvidconv_postosd \n")
    nvvidconv_postosd = Gst.ElementFactory.make("nvvideoconvert", "convertor_postosd")
    if not nvvidconv_postosd:
        sys.stderr.write(" Unable to create nvvidconv_postosd \n")
    
    # Create a caps filter
    print("Creating caps filter \n")
    caps = Gst.ElementFactory.make("capsfilter", "filter")
    caps.set_property("caps", Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420"))
    
    # Make the encoder

    print("Loading encoder properties \n")

    encoder_prop = config['encoder']
    codec = encoder_prop['codec']

    if codec == "H264":
        print("Creating H264 Encoder")
        encoder = Gst.ElementFactory.make("nvv4l2h264enc", "encoder")
    elif codec == "H265":
        print("Creating H265 Encoder")
        encoder = Gst.ElementFactory.make("nvv4l2h265enc", "encoder")
    if not encoder:
        sys.stderr.write(" Unable to create encoder \n")


    encoder.set_property('bitrate', encoder_prop.getint('bitrate'))
    if is_aarch64():
        encoder.set_property('preset-level', encoder_prop.getint('preset-level'))
        encoder.set_property('insert-sps-pps', encoder_prop.getint('insert-sps-pps'))
        encoder.set_property('bufapi-version', encoder_prop.getint('bufapi-version'))
    
    # Make the payload-encode video into RTP packets
    if codec == "H264":
        print("Creating H264 rtppay")
        rtppay = Gst.ElementFactory.make("rtph264pay", "rtppay")
    elif codec == "H265":
        print("Creating H265 rtppay")
        rtppay = Gst.ElementFactory.make("rtph265pay", "rtppay")
    if not rtppay:
        sys.stderr.write(" Unable to create rtppay \n")
    
    # Make the UDP sink


    print("Creating udp sink \n")
    sink = Gst.ElementFactory.make("udpsink", "udpsink")
    if not sink:
        sys.stderr.write(" Unable to create udpsink")
    
    udpsink_prop = config['udpsink']

    sink.set_property('host', udpsink_prop['host'])
    sink.set_property('port', udpsink_prop.getint('port'))
    sink.set_property('async', udpsink_prop.getboolean('async'))
    sink.set_property('sync', udpsink_prop.getint('sync'))
   

    # create fake sink
    print("Creating FakeSink \n")
    fakesink = Gst.ElementFactory.make("fakesink", "fakesink")
    if not fakesink:
        sys.stderr.write(" Unable to create fakesink \n")

    if is_live:
        print("Atleast one of the sources is live")
        streammux.set_property('live-source', 1)


    print("Adding elements to Pipeline \n")
    pipeline.add(pgie)
    pipeline.add(tracker)
    pipeline.add(tiler)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(tee)
    pipeline.add(queue1)
    pipeline.add(queue2)
    # pipeline.add(queue3)
    pipeline.add(msgconv)
    pipeline.add(msgbroker)
    pipeline.add(nvvidconv_postosd)
    pipeline.add(caps)
    pipeline.add(encoder)
    pipeline.add(rtppay)
    if is_aarch64():
        pipeline.add(transform)
    pipeline.add(sink)
    #pipeline.add(fakesink)

    print("Linking elements in the Pipeline \n")
    streammux.link(pgie)
    pgie.link(tracker)
    tracker.link(tiler)
    tiler.link(nvvidconv)
    nvvidconv.link(nvosd)
    nvosd.link(tee)
    queue1.link(msgconv)
    msgconv.link(msgbroker)
    queue2.link(nvvidconv_postosd)    
    nvvidconv_postosd.link(caps)
    caps.link(encoder)
    encoder.link(rtppay)
    if is_aarch64():
        rtppay.link(transform)
        transform.link(sink)
    else:
        rtppay.link(sink)  

    # queue3.link(fakesink) 

    tee_msg_pad = tee.get_request_pad('src_%u')
    tee_render_pad = tee.get_request_pad("src_%u")
    # tee_fakesink_pad = tee.get_request_pad("src_%u")
    if not tee_msg_pad or not tee_render_pad:
        sys.stderr.write("Unable to get request pads \n")

    msg_sink_pad = queue1.get_static_pad("sink")
    tee_msg_pad.link(msg_sink_pad)
    vid_sink_pad = queue2.get_static_pad("sink")
    tee_render_pad.link(vid_sink_pad)
    # fake_sink_pad = queue3.get_static_pad("sink")
    # tee_fakesink_pad.link(fake_sink_pad)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # Start streaming

    rtsp_prop = config['rtsp-server']

    rtsp_port_num = rtsp_prop.getint('port')
    
    server = GstRtspServer.RTSPServer.new()
    server.props.service = "%d" % rtsp_port_num
    server.attach(None)
    
    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch( "( udpsrc name=pay0 port=%d buffer-size=524288 caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=(string)%s, payload=96 \" )" % (udpsink_prop.getint('port'), codec))
    factory.set_shared(True)
    server.get_mount_points().add_factory("/ds-test", factory)
    tiler_src_pad=pgie.get_static_pad("src")
    if not tiler_src_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)

    # List the sources
    print("Now playing...")
    for i, source in enumerate(input_file):
        print(i, ": ", source)

    print("Starting pipeline \n")
    # start play back and listed to events		
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print("Exiting app\n")
    pyds.unset_callback_funcs()
    pipeline.set_state(Gst.State.NULL)

# Parse and validate input arguments
def parse_args():

    parser = argparse.ArgumentParser(description='Provide the args to run the demo')

    parser.add_argument("input_file", nargs="+",
                  help="List of file or RTSP streams")

    parser.add_argument("-d", "--no-display", dest="no_display", default=False,
                  help="Disable display")

    args = parser.parse_args()
 
    return args

if __name__ == '__main__':
    args = parse_args()
    
    sys.exit(main(args))


