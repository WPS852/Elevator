#!/bin/bash

echo "[INFO] 启动服务器..."
gnome-terminal -- bash -c "python3 -m elevator_saga.server.simulator; exec bash"

sleep 2
echo "[INFO] 启动算法客户端..."
gnome-terminal -- bash -c "python3 -m elevator_saga.client_examples.our_example; exec bash"

echo "[INFO] 所有进程已启动。"