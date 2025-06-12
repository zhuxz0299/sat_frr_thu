#!/bin/bash
# UDP接收服务器，接收数据并保存为YAML文件
# 用法: bash udp_receive.sh [--port <端口号>] [--save_dir <保存目录>]

# 默认配置
PORT=12345
SAVE_DIR="/home/resource_manager/resource_info"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        --save_dir)
            SAVE_DIR="$2"
            shift 2
            ;;
        *)
            echo "错误: 未知参数 $1"
            echo "用法: $0 [--port <端口号>] [--save_dir <保存目录>]"
            exit 1
            ;;
    esac
done

# 确保保存目录存在
mkdir -p "$SAVE_DIR"

echo "UDP服务器启动，监听端口 $PORT，保存目录: $SAVE_DIR"

# 创建临时文件存储接收到的数据
TEMP_FILE="/tmp/udp_data_$$.txt"
touch "$TEMP_FILE"
trap "rm -f $TEMP_FILE; kill \$NC_PID 2>/dev/null" EXIT INT TERM

while true; do
    # 使用nc接收UDP数据，保存到临时文件，在后台运行
    echo "等待UDP数据..."
    # 先清空临时文件
    > "$TEMP_FILE"
    
    # 在后台启动nc
    nc -u -l $PORT > "$TEMP_FILE" &
    NC_PID=$!
    
    # 循环检查是否接收到数据
    DATA_RECEIVED=0
    while kill -0 $NC_PID 2>/dev/null; do
        if [ -s "$TEMP_FILE" ]; then
            # 文件有内容，停止nc进程
            kill $NC_PID 2>/dev/null
            DATA_RECEIVED=1
            break
        fi
        sleep 1
    done
    
    echo "接收到数据，正在处理..."
    
    # 获取接收到的数据长度
    DATA_SIZE=$(stat -c %s "$TEMP_FILE" 2>/dev/null || echo 0)
    echo "收到数据，长度: $DATA_SIZE 字节"
    
    # 检查是否接收到数据
    if [[ $DATA_SIZE -gt 0 ]]; then
        # 读取临时文件内容
        DATA=$(cat "$TEMP_FILE")
        
        # 尝试从YAML格式中提取name字段
        # 首先尝试提取metadata.name字段
        SAT_ID=$(echo "$DATA" | grep -A 1 "metadata:" | grep "name:" | sed 's/.*name: *\([^ ]*\).*/\1/' | head -1)
        
        if [[ -z "$SAT_ID" ]]; then
            # 尝试获取node-status中的IP地址
            NODE_STATUS=$(echo "$DATA" | grep "name: node-status-" | head -1)
            if [[ -n "$NODE_STATUS" ]]; then
                SAT_ID=$(echo "$NODE_STATUS" | sed 's/.*node-status-\([^ ]*\).*/\1/')
            fi
        fi
        
        if [[ -z "$SAT_ID" ]]; then
            # 使用时间戳作为文件名
            TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
            FILENAME="unknown_${TIMESTAMP}.yaml"
        else
            FILENAME="${SAT_ID}.yaml"
        fi
        
        # 保存数据到文件
        echo "$DATA" > "${SAVE_DIR}/${FILENAME}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已保存数据到 ${SAVE_DIR}/${FILENAME}"
    else
        echo "没有接收到数据或数据为空"
    fi
done
