#!/bin/bash
# 资源信息响应式发送
# 用法：./status_sender_activate.sh --ip <目标IP> [--port <端口号>]

# ---------- 配置区 ----------
TARGET_USER="root"
TARGET_PASSWORD="passw0rd@123"
REMOTE_DIR="/home/resource_manager/resource_info"
INTERVAL_SECONDS=5
LOG_FILE="/var/log/status_sender.log"
INTERFACE="enp1s0"
TARGET_IP=""  # 通过 --ip 参数设置
PORT=12345    # 默认端口，可通过 --port 参数修改

# ---------- 参数解析 ----------
show_help() {
    echo "用法: $0 --ip <目标IP> [--port <端口号>]"
    echo "选项:"
    echo "  --ip <目标IP>     指定目标IP地址（必需）"
    echo "  --port <端口号>   指定UDP目标端口（可选，默认为12345）"
    echo "示例: nohup $0 --ip 192.253.1.11 --port 12346 &"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)
            TARGET_IP="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            echo "错误: 未知参数 $1"
            show_help
            exit 1
            ;;
    esac
done

# 验证IP参数
if [[ -z "$TARGET_IP" ]]; then
    echo "错误：必须通过 --ip 指定目标IP"
    show_help
    exit 1
elif ! [[ $TARGET_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "错误：无效的IP地址格式 $TARGET_IP"
    exit 1
fi

# 验证端口参数
if ! [[ $PORT =~ ^[0-9]+$ ]] || [[ $PORT -lt 1 ]] || [[ $PORT -gt 65535 ]]; then
    echo "警告：无效的端口号 $PORT，将使用默认端口12345"
    PORT=12345
fi

# ---------- 资源监控函数 ----------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

generate_status_yaml() {
    local timestamp=$(TZ="Asia/Shanghai" date +"%Y-%m-%dT%H:%M:%S")
    
    # 获取本机内网 IP（优先取 10 开头的 IPv4 地址）
    local_ip=$(hostname -I | awk '{for(i=1;i<=NF;i++) if ($i ~ /^10\./) print $i}' | head -n1)
    [[ -z "$local_ip" ]] && local_ip=$(hostname)

    # 获取CPU使用信息 (百分比)
    cpu_cores=$(nproc)
    # 修复正则表达式，提取空闲CPU百分比
    cpu_usage=$(top -b -n1 | grep -oP '\d+\.\d+\s+id\b' | awk '{print 100 - $1}')

    # 获取内存使用信息 (MB)
    memory_info=$(free -m)
    total_memory=$(echo "$memory_info" | grep Mem: | awk '{print $2}')
    used_memory=$(echo "$memory_info" | grep Mem: | awk '{print $3}')
    free_memory=$(echo "$memory_info" | grep Mem: | awk '{print $4}')

    # 获取磁盘使用信息 (MB)
    disk_info=$(df -m / | tail -n 1)
    total_disk=$(echo "$disk_info" | awk '{print $2}')
    used_disk=$(echo "$disk_info" | awk '{print $3}')
    free_disk=$(echo "$disk_info" | awk '{print $4}')
    
    # 获取GPU使用信息 (MB)
	gpu_info_0=$(dlsmi | sed -n '8p')  # 获取GPU信息
	gpu_info_1=$(dlsmi | sed -n '9p')  # 获取GPU信息
	total_dismem=$(echo "$gpu_info_1" | awk '{print $10}')  # 获取总显存
	used_dismem=$(echo "$gpu_info_1" | awk '{print $8}')   # 获取已用显存
	free_dismem=$(expr $total_dismem - $used_dismem) # 获取空闲显存
	gpu_util=$(echo "$gpu_info_0" | awk '{print $8}') # 获取利用率
	
	# # 获取当前链路资源信息
	# tc_output=$(tc -s qdisc show dev $INTERFACE)
    # # 解析参数 延迟 抖动 丢包率 速率
    # delay=$(echo "$tc_output"   | grep -oP 'delay\s+\K[\d.]+(?=ms)'   | head -1)
    # jitter=$(echo "$tc_output"  | grep -oP 'delay\s+[\d.]+ms\s+\K[\d.]+(?=ms)' | head -1)
    # loss=$(echo "$tc_output"    | grep -oP 'loss\s+\K[\d.]+(?=%)'     | head -1)
    # rate=$(echo "$tc_output"    | grep -oP 'rate\s+\K[\d.]+[KMGT]?bit'  | head -1)

    # # 处理空值
    # delay=${delay:-"0"}
    # jitter=${jitter:-"0"}
    # loss=${loss:-"0"}
    # rate=${rate:-"0bit"}

    # 生成 YAML 文件
    cat <<EOF > /home/resource_manager/resource_info/node-status-$local_ip.yaml
metadata:
  name: node-status-$local_ip
spec:
  timestamp: "$timestamp"
  cpuUsage:
    cores: $cpu_cores
    usage: "$cpu_usage%"
  memoryUsage:
    total: "${total_memory}MB"
    used: "${used_memory}MB"
    free: "${free_memory}MB"
  diskUsage:
    total: "${total_disk}MB"
    used: "${used_disk}MB"
    free: "${free_disk}MB"
  gpuUsage:
    total: "${total_dismem}MB"
    used: "${used_dismem}MB"
    free: "${free_dismem}MB"
    util: "${gpu_util}"
EOF
}

# ---------- 主循环 ----------
# 获取本机IP（优先10开头的内网IP）
get_local_ip() {
    local ip=$(hostname -I | awk '{for(i=1;i<=NF;i++) if ($i ~ /^10./) print $i}' | head -n1)
    [[ -z "$ip" ]] && ip=$(hostname)
    echo "$ip"
}

# 生成状态文件
generate_status_yaml
if [ $? -ne 0 ]; then
    log "错误: 无法生成状态文件"
    exit 1
fi

# 使用UDP发送状态信息
log "主动请求已接收，开始使用UDP发送状态信息到 $TARGET_IP:$PORT"

# 使用已有的get_local_ip函数获取本机IP
local_ip=$(get_local_ip)
yaml_file="/home/resource_manager/resource_info/node-status-${local_ip}.yaml"

if [[ ! -f "$yaml_file" ]]; then
    log "错误: 找不到特定YAML文件: $yaml_file"
    # 尝试查找任何YAML文件作为备选
    yaml_file=$(find /home/resource_manager/resource_info/ -name "*.yaml" | head -n 1)
    if [[ -z "$yaml_file" ]]; then
        log "错误: 无法找到任何YAML文件用于发送"
        exit 1
    fi
    log "使用备选YAML文件: $yaml_file"
fi

# 使用Bash UDP发送脚本，传递端口参数
bash /home/resource_manager/udp_send.sh --target_ip "$TARGET_IP" --port "$PORT" --file "$yaml_file"

# 检查是否成功
if [ $? -eq 0 ]; then
    log "状态信息通过UDP发送成功 (目标: $TARGET_IP:$PORT)"
else
    log "错误: 状态信息通过UDP发送失败"
    exit 1
fi

exit 0
