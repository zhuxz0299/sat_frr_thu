#!/bin/bash
# 脚本名称: send_constellation_json.sh
# 描述: 将资源信息JSON文件传输到Windows电脑的指定目录
# 用法: ./send_constellation_json.sh [IP地址] [用户名] [密码]

# 默认参数
DEFAULT_IP="192.168.200.254"
DEFAULT_USER="123"
DEFAULT_PASSWORD=""  # 为安全起见，默认为空

# 使用命令行参数覆盖默认值，如果提供
IP=${1:-$DEFAULT_IP}
USER=${2:-$DEFAULT_USER}
PASSWORD=${3:-$DEFAULT_PASSWORD}

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
echo "源文件:"
[ -f "$YG_FILE" ] && echo "  - $YG_FILE" || echo "  - $YG_FILE (不存在)"
[ -f "$XW_FILE" ] && echo "  - $XW_FILE" || echo "  - $XW_FILE (不存在)"
[ -f "$TSN_FILE" ] && echo "  - $TSN_FILE" || echo "  - $TSN_FILE (不存在)"
echo "目标目录:"
echo "  - $YG_DEST"
echo "  - $XW_DEST"
echo "  - $TSN_DEST"
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

# 传输文件
transfer_file "$YG_FILE" "$YG_DEST/yg_constellation.json" "$YG_DEST"
transfer_file "$XW_FILE" "$XW_DEST/xw_constellation.json" "$XW_DEST"
transfer_file "$TSN_FILE" "$TSN_DEST/tsn_constellation.json" "$TSN_DEST"

echo "====================================="
echo "传输操作完成"
echo "======================================"
