#!/bin/bash
# 资源信息发送端守护进程脚本（集成资源监控）
# 用法：nohup ./status_sender.sh --ip <目标IP> &

# ---------- 配置区 ----------
TARGET_USER="root"
TARGET_PASSWORD="passw0rd@123"
REMOTE_DIR="/home/resource_manager/resource_info"
INTERVAL_SECONDS=5
LOG_FILE="/var/log/status_sender.log"
INTERFACE="enp1s0"
TARGET_IP=""  # 通过 --ip 参数设置

# ---------- 参数解析 ----------
show_help() {
    echo "用法: $0 --ip <目标IP>"
    echo "示例: nohup $0 --ip 192.253.1.11 &"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)
            TARGET_IP="$2"
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

# ---------- 资源监控函数 ----------
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

generate_status_yaml() {
    local timestamp=$(TZ="Asia/Shanghai" date +"%Y-%m-%dT%H:%M:%S")
    
    # 获取本机内网 IP
    local_ip=$(hostname -I | awk '{for(i=1;i<=NF;i++) if ($i ~ /^10\./) print $i}' | head -n1)
    [[ -z "$local_ip" ]] && local_ip=$(hostname)

    # 获取CPU使用率
    cpu_cores=$(nproc)
    cpu_usage=$(top -b -n1 | grep -oP '\d+\.\d+\s+id\b' | awk '{print 100 - $1}')

    # 获取内存信息
    memory_info=$(free -m)
    total_memory=$(echo "$memory_info" | grep Mem: | awk '{print $2}')
    used_memory=$(echo "$memory_info" | grep Mem: | awk '{print $3}')
    free_memory=$(echo "$memory_info" | grep Mem: | awk '{print $4}')

    # 获取磁盘信息
    disk_info=$(df -m / | tail -n 1)
    total_disk=$(echo "$disk_info" | awk '{print $2}')
    used_disk=$(echo "$disk_info" | awk '{print $3}')
    free_disk=$(echo "$disk_info" | awk '{print $4}')
    
    # 获取GPU信息
    gpu_info_0=$(dlsmi | sed -n '8p')
    gpu_info_1=$(dlsmi | sed -n '9p')
    total_dismem=$(echo "$gpu_info_1" | awk '{print $10}')
    used_dismem=$(echo "$gpu_info_1" | awk '{print $8}')
    free_dismem=$(expr $total_dismem - $used_dismem)
    gpu_util=$(echo "$gpu_info_0" | awk '{print $8}')
    
    # # 获取链路信息
    # tc_output=$(tc -s qdisc show dev $INTERFACE)
    # delay=$(echo "$tc_output"   | grep -oP 'delay\s+\K[\d.]+(?=ms)'   | head -1)
    # jitter=$(echo "$tc_output"  | grep -oP 'delay\s+[\d.]+ms\s+\K[\d.]+(?=ms)' | head -1)
    # loss=$(echo "$tc_output"    | grep -oP 'loss\s+\K[\d.]+(?=%)'     | head -1)
    # rate=$(echo "$tc_output"    | grep -oP 'rate\s+\K[\d.]+[KMGT]?bit'  | head -1)

    # # 处理空值
    # delay=${delay:-"0"}
    # jitter=${jitter:-"0"}
    # loss=${loss:-"0"}
    # rate=${rate:-"0bit"}

    # 生成YAML文件
    cat <<EOF > /home/resource_manager/resource_info/node_status-$local_ip.yaml
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
while true; do
    generate_status_yaml || {
        log "错误: 无法生成状态文件"
        sleep $INTERVAL_SECONDS
        continue
    }

    log "开始发送状态文件到 $TARGET_IP:$REMOTE_DIR"
    if sshpass -p "$TARGET_PASSWORD" scp -o StrictHostKeyChecking=no /home/resource_manager/resource_info/node_status-$local_ip.yaml "$TARGET_USER@$TARGET_IP:$REMOTE_DIR"; then
        log "状态文件发送成功"
    else
        log "错误: 状态文件发送失败"
    fi

    sleep $INTERVAL_SECONDS
done
