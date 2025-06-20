#!/bin/bash
# 脚本名称: send_constellation_json.sh
# 描述: 将资源信息JSON文件传输到Windows电脑的指定目录
# 用法: ./send_constellation_json.sh [IP地址] [用户名] [密码] [间隔时间(秒)]

# 默认参数
DEFAULT_IP="192.168.200.254"
DEFAULT_USER="123"
DEFAULT_PASSWORD=""  # 为安全起见，默认为空
DEFAULT_INTERVAL=20  # 默认间隔时间（秒）

# 使用命令行参数覆盖默认值，如果提供
IP=${1:-$DEFAULT_IP}
USER=${2:-$DEFAULT_USER}
PASSWORD=${3:-$DEFAULT_PASSWORD}
INTERVAL=${4:-$DEFAULT_INTERVAL}

# 脚本路径
RESOURCE_INFO_GATHERING_PY="./script/resource_info_gathering.py"

# 源文件路径
SOURCE_DIR="./resource_info"
YG_FILE="$SOURCE_DIR/yg_constellation.json"
XW_FILE="$SOURCE_DIR/xw_constellation.json"
TSN_FILE="$SOURCE_DIR/tsn_constellation.json"

# 目标路径
YG_DEST="D:/temp/qinghua/yg"
XW_DEST="D:/temp/qinghua/xw"
TSN_DEST="D:/temp/qinghua/tsn"

# 显示将要执行的操作
echo "====================================="
echo "文件传输配置"
echo "====================================="
echo "目标主机: $IP"
echo "用户名: $USER"
echo "源文件目录: $SOURCE_DIR"
echo "目标目录:"
echo "  - $YG_DEST"
echo "  - $XW_DEST"
echo "  - $TSN_DEST"
echo "执行间隔: ${INTERVAL}秒"
echo "====================================="

# 检查文件是否存在
if [ ! -f "$YG_FILE" ] && [ ! -f "$XW_FILE" ] && [ ! -f "$TSN_FILE" ]; then
    echo "错误: 所有源文件都不存在！请检查路径。"
    exit 1
fi

# 询问密码（如果未提供）
if [ -z "$PASSWORD" ]; then
    read -sp "请输入 $USER@$IP 的密码: " PASSWORD
    echo
fi

# 传输每个存在的文件
transfer_file() {
    local src=$1
    local dest=$2
    local dest_dir=$3
    
    if [ -f "$src" ]; then
        echo "正在传输 $(basename $src) 到 $dest_dir..."
        if [ -n "$PASSWORD" ]; then
            sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${USER}@${IP}:$dest"
        else
            scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$src" "${USER}@${IP}:$dest"
        fi
        
        if [ $? -eq 0 ]; then
            echo "✓ $(basename $src) 传输成功"
        else
            echo "✗ $(basename $src) 传输失败"
        fi
    fi
}

# 定义主要流程函数
process_and_transfer() {
    local current_time=$(date "+%Y-%m-%d %H:%M:%S")
    echo "====================================="
    echo "[$current_time] 开始处理..."
    
    # 生成JSON文件
    generate_json_files
    
    # 检查文件是否存在
    if [ ! -f "$YG_FILE" ] && [ ! -f "$XW_FILE" ] && [ ! -f "$TSN_FILE" ]; then
        echo "错误: 所有源文件都不存在！请检查生成过程。"
        return 1
    fi
    
    # 传输文件
    transfer_file "$YG_FILE" "$YG_DEST/yg_constellation.json" "$YG_DEST"
    transfer_file "$XW_FILE" "$XW_DEST/xw_constellation.json" "$XW_DEST"
    transfer_file "$TSN_FILE" "$TSN_DEST/tsn_constellation.json" "$TSN_DEST"
    
    echo "====================================="
    echo "本次处理完成"
    echo "====================================="
}

# 生成JSON文件函数
generate_json_files() {
    echo "====================================="
    echo "正在生成JSON文件..."
    
    # 检查resource_info_gathering.py是否存在
    if [ ! -f "$RESOURCE_INFO_GATHERING_PY" ]; then
        echo "错误: 找不到脚本 $RESOURCE_INFO_GATHERING_PY"
        return 1
    fi

    # 运行resource_info_gathering.py生成各种类型的JSON文件
    # yg对应vm47, xw对应vm46, tsn对应vm45
    echo "处理 yg 类型 (vm47)..."
    python3 "$RESOURCE_INFO_GATHERING_PY" "$SOURCE_DIR/vm47" "yg"
    if [ $? -ne 0 ]; then
        echo "警告: 处理 yg 类型时出错"
    fi
    
    echo "处理 xw 类型 (vm46)..."
    python3 "$RESOURCE_INFO_GATHERING_PY" "$SOURCE_DIR/vm46" "xw"
    if [ $? -ne 0 ]; then
        echo "警告: 处理 xw 类型时出错"
    fi
    
    echo "处理 tsn 类型 (vm45)..."
    python3 "$RESOURCE_INFO_GATHERING_PY" "$SOURCE_DIR/vm45" "tsn"
    if [ $? -ne 0 ]; then
        echo "警告: 处理 tsn 类型时出错"
    fi
    
    echo "JSON文件生成完成"
    echo "====================================="
}


# 主循环，定期执行
echo "====================================="
echo "开始定期执行，每 ${INTERVAL} 秒一次"
echo "按 Ctrl+C 终止执行"
echo "====================================="

# 捕获Ctrl+C信号，优雅退出
trap "echo '收到中断信号，正在退出...'; exit 0" SIGINT SIGTERM

# 首次运行
process_and_transfer

# 定期运行
while true; do
    echo "等待 ${INTERVAL} 秒后再次执行..."
    sleep ${INTERVAL}
    process_and_transfer
done
