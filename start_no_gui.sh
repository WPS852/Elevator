#!/bin/bash

# 1) 先启动 server，后台运行
python -m elevator_saga.server.simulator &
SERVER_PID=$!

# 2) 等待 server 端口就绪
echo "Waiting for server to start..."
until curl -s http://127.0.0.1:8000/api/state > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Server is up!"

# 3) 再启动 client
python -m elevator_saga.client_examples.our_example
