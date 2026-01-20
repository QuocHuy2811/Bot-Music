# Sử dụng Python làm gốc
FROM python:3.11-slim

# Cài đặt Java 21 và công cụ hỗ trợ 
RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless dos2unix wget ca-certificates && \
    update-ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Tải trực tiếp Lavalink Server bản 4.1.2
ADD https://github.com/lavalink-devs/Lavalink/releases/download/4.1.2/Lavalink.jar Lavalink.jar

# 2. Tải sẵn các plugin tương thích
RUN mkdir -p /app/plugins && \
    wget https://github.com/lavalink-devs/youtube-plugin/releases/download/1.16.0/youtube-plugin-1.16.0.jar -P /app/plugins && \
    wget https://github.com/topi806/LavaSrc/releases/download/4.1.1/lavasrc-plugin-4.1.1.jar -P /app/plugins

# 3. Cài đặt thư viện Python 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt [cite: 1]

# 4. Copy các file code còn lại (main.py, application.yml, start.sh) 
COPY . .

# 5. Sửa lỗi xuống dòng và cấp quyền chạy 
RUN dos2unix start.sh && chmod +x start.sh

CMD ["./start.sh"] [cite: 3]