FROM  nvcr.io/nvidia/deepstream:5.0-20.07-triton

RUN apt-get update && apt-get install -y \
  autoconf \
  automake \
  libtool \
  python3-dev \
  libgstreamer1.0-dev \
  python3-gi \
  python3-gst-1.0 \
  python3-opencv \
  python3-numpy \
  libgstrtspserver-1.0-0 \
  gstreamer1.0-rtsp \
  libgirepository1.0-dev \
  gobject-introspection \ 
  gir1.2-gst-rtsp-server-1.0 

# Kafka Installation

RUN apt-get update && apt-get install -y \
  libglib2.0 \
  libglib2.0-dev \
  libjansson4 \
  libjansson-dev \
  librdkafka1=0.11.3-1build1 \
  openjdk-8-jre



ENV HOME /root
ENV DEEPSTREAM_ROOT /opt/nvidia/deepstream/deepstream-5.0

WORKDIR ${HOME}

# RUN git clone https://github.com/GStreamer/gst-python.git
# WORKDIR ${HOME}/gst-python
# RUN git checkout 1a8f48a
# RUN ./autogen.sh PYTHON=python3
# RUN ./configure PYTHON=python3
# RUN make
# RUN make install

ENV GST_LIBS -lgstreamer-1.0 -lgobject-2.0 -lglib-2.0
ENV GST_CFLAGS -pthread -I/usr/include/gstreamer-1.0 -I/usr/include/glib-2.0 -I/usr/lib/x86_64-linux-gnu/glib-2.0/include


WORKDIR ${HOME}

COPY python $DEEPSTREAM_ROOT/sources/python

WORKDIR ${DEEPSTREAM_ROOT}/sources/python/apps/deepstream-facedetect

CMD ["python3", "deepstream_facedetect.py", "rtsp://videoanalytics-video-analytics-pipeline-rtsp-input1:8554/input", "rtsp://videoanalytics-video-analytics-pipeline-rtsp-input2:8554/input"]













