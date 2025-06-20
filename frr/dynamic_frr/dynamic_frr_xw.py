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

class NetworkTopologyManager:
    def __init__(self, base_container_name="clab-sat-network-XW",csv_dir='csv_xw'):
        """
        初始化网络拓扑管理器
        
        参数:
        - base_container_name: 容器名称的前缀
        """
        self.base_container_name = base_container_name
        self.csv_dir = csv_dir
        self.current_matrix = None
        self.current_links = set()  # 存储当前已建立的链路 (node1, node2, ip_info)
        self.sat_num = 0
        self.ip_mapping = {}  # 存储节点对到IP地址的映射
        logger.info("网络拓扑管理器初始化完成")
        
    def read_matrix_from_csv(self, csv_file):
        """从CSV文件读取链路可见性矩阵"""
        try:
            # 使用pandas读取CSV文件，不设置列名或索引列
            df = pd.read_csv(csv_file, header=None, sep=',', dtype=float)
            matrix = df.values
            
            # 验证矩阵格式
            rows, cols = matrix.shape
            if rows != cols:
                logger.warning(f"矩阵不是方阵！行数: {rows}, 列数: {cols}")
            
            logger.info(f"成功读取矩阵，大小: {matrix.shape}")
            sat_num = rows
            return matrix
        except Exception as e:
            logger.error(f"读取CSV文件错误: {e}")
            logger.exception("详细错误信息:")
            return None
    

    def generate_ip_addresses(self, node1, node2):
        """根据节点编号生成唯一的IP地址对"""
        """同一链路的两端必须处于同一子网中，不同链路之间的端口ip必须处于不同子网中"""
        """划分范围10.0.16.0/30 -- 10.0.64.0/30"""
        original_node1, original_node2 = node1+1, node2+1
        key = (min(original_node1, original_node2), max(original_node1, original_node2))
        if key in self.ip_mapping:
            return self.ip_mapping[key]
        
        # 计算第三个网段
        third_byte = ( original_node1*original_node2 // 64 ) + 16
        
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
        # 记录原始顺序的节点编号
        original_node1, original_node2 = node1+1, node2+1
        
        
        # 生成IP地址对
        ip1, ip2 = self.generate_ip_addresses(node1, node2)
        logger.info(f"创建链路: {original_node1} <-> {original_node2} (IP: {ip1} <-> {ip2})")
        
        script = f"""
        # 创建veth pair
        sudo ip link add {original_node1}-{original_node2} type veth peer name {original_node2}-{original_node1}
        
        # 配置第一个容器
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {self.base_container_name}{original_node1})
        sudo ip link set {original_node1}-{original_node2} netns $n1_pid
        sudo nsenter -t $n1_pid -n ip link set {original_node1}-{original_node2} up
        sudo nsenter -t $n1_pid -n ip addr add {ip1} dev {original_node1}-{original_node2}
        
        # 配置第二个容器
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {self.base_container_name}{original_node2})
        sudo ip link set {original_node2}-{original_node1} netns $n2_pid
        sudo nsenter -t $n2_pid -n ip link set {original_node2}-{original_node1} up
        sudo nsenter -t $n2_pid -n ip addr add {ip2} dev {original_node2}-{original_node1}
        """
        
        success = self.execute_script(script)
        if success:
            # 使用IP地址而不是子网ID来存储链路信息
            self.current_links.add((min(node1, node2), max(node1, node2), f"{ip1}-{ip2}"))
            return True
        return False
    
    def delete_link(self, node1, node2):
        """删除两个节点之间的链路"""
        # 记录原始顺序的节点编号
        original_node1, original_node2 = node1+1, node2+1
        
        # 获取链路的IP地址，仅用于日志记录
        ip1, ip2 = self.generate_ip_addresses(node1, node2)
        logger.info(f"删除链路: {original_node1} <-> {original_node2} (IP: {ip1} <-> {ip2})")
        
        script = f"""
        # 尝试获取容器PID
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {self.base_container_name}{original_node1} 2>/dev/null)
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {self.base_container_name}{original_node2} 2>/dev/null)
        
        # 检查容器是否存在
        if [ -z "$n1_pid" ] || [ "$n1_pid" = "<no value>" ]; then
            echo "容器 {self.base_container_name}{original_node1} 不存在或无法获取PID"
        else
            # 删除第一个容器中的接口
            sudo nsenter -t $n1_pid -n ip link delete {original_node1}-{original_node2} 2>/dev/null || true
        fi
        
        if [ -z "$n2_pid" ] || [ "$n2_pid" = "<no value>" ]; then
            echo "容器 {self.base_container_name}{original_node2} 不存在或无法获取PID"
        else
            # 删除第二个容器中的接口
            sudo nsenter -t $n2_pid -n ip link delete {original_node2}-{original_node1} 2>/dev/null || true
        fi
        """
        
        success = self.execute_script(script)
        if success:
            # 从当前链路集合中移除
            for link in list(self.current_links):
                if (link[0] == min(node1, node2) and link[1] == max(node1, node2)):
                    self.current_links.remove(link)
                    logger.debug(f"从当前链路集合中移除: {link}")
            return True
        return False
    
    def modify_link(self, node1, node2, delay):
        """修改两个节点之间的链路延迟等属性参数"""
        # 记录原始顺序的节点编号
        original_node1, original_node2 = node1+1, node2+1
        

        real_delay = delay // 300
        
        
        logger.info(f"设置链路延迟: {original_node1} <-> {original_node2} (DELAY: {real_delay} ms)")
        
        script = f"""
        # 在添加规则前，清空可能存在的旧规则
        docker exec "{self.base_container_name}{original_node1}" bash -c "tc qdisc del dev {original_node1}-{original_node2} root"
        docker exec "{self.base_container_name}{original_node2}" bash -c "tc qdisc del dev {original_node2}-{original_node1} root"  
        
        # 对该链路双端均添加延迟控制
        docker exec "{self.base_container_name}{original_node1}" bash -c "
        tc qdisc add dev {original_node1}-{original_node2} root netem delay {real_delay}ms" || {{
            echo "添加规则失败，请检查接口或参数。"
            exit 1
        }}

        # docker exec "{self.base_container_name}{original_node2}" bash -c "
        # tc qdisc add dev {original_node2}-{original_node1} root netem delay {real_delay}ms" || {{
        #     echo "添加规则失败，请检查接口或参数。"
        #     exit 1
        # }}
        """
        
        success = self.execute_script(script)

        return success
    
    def execute_script(self, script):
        """执行bash脚本"""
        try:
            result = subprocess.run(script, shell=True, check=True, 
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            return True
        except subprocess.SubprocessError as e:
            logger.error(f"执行脚本错误: {e}")
            logger.error(f"错误输出: {e.stderr.decode() if hasattr(e, 'stderr') else 'N/A'}")
            return False
    
    def find_differences(self, old_matrix, new_matrix):
        """对比两个矩阵，找出需要添加和删除的链路"""
        to_add = []
        to_remove = []
        to_modify = []
        # 获取两个矩阵的最小尺寸
        n = min(old_matrix.shape[0], new_matrix.shape[0])
        
        for i in range(n):
            for j in range(i+1, n):  # 只处理上三角矩阵，避免重复
                # 原本没有链路（值<0），现在有了（值>=0）-> 添加
                if old_matrix[i, j] < 0 and new_matrix[i, j] >= 0:
                    to_add.append((i, j))
                    logger.debug(f"需要添加链路: {i} <-> {j} (值: {new_matrix[i, j]})")
                
                # 原本有链路（值>=0），现在没了（值<0）-> 删除  
                elif old_matrix[i, j] >= 0 and new_matrix[i, j] < 0:
                    to_remove.append((i, j))
                    logger.debug(f"需要删除链路: {i} <-> {j}")
                
                # 原本有链路（值>=0），现在有了（值>=0）但值不同-> 修改
                elif old_matrix[i, j] >= 0 and new_matrix[i, j] >= 0 and old_matrix[i, j] != new_matrix[i, j]:
                    to_modify.append((i, j))
                    logger.debug(f"需要修改链路: {i} <-> {j} (原值: {old_matrix[i, j]}, 新值: {new_matrix[i, j]})")
        
        logger.info(f"找到 {len(to_add)} 条需要添加的链路，{len(to_remove)} 条需要删除的链路，{len(to_modify)} 条需要修改的链路")
        return to_add, to_remove, to_modify
    
    def validate_csv_file(self, csv_file):
        """验证CSV文件的格式是否符合要求"""
        try:
            # 检查文件是否存在
            if not os.path.exists(csv_file):
                logger.error(f"CSV文件不存在: {csv_file}")
                return False
                
            # 检查文件是否为空
            if os.path.getsize(csv_file) == 0:
                logger.error(f"CSV文件为空: {csv_file}")
                return False
                
            # 尝试读取文件内容
            with open(csv_file, 'r') as f:
                first_line = f.readline().strip()
                # 检查第一行是否包含逗号（CSV格式）
                if ',' not in first_line:
                    logger.warning(f"CSV文件可能格式不正确，第一行未发现逗号: {first_line}")
                    
            return True
        except Exception as e:
            logger.error(f"验证CSV文件出错: {e}")
            return False
    
    def process_links_in_batches(self, links, operation, batch_size=10, new_matrix=None):
        """分批处理链路操作，支持创建或删除"""
        total = len(links)
        success_count = 0
        
        for i in range(0, total, batch_size):
            batch = links[i:i+batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}/{(total+batch_size-1)//batch_size}，{operation}链路...")
            
            for node1, node2 in batch:
                if operation == "create_link": # "创建"
                    success = self.create_link(node1, node2)
                    if success and new_matrix is not None:
                        delay = new_matrix[node1, node2]
                        success = self.modify_link(node1, node2, delay)
                elif operation == "delete_link":  # "删除"
                    success = self.delete_link(node1, node2)
                elif operation == "modify_link":  # "修改"
                    delay = new_matrix[node1, node2]
                    success = self.modify_link(node1, node2, delay)

                if success:
                    success_count += 1
                    
            # 批处理之间短暂等待，避免系统过载
            if i + batch_size < total:
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
            n = new_matrix.shape[0]
            logger.info(f"首次初始化，矩阵大小: {n}x{n}")
            
            links_to_create = []
            for i in range(n):
                for j in range(i+1, n):  # 只处理上三角矩阵
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
        
        n = self.current_matrix.shape[0]
        active_links = 0
        
        for i in range(n):
            for j in range(i+1, n):
                if self.current_matrix[i, j] >= 0:
                    active_links += 1
        
        logger.info(f"当前网络拓扑状态:")
        logger.info(f"  容器数量: {n}")
        logger.info(f"  活跃链路: {active_links}")
        logger.info(f"  总链路容量: {n * (n-1) // 2}")
    
    def process_csv_directory(self, directory, interval=20):
        """处理目录中的所有CSV文件，按时间间隔更新网络拓扑"""
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
            return
         
        logger.info(f"找到 {len(csv_files)} 个CSV文件待处理，排序后的顺序:")
        for i, f in enumerate(csv_files):
            logger.info(f"  {i+1}. {f.name}")
        
        # 处理每个CSV文件
        for i, csv_file in enumerate(csv_files):
            logger.info(f"\n{'='*50}")
            logger.info(f"处理文件 [{i+1}/{len(csv_files)}]: {csv_file}")
            
            # 验证并更新网络拓扑
            if self.validate_csv_file(csv_file):
                start_time = time.time()
                success = self.update_topology(csv_file)
                elapsed = time.time() - start_time
                
                if success:
                    logger.info(f"成功应用拓扑: {csv_file.name} (耗时: {elapsed:.2f}秒)")
                else:
                    logger.error(f"应用拓扑失败: {csv_file.name}")
            
            # 等待指定的时间间隔
            if i < len(csv_files) - 1:
                logger.info(f"等待 {interval} 秒后处理下一个文件...")
                time.sleep(interval)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='动态网络拓扑管理')
    parser.add_argument('--csv_dir', default='csv_xw',help='包含CSV文件的目录路径，默认值为csv_xw')
    parser.add_argument('--interval', type=int, default=20, help='更新间隔（秒），默认20秒')
    parser.add_argument('--container-prefix', default='clab-sat-network-XW', 
                        help='容器名称前缀，默认为clab-sat-network-XW')
    
    args = parser.parse_args()
    
    logger.info(f"启动网络拓扑管理，处理目录: {args.csv_dir}，更新间隔: {args.interval}秒")
    
    manager = NetworkTopologyManager(base_container_name=args.container_prefix, csv_dir=args.csv_dir)
    manager.process_csv_directory(args.csv_dir, args.interval)

if __name__ == "__main__":
    main()
