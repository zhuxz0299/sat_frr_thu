#!/usr/bin/env python3
# filepath: /home/zxz/875/sat_simulator/frr/dynamic_frr/frr_network_builder.py
import pandas as pd
import numpy as np
import subprocess
import os
import time
import re
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NetworkTopologyBuilder:
    def __init__(self, base_tsn_container_name="clab-sat-network-TSN",
                 base_yg_container_name="clab-sat-network-YG",
                 base_xw_container_name="clab-sat-network-XW",
                 csv_dir='csv_tsn_modify'
                 ):
        """
        初始化网络拓扑构建器
        
        参数:
        - base_container_name: 容器名称的前缀
        """
        self.base_tsn_container_name = base_tsn_container_name
        self.base_yg_container_name = base_yg_container_name
        self.base_xw_container_name = base_xw_container_name
        self.csv_dir = csv_dir
        self.current_matrix = None
        self.current_links = set()  # 存储当前已建立的链路 (node1, node2, ip_info)
        self.ip_mapping = {}  # 存储节点对到IP地址的映射
        logger.info("网络拓扑构建器初始化完成")
        
    def read_matrix_from_csv(self, csv_file):
        """从CSV文件读取链路可见性矩阵"""
        try:
            # 使用pandas读取CSV文件，不设置列名或索引列
            df = pd.read_csv(csv_file, header=None, sep=',', dtype=float)
            matrix = df.values
            
            # 验证矩阵格式
            rows, cols = matrix.shape
            
            logger.info(f"成功读取矩阵，大小: {rows}x{cols}")
            return matrix
        except Exception as e:
            logger.error(f"读取CSV文件错误: {e}")
            logger.exception("详细错误信息:")
            return None
    
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
    
    def generate_ip_addresses(self, node1, node2):
        """根据节点编号生成唯一的IP地址对"""
        """同一链路的两端必须处于同一子网中，不同链路之间的端口ip必须处于不同子网中"""
        """划分范围10.0.0.0/30 -- 10.0.15.0/30"""
        original_node1, original_node2 = node1+1, node2+1
        key = (original_node1, original_node2)
        if key in self.ip_mapping:
            return self.ip_mapping[key]
        
        # 计算第三个网段
        third_byte = ( original_node1*original_node2 // 64 )
        
        # 计算第四个网段
        fourth_byte = ( original_node1*original_node2 % 64 ) * 4 + 1
        
        # 生成第一个IP
        ip1 = f"10.0.{third_byte}.{fourth_byte}/30"
        
        # 生成第二个IP (第四个字节+1)
        ip2 = f"10.0.{third_byte}.{fourth_byte + 1}/30"

        self.ip_mapping[key] = (ip1, ip2)
        
        return ip1, ip2
        
    def create_link(self, node1, node2):
        """创建两个节点之间的链路"""

        ip1, ip2 = self.generate_ip_addresses(node1, node2)

        original_node1 = node1+1
        
        if node2 < 12:
            original_node2 = node2+1
            logger.info(f"创建链路: TSN{original_node1} <-> YG{original_node2} (IP: {ip1} <-> {ip2})")
            veth_tsn = f"tsn{original_node1}-yg{original_node2}"
            veth_dg = f"yg{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_yg_container_name}{original_node2}"
        else:
            original_node2 = node2 - 11
            logger.info(f"创建链路: TSN{original_node1} <-> XW{original_node2} (IP: {ip1} <-> {ip2})")
            veth_tsn = f"tsn{original_node1}-xw{original_node2}"
            veth_dg = f"xw{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_xw_container_name}{original_node2}"
            
        # 设置带宽限制为50kb
        bandwidth = "50kbit"
        logger.info(f"设置链路带宽限制: {bandwidth}")
        
        script = f"""
        # 创建veth pair
        sudo ip link add {veth_tsn} type veth peer name {veth_dg}
        
        # 配置第一个容器
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {tsn_container_name})
        sudo ip link set {veth_tsn} netns $n1_pid
        sudo nsenter -t $n1_pid -n ip link set {veth_tsn} up
        sudo nsenter -t $n1_pid -n ip addr add {ip1} dev {veth_tsn}
        
        # 配置第二个容器
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {dg_container_name})
        sudo ip link set {veth_dg} netns $n2_pid
        sudo nsenter -t $n2_pid -n ip link set {veth_dg} up
        sudo nsenter -t $n2_pid -n ip addr add {ip2} dev {veth_dg}
        
        # 设置带宽限制 (50kb)
        sudo nsenter -t $n1_pid -n tc qdisc add dev {veth_tsn} root tbf rate {bandwidth} burst 5kb latency 70ms
        sudo nsenter -t $n2_pid -n tc qdisc add dev {veth_dg} root tbf rate {bandwidth} burst 5kb latency 70ms
        """
        
        success = self.execute_script(script)
        if success:
            # 使用IP地址而不是子网ID来存储链路信息
            self.current_links.add((node1, node2, f"{ip1}-{ip2}"))
            return True
        return False
    
    def delete_link(self, node1, node2):
        """删除两个节点之间的链路"""
        # 记录原始顺序的节点编号
        original_node1 = node1+1
        
        # 获取链路的IP地址，仅用于日志记录
        ip1, ip2 = self.generate_ip_addresses(node1, node2)
        
        if node2 < 12:
            original_node2 = node2+1
            logger.info(f"删除链路: TSN{original_node1} <-> YG{original_node2} (IP: {ip1} <-> {ip2})")
            veth_tsn = f"tsn{original_node1}-yg{original_node2}"
            veth_dg = f"yg{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_yg_container_name}{original_node2}"
        else:
            original_node2 = node2 - 11
            logger.info(f"删除链路: TSN{original_node1} <-> XW{original_node2} (IP: {ip1} <-> {ip2})")
            veth_tsn = f"tsn{original_node1}-xw{original_node2}"
            veth_dg = f"xw{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_xw_container_name}{original_node2}"
        
        script = f"""
        # 尝试获取容器PID
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {tsn_container_name} 2>/dev/null)
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {dg_container_name} 2>/dev/null)
        
        # 检查容器是否存在
        if [ -z "$n1_pid" ] || [ "$n1_pid" = "<no value>" ]; then
            echo "容器 {tsn_container_name} 不存在或无法获取PID"
        else
            # 删除第一个容器中的接口
            sudo nsenter -t $n1_pid -n ip link delete {veth_tsn} 2>/dev/null || true
        fi
        
        if [ -z "$n2_pid" ] || [ "$n2_pid" = "<no value>" ]; then
            echo "容器 {dg_container_name} 不存在或无法获取PID"
        else
            # 删除第二个容器中的接口
            sudo nsenter -t $n2_pid -n ip link delete {veth_dg} 2>/dev/null || true
        fi
        """
        
        success = self.execute_script(script)
        if success:
            # 从当前链路集合中移除
            for link in list(self.current_links):
                if (link[0] == node1 and link[1] == node2):
                    self.current_links.remove(link)
                    logger.debug(f"从当前链路集合中移除: {link}")
            return True
        return False
    
    def modify_link(self, node1, node2, delay):
        """修改两个节点之间的链路延迟等属性参数"""
        # 记录原始顺序的节点编号
        original_node1 = node1+1
        
        real_delay = delay
        bandwidth = "50kbit"  # 保持带宽限制为50kb
        
        if node2 < 12:
            original_node2 = node2+1
            logger.info(f"设置链路延迟: TSN{original_node1} <-> YG{original_node2} (DELAY: {real_delay} ms)")
            veth_tsn = f"tsn{original_node1}-yg{original_node2}"
            veth_dg = f"yg{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_yg_container_name}{original_node2}"
        else:
            original_node2 = node2 - 11
            logger.info(f"设置链路延迟: TSN{original_node1} <-> XW{original_node2} (DELAY: {real_delay} ms)")
            veth_tsn = f"tsn{original_node1}-xw{original_node2}"
            veth_dg = f"xw{original_node2}-tsn{original_node1}"
            tsn_container_name = f"{self.base_tsn_container_name}{original_node1}"
            dg_container_name = f"{self.base_xw_container_name}{original_node2}"
        
        script = f"""
        # 尝试获取容器PID
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {tsn_container_name} 2>/dev/null)
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {dg_container_name} 2>/dev/null)
        
        # 清除现有的TC规则（如果有）
        sudo nsenter -t $n1_pid -n tc qdisc del dev {veth_tsn} root 2>/dev/null || true
        sudo nsenter -t $n2_pid -n tc qdisc del dev {veth_dg} root 2>/dev/null || true
        
        # 添加新的TC规则设置延迟
        sudo nsenter -t $n1_pid -n tc qdisc add dev {veth_tsn} root netem delay {real_delay}ms
        sudo nsenter -t $n2_pid -n tc qdisc add dev {veth_dg} root netem delay {real_delay}ms
        
        # 重新设置带宽限制 (50kb)
        sudo nsenter -t $n1_pid -n tc qdisc add dev {veth_tsn} handle 1: root tbf rate {bandwidth} burst 5kb latency 70ms
        sudo nsenter -t $n2_pid -n tc qdisc add dev {veth_dg} handle 1: root tbf rate {bandwidth} burst 5kb latency 70ms
        """
        
        success = self.execute_script(script)
        return success
    
    def execute_script(self, script):
        """执行shell脚本并检查是否成功"""
        try:
            # 执行脚本，使用bash -c确保命令被正确解析
            result = subprocess.run(['bash', '-c', script], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    text=True)
            
            # 检查返回码
            if result.returncode == 0:
                return True
            else:
                logger.warning(f"脚本执行失败，返回码: {result.returncode}")
                logger.debug(f"错误输出: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"执行脚本时出错: {e}")
            return False
    
    def find_differences(self, old_matrix, new_matrix):
        """找出两个矩阵之间的差异链路"""
        rows, cols = old_matrix.shape
        new_rows, new_cols = new_matrix.shape
        
        # 确保矩阵大小相同
        if rows != new_rows or cols != new_cols:
            logger.error(f"矩阵大小不匹配: 旧矩阵 {rows}x{cols} vs 新矩阵 {new_rows}x{new_cols}")
            return [], [], []
        
        to_add = []
        to_remove = []
        to_modify = []
        
        for i in range(rows):
            for j in range(cols):
                # 链路存在与否的状态变化
                if old_matrix[i, j] < 0 and new_matrix[i, j] >= 0:
                    # 需要添加链路
                    to_add.append((i, j))
                elif old_matrix[i, j] >= 0 and new_matrix[i, j] < 0:
                    # 需要删除链路
                    to_remove.append((i, j))
                elif old_matrix[i, j] >= 0 and new_matrix[i, j] >= 0 and old_matrix[i, j] != new_matrix[i, j]:
                    # 链路属性变化，需要修改
                    to_modify.append((i, j))
        
        logger.info(f"识别到差异: 添加 {len(to_add)} 条链路, 删除 {len(to_remove)} 条链路, 修改 {len(to_modify)} 条链路")
        return to_add, to_remove, to_modify
    
    def validate_csv_file(self, csv_file):
        """验证CSV文件是否有效"""
        try:
            df = pd.read_csv(csv_file, header=None, sep=',', dtype=float)
            matrix = df.values
            
            # 检查矩阵维度
            rows, cols = matrix.shape
            if rows == 0 or cols == 0:
                logger.error(f"无效的矩阵尺寸: {rows}x{cols}")
                return False
                
            # 检查矩阵值是否合法
            for i in range(rows):
                for j in range(cols):
                    # 这里可以添加任何值的验证逻辑
                    pass
                    
            return True
        except Exception as e:
            logger.error(f"CSV文件验证失败: {e}")
            return False
    
    def process_links_in_batches(self, links, operation, batch_size=20, new_matrix=None):
        """
        批处理方式处理链路的创建、删除或修改
        
        参数:
        - links: 待处理的链路列表，每个链路为元组 (node1, node2)
        - operation: 要执行的操作，可以是 "create_link"、"delete_link" 或 "modify_link"
        - batch_size: 每批处理的链路数
        - new_matrix: 如果有新矩阵，用于获取链路属性如延迟
        """
        total = len(links)
        logger.info(f"开始{operation}，共 {total} 个链路，批次大小 {batch_size}")
        
        success_count = 0
        
        # 获取操作函数
        op_func = getattr(self, operation)
        
        for i in range(0, total, batch_size):
            batch = links[i:i+batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}，包含 {len(batch)} 个链路")
            
            # 对批处理中的每个链路创建一个线程
            for node1, node2 in batch:
                try:
                    if operation == "modify_link" and new_matrix is not None:
                        # 修改链路需要传递延迟参数
                        delay = new_matrix[node1, node2]
                        if op_func(node1, node2, delay):
                            success_count += 1
                    else:
                        # 创建或删除链路
                        if op_func(node1, node2):
                            success_count += 1
                except Exception as e:
                    logger.error(f"{operation} 链路 {node1}-{node2} 时出错: {e}")
            
            # 批次间短暂暂停，避免系统负载过高
            time.sleep(0.5)
        
        logger.info(f"{operation}链路完成: {success_count}/{total} 成功")
        return success_count
    
    def update_topology(self, csv_file):
        """根据CSV文件更新网络拓扑"""
        new_matrix = self.read_matrix_from_csv(csv_file)
        if new_matrix is None:
            logger.error("无法更新拓扑：读取矩阵失败")
            return False
        
        if self.current_matrix is not None:
            # 找出需要添加和删除的链路
            to_add, to_remove, to_modify = self.find_differences(self.current_matrix, new_matrix)
            
            # 使用批处理删除旧链路
            if to_remove:
                self.process_links_in_batches(to_remove, "delete_link", new_matrix=new_matrix)
            
            # 使用批处理添加新链路
            if to_add:
                self.process_links_in_batches(to_add, "create_link", new_matrix=new_matrix)

            # 使用批处理修改链路
            if to_modify:
                self.process_links_in_batches(to_modify, "modify_link", new_matrix=new_matrix)
                    
        else:
            # 第一次运行，初始化所有链路
            rows,cols = new_matrix.shape
            logger.info(f"首次初始化，矩阵大小: {rows}x{cols}")
            
            links_to_create = []
            for i in range(rows):
                for j in range(cols):  # 处理TSN-DG全矩阵
                    if new_matrix[i, j] >= 0:  # 如果有链路
                        links_to_create.append((i, j))
            
            if links_to_create:
                self.process_links_in_batches(links_to_create, "create_link", new_matrix=new_matrix)
        
        # 更新当前矩阵
        self.current_matrix = new_matrix
        # 显示当前拓扑状态
        self.print_topology_status()
        return True
    
    def print_topology_status(self):
        """打印当前网络拓扑状态"""
        if self.current_matrix is None:
            logger.info("当前没有加载任何网络拓扑")
            return
        
        rows,cols = self.current_matrix.shape
        active_links = 0
        
        for i in range(rows):
            for j in range(cols):
                if self.current_matrix[i, j] >= 0:
                    active_links += 1
        
        logger.info(f"当前网络拓扑状态:")
        logger.info(f"  容器数量: {rows}TSN-{cols}DG")
        logger.info(f"  活跃链路: {active_links}")
        logger.info(f"  总链路容量: {rows * cols}")
    
    def build_network_from_csv(self, directory):    
        """从CSV目录中选择第一个文件构建网络拓扑"""
        directory = Path(directory)
        
        # 尝试以数字顺序排序CSV文件（例如output_1.csv, output_2.csv...）
        def get_csv_number(filename):
            # 从文件名中提取数字
            match = re.search(r'(\d+)', filename.stem)
            if match:
                return int(match.group(1))
            return float('inf')  # 没有数字的放到最后
        
        # 获取目录中的所有CSV文件并排序
        csv_files = sorted([f for f in directory.glob("*.csv")], key=get_csv_number)
        
        if not csv_files:
            logger.error(f"目录 {directory} 中没有找到CSV文件")
            return False
         
        logger.info(f"找到 {len(csv_files)} 个CSV文件，将使用第一个文件: {csv_files[0].name}")
        
        # 只处理第一个CSV文件
        csv_file = csv_files[0]
        logger.info(f"处理文件: {csv_file}")
        
        # 验证并更新网络拓扑
        if self.validate_csv_file(csv_file):
            start_time = time.time()
            success = self.update_topology(csv_file)
            elapsed = time.time() - start_time
            
            if success:
                logger.info(f"成功应用拓扑: {csv_file.name} (耗时: {elapsed:.2f}秒)")
                
                # 生成分域表并写入到TSN节点
                logger.info("开始生成分域表并写入到TSN节点...")
                domain_start_time = time.time()
                domain_success = self.generate_domain_tables()
                domain_elapsed = time.time() - domain_start_time
                
                if domain_success:
                    logger.info(f"分域表生成完成 (耗时: {domain_elapsed:.2f}秒)")
                else:
                    logger.warning("分域表生成过程中出现问题，请检查日志")
                
                return True
            else:
                logger.error(f"应用拓扑失败: {csv_file.name}")
                return False
        else:
            logger.error(f"CSV文件验证失败: {csv_file}")
            return False
    def generate_domain_tables(self):
        """为每个TSN节点生成分域表（能看到的低轨卫星IP列表）并写入到TSN节点"""
        if self.current_matrix is None:
            logger.error("当前没有加载任何网络拓扑，无法生成分域表")
            return False
        
        rows, cols = self.current_matrix.shape
        logger.info(f"开始为 {rows} 个TSN节点生成分域表")
        
        for tsn_idx in range(rows):
            original_tsn_idx = tsn_idx + 1  # 转换为原始节点编号
            
            # 查找与当前TSN节点相连的所有低轨卫星节点IP
            dg_ips = [] 
            dg_info = []  # 用于日志记录

            # 获取当前TSN的VM信息
            tsn_vm_name, tsn_vm_ip = self.vm_sat_ip_map("TSN", original_tsn_idx)
            
            for dg_idx in range(cols):
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
                continue
            
            # 创建分域表文件内容
            dg_ips_str = " ".join(dg_ips)
            
            # 写入分域表到TSN节点
            self.write_domain_table_to_tsn(tsn_vm_name, dg_ips_str, original_tsn_idx, dg_info)
        
        logger.info("所有TSN节点分域表生成完成")
        return True
    
    def write_domain_table_to_tsn(self, tsn_vm_name, dg_ips_str, tsn_idx, dg_info):
        """将分域表写入到TSN节点"""
        try:
            import tempfile
            
            logger.info(f"TSN{tsn_idx} 写入分域表: {', '.join(dg_info)}")
            
            # 创建expect脚本将分域表写入TSN
            expect_script = f"""#!/usr/bin/expect -f
# 设置超时时间
set timeout 60

# 连接到TSN的VM
spawn sudo virsh console {tsn_vm_name}

sleep 1
send "\r"

expect "localhost login:"
send "root\r"
expect "密码："
send "passw0rd@123\r"

expect "# "

# 确保目录存在
send "mkdir -p /home/resource_manager/domain_tables\r"
expect "# "

# 写入分域表
send "echo '{dg_ips_str}' > /home/resource_manager/domain_tables/domain_table.txt\r"
expect "# "

# 检查文件内容
send "cat /home/resource_manager/domain_tables/domain_table.txt\r"
expect "# "

# 退出VM控制台
send "exit\r"
sleep 1
send "exit\r"
"""
            # 将expect脚本保存到临时文件并执行
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.exp') as script_file:
                script_file.write(expect_script)
                script_path = script_file.name
            
            # 使脚本可执行
            os.chmod(script_path, 0o755)
            
            # 执行expect脚本
            result = subprocess.run(['expect', script_path], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    text=True)
            
            # 检查返回码
            if result.returncode == 0:
                logger.info(f"TSN{tsn_idx} 成功写入分域表")
            else:
                logger.error(f"TSN{tsn_idx} 写入分域表失败: {result.stderr}")
                
            # 删除临时脚本文件
            os.unlink(script_path)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"TSN{tsn_idx} 写入分域表时出错: {e}")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='FRR网络拓扑构建')
    parser.add_argument('--csv_dir', default='csv_tsn_modify', help='包含CSV文件的目录路径,默认为csv_tsn_modify')
    parser.add_argument('--container-tsn-prefix', default='clab-sat-network-TSN', 
                        help='TSN容器名称前缀，默认为clab-sat-network-TSN')
    parser.add_argument('--container-yg-prefix', default='clab-sat-network-YG', 
                        help='YG容器名称前缀，默认为clab-sat-network-YG')
    parser.add_argument('--container-xw-prefix', default='clab-sat-network-XW',
                        help='XW容器名称前缀，默认为clab-sat-network-XW')
    args = parser.parse_args()
    
    logger.info(f"启动FRR网络拓扑构建，处理目录: {args.csv_dir}")

    builder = NetworkTopologyBuilder(base_tsn_container_name=args.container_tsn_prefix,
                                     base_yg_container_name=args.container_yg_prefix,
                                     base_xw_container_name=args.container_xw_prefix,
                                     )
    success = builder.build_network_from_csv(args.csv_dir)
    
    if success:
        logger.info("FRR网络拓扑构建成功")
    else:
        logger.error("FRR网络拓扑构建失败")

if __name__ == "__main__":
    main()
