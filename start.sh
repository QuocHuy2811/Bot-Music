#!/bin/bash

# Khởi chạy Lavalink với giới hạn RAM 400MB
java -Xmx400M -jar Lavalink.jar &

# Chờ 30 giây để Lavalink sẵn sàng
sleep 30

# Chạy Bot Python
python main.py