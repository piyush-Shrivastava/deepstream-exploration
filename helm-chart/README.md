# video-analytics-demo-wvideo-1.0.0

Helm Chart for video analytics demo with sample video 

Create Helm Chart with following command:

```
sudo helm repo add nvidia https://nvidiagit.github.io/video-analytics-demo-wvideo/

sudo helm repo update

helm install nvidia/video-analytics-demo-wvideo
```

1. Client Setup Download VLC Player from: https://www.videolan.org/vlc/ on the client machine where the user intends to view the video stream.
2. We can view the video stream by entering the following URL in the VLC player. 
```
rtsp://ipaddress-of-Node:31113/ds-test 
```
IPAddress of the node can be viewed by executing ifconfig on the server node

Disclaimer:
- Note: Due to the output from DeepStream being real-time via RTSP, you may experience occasional hiccups in the video stream depending on network conditions.

