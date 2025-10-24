#!/bin/bash

# 切到脚本所在目录 elevator_saga/
cd "$(dirname "$0")"

# 项目根目录 /root/homework/se/Elevator
PROJECT_ROOT=$(dirname "$(pwd)")

echo "[INFO] 启动 Elevator Server..."

# 如果端口被占用，清理
if fuser 8000/tcp >/dev/null 2>&1; then
  echo "[INFO] 发现端口 8000 被占用，正在清理..."
  fuser -k 8000/tcp
fi

# 后台启动 server
nohup python3 -m elevator_saga.server.simulator > "$PROJECT_ROOT/server.log" 2>&1 &
echo "[INFO] Elevator 服务器已后台运行"

echo "[INFO] 启动电梯可视化系统..."

# ✅ 关键：回到项目根目录，再启动 GUI（确保 required_files 路径正确）
cd "$PROJECT_ROOT"
python3 start_visualization.py
