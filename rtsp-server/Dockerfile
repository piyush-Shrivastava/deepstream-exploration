FROM ubuntu:18.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=America/New_York
RUN apt-get update && apt-get install -y tzdata
RUN  ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y \
  libgstreamer1.0-0 \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  gstreamer1.0-doc \
  gstreamer1.0-tools \
  gstreamer1.0-x \
  gstreamer1.0-alsa \
  gstreamer1.0-gl \
  gstreamer1.0-gtk3 \
  gstreamer1.0-qt5 \
  gstreamer1.0-pulseaudio \
  autoconf \
  automake \
  libtool \
  python3-dev \
  libgstreamer1.0-dev \
  python3-gi \
  python3-gst-1.0 \
  python-gi-dev \
  python3-opencv \
  python3-numpy \
  libgstrtspserver-1.0-0 \
  gstreamer1.0-rtsp \
  libgirepository1.0-dev \
  gobject-introspection \ 
  gir1.2-gst-rtsp-server-1.0 
 
ENV HOME /root

RUN mkdir -p /opt/python/rtspserver

COPY . /opt/python/rtspserver

WORKDIR /opt/python/rtspserver

CMD ["python3", "vid2rtspso.py"]














