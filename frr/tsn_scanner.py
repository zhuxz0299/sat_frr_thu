#!/usr/bin/env python3
# filepath: /home/zxz/875/sat_simulator/frr/dynamic_frr/tsn_scanner.py
import os
import time
import logging
import tempfile
import subprocess
import numpy as np
import pandas as pd
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TSNScanner:
    def __init__(self, base_tsn_container_name="clab-sat-network-TSN",
                 base_yg_container_name="clab-sat-network-YG",
                 base_xw_container_name="clab-sat-network-XW",
                 csv_file=None):
        """
        初始化TSN扫描器
        
        参数:
        - base_container_name: 容器名称的前缀
        - csv_file: CSV文件路径，用于读取网络拓扑矩阵
        """
        self.base_tsn_container_name = base_tsn_container_name
        self.base_yg_container_name = base_yg_container_name
        self.base_xw_container_name = base_xw_container_name
        self.current_matrix = None
        
        # 如果提供了CSV文件，则立即读取矩阵
        if csv_file:
            self.read_matrix_from_csv(csv_file)
            
        logger.info("TSN扫描器初始化完成")

    def read_matrix_from_csv(self, csv_file):
        """从CSV文件读取链路可见性矩阵"""
        try:
            # 使用pandas读取CSV文件，不设置列名或索引列
            df = pd.read_csv(csv_file, header=None, sep=',', dtype=float)
            matrix = df.values
            
            # 验证矩阵格式
            rows, cols = matrix.shape
            
            logger.info(f"成功读取矩阵，大小: {rows}x{cols}")
            self.current_matrix = matrix
            return True
        except Exception as e:
            logger.error(f"读取CSV文件错误: {e}")
            logger.exception("详细错误信息:")
            return False

    def vm_sat_ip_map(self, type, idx):
        """给定指定tsn编号，返回tsn对应vm名称和ip"""

        if type == "TSN":
            vm_name = f"vm{idx}"
            fourth_byte = (idx-1)*4 + 2
            vm_ip = f"10.0.64.{fourth_byte}"
            
        elif type == "YG":
            vm_name = f"vm{idx+8}"
            fourth_byte = (idx-1+8)*4 + 2
            vm_ip = f"10.0.64.{fourth_byte}"

        elif type == "XW":
            vm_name = f"vm{idx+20}"
            fourth_byte = (idx-1+20)*4 + 2
            vm_ip = f"10.0.64.{fourth_byte}"

        return vm_name, vm_ip

    def scan_connected_nodes(self):
        """多线程并发扫描当前矩阵中每个TSN节点连接的所有低轨卫星节点"""
        
        if self.current_matrix is None:
            logger.info("当前没有加载任何网络拓扑，无法执行扫描")
            return False
        
        rows, cols = self.current_matrix.shape
        logger.info(f"开始扫描，共 {rows} 个TSN节点")
        
        # 使用线程池执行并发扫描
        with ThreadPoolExecutor(max_workers=rows) as executor:
            # 为每个TSN节点提交一个扫描任务
            futures = []
            for tsn_idx in range(rows):
                future = executor.submit(self._scan_single_tsn_node, tsn_idx)
                futures.append(future)
            
            # 等待所有扫描任务完成
            for future in futures:
                future.result()
        
        logger.info("所有TSN节点扫描完成")
        return True

    def _scan_single_tsn_node(self, tsn_idx):
        """扫描单个TSN节点连接的所有低轨卫星节点"""

        original_tsn_idx = tsn_idx + 1  # 转换为原始节点编号
        tsn_container_name = f"{self.base_tsn_container_name}{original_tsn_idx}"
        
        # 查找与当前TSN节点相连的所有低轨卫星节点IP
        dg_ips = [] 
        # 收集详细信息用于日志记录
        dg_info = []

        # 获取当前TSN的VM信息
        tsn_vm_name, tsn_vm_ip = self.vm_sat_ip_map("TSN", original_tsn_idx)
        
        for dg_idx in range(self.current_matrix.shape[1]):
            if self.current_matrix[tsn_idx, dg_idx] >= 0:
                if dg_idx < 12:  # YG节点
                    original_dg_idx = dg_idx + 1
                    dg_type = "YG"
                else:  # XW节点
                    original_dg_idx = dg_idx - 12 + 1
                    dg_type = "XW"

                dg_vm_name, dg_vm_ip = self.vm_sat_ip_map(dg_type, original_dg_idx)
                dg_ips.append(dg_vm_ip)
                dg_info.append(f"{dg_type}{original_dg_idx}({dg_vm_ip})")

        if not dg_ips:
            logger.info(f"TSN{original_tsn_idx} 没有连接的低轨卫星节点")  
            return

        logger.info(f"TSN{original_tsn_idx} 开始扫描 {len(dg_ips)} 个连接的低轨卫星节点")  
        
        try:
            # 创建expect脚本，将所有IP作为列表传入
            dg_ips_tcl_list = " ".join([f"\"{ip}\"" for ip in dg_ips])

            # NOCC-TSN/NOCC-YG/NOCC-XW ip地址(注意是vm的ip地址不是frr的ip地址), 顺序在分配ip时有点乱，后续改
            nocc_ips = ["10.0.64.178","10.0.64.186","10.0.64.182"]
            nocc_ips_tcl_list = " ".join([f"\"{ip}\"" for ip in nocc_ips])
        
            expect_script = f"""#!/usr/bin/expect -f
# 设置超时时间
set timeout 300

# 定义低轨节点IP列表
set dg_list [list {dg_ips_tcl_list}]
# 定义NOCC节点IP列表
set nocc_list [list {nocc_ips_tcl_list}]
# 连接到TSN的VM
spawn sudo virsh console {tsn_vm_name}

sleep 1
send "\r"

expect "localhost login:"
send "root\r"
expect "密码："
send "passw0rd@123\r"

expect "# "

catch {{
    # 首先启动UDP接收服务（在后台运行）    
    send "cd /home/resource_manager\r"
    expect "# "
    send "pgrep -f 'bash.*udp_receive.sh' || (nohup bash /home/resource_manager/udp_receive.sh > /home/resource_manager/udp_receiver.log 2>&1 &)\r"
    expect "# "
    
    # 切换到资源信息目录
    send "cd /home/resource_manager/resource_info\r"
    expect "# "
    foreach ip $dg_list {{
        puts "正在扫描可见域内低轨卫星IP: $ip"
        send "/home/resource_manager/resource_request.sh -p passw0rd@123 -u root -i $ip\r"
        expect "# "

        # 方案一 tsn获取后直接转发nocc
        puts "获取成功直接转发nocc"
        set parts [split $ip .]
        set fourth [lindex $parts 3]
        puts "$fourth"
        set num [expr ((int($fourth) - 2) / 4) + 1]
        puts "$num"
        # 选择目标NOCC节点
        if {{ $num >= 1 && $num <= 8 }} {{
            set target [lindex $nocc_list 0]
        }} elseif {{ $num >= 9 && $num <= 20 }} {{
            set target [lindex $nocc_list 1]
        }} else {{
            set target [lindex $nocc_list 2]
        }}
        puts "传输到 NOCC节点 $target"

        ## 执行传输动作
        send "sshpass -p passw0rd@123 scp -o StrictHostKeyChecking=no node-status-$ip.yaml root@$target:/home/resource_manager/resource_info\r"
        expect "# "
    }}
    
    # tsn 获取自身资源信息，发送至NOCC
    set target [lindex $nocc_list 0]
    send "echo '正在转发TSN节点信息到NOCC节点 $target'\r"
    expect "# "
    send "bash /home/resource_manager/status_sender.sh --ip $target\r"
    expect "# "
}} errMsg

puts "退出TSN的VM控制"
sleep 1
send "exit\r"

sleep 1
send "exit\r"

if {{$errMsg ne ""}} {{
    puts "警告：主逻辑中发生错误：$errMsg"
}}
"""

            # 将expect脚本保存到临时文件并执行
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.exp') as script_file:
                script_file.write(expect_script)
                script_path = script_file.name

            # 使脚本可执行
            os.chmod(script_path, 0o755)
            # 创建日志目录
            logs_dir = "scan_logs_temp"
            os.makedirs(logs_dir, exist_ok=True)
            
            # 创建日志文件名，包含时间戳以避免覆盖
            log_filename = f"tsn{original_tsn_idx}_scan_{time.strftime('%Y%m%d_%H%M%S')}.log"
            log_path = os.path.join(logs_dir, log_filename)

            # 执行expect脚本并将输出重定向到日志文件
            logger.info(f"TSN{original_tsn_idx}({tsn_vm_ip}) 正在扫描: {', '.join(dg_info)}")
            logger.info(f"脚本输出将保存到: {log_path}")
            
            with open(log_path, 'w') as log_file:
                result = subprocess.run(['expect', script_path], 
                                    stdout=log_file, 
                                    stderr=subprocess.STDOUT)
            
            # 检查返回码
            if result.returncode == 0:
                logger.info(f"TSN{original_tsn_idx} 成功完成所有扫描任务并转发NOCC，详细日志: {log_path}")
            else:
                logger.error(f"TSN{original_tsn_idx} 扫描任务失败，请查看日志: {log_path}")
                
            # 删除临时脚本文件
            os.unlink(script_path)
            
        except Exception as e:
            logger.error(f"TSN{original_tsn_idx} 执行扫描任务时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='TSN节点扫描工具')
    parser.add_argument('--csv_file', required=True, help='网络拓扑矩阵CSV文件路径')
    parser.add_argument('--container-tsn-prefix', default='clab-sat-network-TSN', 
                        help='TSN容器名称前缀，默认为clab-sat-network-TSN')
    parser.add_argument('--container-yg-prefix', default='clab-sat-network-YG', 
                        help='YG容器名称前缀，默认为clab-sat-network-YG')
    parser.add_argument('--container-xw-prefix', default='clab-sat-network-XW',
                        help='XW容器名称前缀，默认为clab-sat-network-XW')
    args = parser.parse_args()
    
    logger.info(f"启动TSN扫描，使用网络拓扑文件: {args.csv_file}")

    scanner = TSNScanner(base_tsn_container_name=args.container_tsn_prefix,
                         base_yg_container_name=args.container_yg_prefix,
                         base_xw_container_name=args.container_xw_prefix,
                         csv_file=args.csv_file)
    
    scan_start_time = time.time()
    success = scanner.scan_connected_nodes()
    scan_elapsed = time.time() - scan_start_time
    
    if success:
        logger.info(f"扫描完成 (耗时: {scan_elapsed:.2f}秒)")
    else:
        logger.error("扫描失败")

if __name__ == "__main__":
    main()
