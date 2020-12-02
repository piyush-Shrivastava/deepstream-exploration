kafka_2.13-2.6.0/bin/zookeeper-server-start.sh kafka_2.12-2.5.0/config/zookeeper.properties &
kafka_2.13-2.6.0/bin/kafka-server-start.sh kafka_2.12-2.5.0/config/server.properties &
python3 deepstream_facedetect.py 