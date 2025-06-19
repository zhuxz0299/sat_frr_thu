#!/bin/bash
# 远程命令执行脚本（支持自动注入本机IP）
# 用法：./resource_request.sh -p <密码> -u <用户> -i <IP> [-c "远程命令"]

# 获取本机IP（优先10开头的内网IP）
get_local_ip() {
    local ip=$(hostname -I | awk '{for(i=1;i<=NF;i++) if ($i ~ /^10./) print $i}' | head -n1)
    [[ -z "$ip" ]] && ip=$(hostname)
    echo "$ip"
}

# 带本机IP的默认命令
DEFAULT_CMD="/home/resource_manager/status_sender_activate.sh --ip $(get_local_ip)"

# 解析命令行参数
while getopts "p:u:i:c:" opt; do
  case $opt in
    p) PASSWORD="$OPTARG" ;;
    u) USER="$OPTARG" ;
    i) IP="$OPTARG" ;;
    c) CMD="$OPTARG" ;;
    *) echo "用法: $0 -p <密码> -u <用户> -i <IP> [-c \"远程命令\"]"
       exit 1
  esac
done

# 检查必要参数
if [[ -z "$PASSWORD" || -z "$USER" || -z "$IP" ]]; then
  echo "错误: 必须指定 -p、-u 和 -i 参数"
  echo "用法: $0 -p <密码> -u <用户> -i <IP> [-c \"远程命令\"]"
  exit 1
fi

# 设置默认命令（如果未指定 -c 参数）
: ${CMD:=$DEFAULT_CMD}

# 执行远程命令
echo "正在执行远程命令：$CMD"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "${USER}@${IP}" "$CMD"

# 处理执行结果
if [ $? -eq 0 ]; then
  echo "[成功] 命令已执行: $CMD"
else
  echo "[失败] 命令执行失败: $CMD" >&2
  exit 1
fi