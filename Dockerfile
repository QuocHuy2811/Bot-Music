# Sử dụng Python làm gốc
FROM python:3.11-slim

# Cài đặt Java 21 (để chạy Lavalink) và dos2unix (để sửa lỗi script)
RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless dos2unix && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy file requirements và cài đặt thư viện Python trước
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy TOÀN BỘ file từ GitHub vào container (Bao gồm cả Lavalink.jar và plugins)
COPY . .

# Sửa lỗi định dạng file script và cấp quyền chạy
# Sửa lỗi định dạng file script và cấp quyền chạy
RUN apt-get update && apt-get install -y dos2unix
RUN dos2unix start.sh && chmod +x start.sh

# Lệnh khởi động
CMD ["./start.sh"]