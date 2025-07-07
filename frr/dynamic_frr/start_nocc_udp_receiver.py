#!/usr/bin/env python3
# filepath: /home/zxz/875/sat_simulator_thu/frr/dynamic_frr/start_nocc_udp_receiver.py
"""
启动NOCC节点上的UDP接收服务
"""
import os
import time
import logging
import tempfile
import subprocess
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_nocc_udp_receiver(nocc_ips=None, udp_port=12346):
    """
    确保NOCC节点上的UDP接收服务已启动
    
    参数:
    - nocc_ips: NOCC节点IP列表，默认为["10.0.64.178", "10.0.64.186", "10.0.64.182"]
    - udp_port: NOCC UDP端口，默认为12346
    """
    # 如果未提供NOCC IP列表，则使用默认值
    if nocc_ips is None:
        nocc_ips = ["10.0.64.178", "10.0.64.186", "10.0.64.182"]
    
    logger.info("确保NOCC节点上UDP接收服务已启动...")
    
    for idx, nocc_ip in enumerate(nocc_ips):
        try:
            nocc_idx = idx + 1
            vm_name = f"vm{nocc_idx+44}"  # 假设NOCC节点从VM45开始
            
            # 创建expect脚本
            expect_script = f"""#!/usr/bin/expect -f
# 设置超时时间
set timeout 60

# 连接到NOCC节点
spawn sudo virsh console {vm_name}

sleep 1
send "\r"

expect "localhost login:" {{
    send "root\r"
}}

expect "密码：" {{
    send "passw0rd@123\r"
}}

expect "# " {{
    # 启动UDP接收服务（如果未运行）
    send "cd /home/resource_manager\r"
    expect "# "
    send "pgrep -f 'bash.*udp_receive.sh.*--port {udp_port}' || (nohup bash /home/resource_manager/udp_receive.sh --port {udp_port} > /home/resource_manager/udp_receiver.log 2>&1 &)\r"
    expect "# "
}}

expect "# " {{
    send "exit\r"
}}
"""
            
            # 将expect脚本保存到临时文件并执行
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.exp') as script_file:
                script_file.write(expect_script)
                script_path = script_file.name
            
            # 使脚本可执行
            os.chmod(script_path, 0o755)
            
            # 执行expect脚本
            logger.info(f"确保NOCC节点 {nocc_ip} (VM: {vm_name}) 上的UDP接收服务已启动...")
            result = subprocess.run(['expect', script_path], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.STDOUT)
            
            # 删除临时脚本文件
            os.unlink(script_path)
            
            logger.info(f"NOCC节点 {nocc_ip} UDP接收服务启动命令已执行")
            
        except Exception as e:
            logger.error(f"在NOCC节点 {nocc_ip} 上启动UDP接收服务时出错: {e}")
            logger.exception("详细错误信息:")

def main():
    parser = argparse.ArgumentParser(description='启动NOCC节点上的UDP接收服务')
    parser.add_argument('--port', type=int, default=12346, help='NOCC UDP接收端口，默认为12346')
    parser.add_argument('--ips', nargs='+', help='NOCC节点IP列表，默认为预设值')
    args = parser.parse_args()
    
    start_nocc_udp_receiver(nocc_ips=args.ips, udp_port=args.port)
    logger.info("NOCC UDP接收服务启动脚本执行完成")

if __name__ == "__main__":
    main()
