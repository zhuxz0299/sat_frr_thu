#!/bin/bash
# 通过UDP发送数据到指定IP和端口
# 用法: bash udp_send.sh --target_ip <目标IP> [--port <端口号>] [--file <文件路径>]

# 默认端口
PORT=12345
TARGET_IP=""
FILE_PATH=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target_ip)
            TARGET_IP="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --file)
            FILE_PATH="$2"
            shift 2
            ;;
        *)
            echo "错误: 未知参数 $1"
            echo "用法: $0 --target_ip <目标IP> [--port <端口号>] [--file <文件路径>]"
            exit 1
            ;;
    esac
done

# 验证参数
if [[ -z "$TARGET_IP" ]]; then
    echo "错误：必须指定目标IP"
    exit 1
fi

# 如果指定了文件，则从文件读取内容，否则从标准输入读取
if [[ -n "$FILE_PATH" ]]; then
    if [[ ! -f "$FILE_PATH" ]]; then
        echo "错误：文件 $FILE_PATH 不存在"
        exit 1
    fi
    DATA=$(cat "$FILE_PATH")
else
    # 从标准输入读取数据
    DATA=$(cat)
fi

# 检查数据是否为空
if [[ -z "$DATA" ]]; then
    echo "错误：没有数据可发送"
    exit 1
fi

# 使用 nc (netcat) 发送 UDP 数据
echo -n "$DATA" | nc -u -w1 $TARGET_IP $PORT

# 检查发送结果
if [[ $? -eq 0 ]]; then
    echo "数据已成功发送至 $TARGET_IP:$PORT"
    exit 0
else
    echo "发送数据时出错"
    exit 1
fi
