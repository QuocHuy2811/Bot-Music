#!/bin/bash

# Chạy Lavalink ở chế độ nền
java -jar Lavalink.jar &

# Chờ Lavalink khởi động (khoảng 20 giây)
sleep 20

# Chạy Bot Python
python main.py