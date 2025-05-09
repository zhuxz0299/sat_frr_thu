import pandas as pd
import numpy as np
import subprocess
import os
import time
import re
from pathlib import Path
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NetworkTopologyManager:
    def __init__(self, base_tsn_container_name="clab-sat-network-TSN",
                 base_yg_container_name="clab-sat-network-YG",
                 base_xw_container_name="clab-sat-network-XW",
                 csv_dir='csv_tsn'
                 ):
        """
        初始化网络拓扑管理器
        
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
        logger.info("网络拓扑管理器初始化完成")
        
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
            
        
        # 生成IP地址对
        
        
        
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
        # 在添加规则前，清空可能存在的旧规则
        docker exec "{tsn_container_name}" bash -c "tc qdisc del dev {veth_tsn} root"
        docker exec "{dg_container_name}" bash -c "tc qdisc del dev {veth_dg} root"  
        
        # 对该链路单端添加延迟控制
        docker exec "{tsn_container_name}" bash -c "
        tc qdisc add dev {veth_tsn} root netem delay {real_delay}ms" || {{
            echo "添加规则失败，请检查接口或参数。"
            exit 1
        }}

        # docker exec "{dg_container_name}" bash -c "
        # tc qdisc add dev {veth_dg} root netem delay {real_delay}ms" || {{
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
        # 默认矩阵尺寸不随时间片变化
        rows, cols = new_matrix.shape
        
        for i in range(rows):
            for j in range(cols):  # 处理TSN-DG全矩阵
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
    
    def process_links_in_batches(self, links, operation, batch_size=20, new_matrix=None):
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
                    # 添加扫描步骤：在建链完成后执行扫描
                    logger.info("开始执行本轮TSN域扫描...")
                    scan_start_time = time.time()
                    self.scan_connected_nodes()  # 执行扫描
                    scan_elapsed = time.time() - scan_start_time
                    logger.info(f"扫描完成 (耗时: {scan_elapsed:.2f}秒)")
                else:
                    logger.error(f"应用拓扑失败: {csv_file.name}")
            
            # 等待指定的时间间隔
            if i < len(csv_files) - 1:
                logger.info(f"等待 {interval} 秒后处理下一个文件...")
                time.sleep(interval)

    def vm_sat_ip_map(self,type,idx):
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
            return
        
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

    def _scan_single_tsn_node(self, tsn_idx):
        """扫描单个TSN节点连接的所有低轨卫星节点"""

        original_tsn_idx = tsn_idx + 1  # 转换为原始节点编号
        tsn_container_name = f"{self.base_tsn_container_name}{original_tsn_idx}"
        
        # 查找与当前TSN节点相连的所有低轨卫星节点IP
        dg_ips = [] 
        # 收集详细信息用于日志记录
        dg_info = []

        # 获取当前TSN的VM信息
        tsn_vm_name, tsn_vm_ip = self.vm_sat_ip_map("TSN",original_tsn_idx)
        
        for dg_idx in range(self.current_matrix.shape[1]):
            if self.current_matrix[tsn_idx, dg_idx] >= 0:
                if dg_idx < 12:  # YG节点
                    original_dg_idx = dg_idx + 1
                    # dg_container_name = f"{self.base_yg_container_name}{original_dg_idx}"
                    # connected_nodes.append((dg_container_name, "YG", original_dg_idx))
                    dg_type = "YG"
                else:  # XW节点
                    original_dg_idx = dg_idx - 12 + 1
                    # dg_container_name = f"{self.base_xw_container_name}{original_dg_idx}"
                    # connected_nodes.append((dg_container_name, "XW", original_dg_idx))
                    dg_type = "XW"

                dg_vm_name, dg_vm_ip = self.vm_sat_ip_map(dg_type,original_dg_idx)
                dg_ips.append(dg_vm_ip)
                dg_info.append(f"{dg_type}{original_dg_idx}({dg_vm_ip})")

        if not dg_ips:
            logger.info(f"TSN{original_tsn_idx} 没有连接的低轨卫星节点")  
            return

        logger.info(f"TSN{original_tsn_idx} 开始扫描 {len(dg_ips)} 个连接的低轨卫星节点")  
        
        try:
            # 创建expect脚本，将所有IP作为列表传入
            dg_ips_tcl_list = " ".join([f"\"{ip}\"" for ip in dg_ips])

            # NOCC-TSN/NOCC-XW/NOCC-YG ip地址, 顺序在分配ip时有点乱，后续改
            nocc_ips = ["10.0.203.2","10.0.201.2","10.0.202.2"]
            nocc_ips_tcl_list = " ".join([f"\"{ip}\"" for ip in nocc_ips])
        
            expect_template = r"""#!/usr/bin/expect -f
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
expect "Password:"
send "passw0rd@123\r"

expect "# "


# 循环处理每个IP
foreach ip $dg_list {{
    puts "正在扫描可见域内低轨卫星IP: $ip"
    send "/home/resource_manager/resource_request.sh -p passw0rd@123 -u root -i $ip &\r"
    # expect "# "
}}

# tsn扫描完成后，将/home/resource_manager/resource_info文件夹下的所有文件发送到对应的NOCC节点，并删除该目录下所有文件

puts "TSN扫描完成，资源纳管信息正在从TSN中转至NOCC"
send "cd /home/resource_manager/resource_info\r"
expect "# "

# 发送ls命令
send "ls -1\r"
#--- 等待命令输出结束：等待下一个提示符出现 ---
puts "输出结束，等待读取文件列表"
expect {{
    -re "(.*)\r\n$prompt" {{
        # 捕获 ls 的所有输出，保存在 expect_out(1,string)
        set raw_output $expect_out(1,string)
    }}
    timeout {{
        puts "ls 命令执行超时"
        exit 2
    }}
}}

puts $raw_output
#--- raw_output 里现在类似：
#    "node_status-10.0.64.122.yaml\r\n
#     node_status-10.0.64.126.yaml\r\n
#     ……"
#--- 把它按行拆分成一个 Tcl 列表
set yaml_files [split $raw_output "\r\n"]

# （可选）去掉列表里可能的空字符串
set yaml_files [lselect $yaml_files {string length > 0}]

foreach file $yaml_files {{
    # 提取第四个字段
    regexp {{node_status-(\d+\.\d+\.\d+\.(\d+))\.yaml}} $file _ full_ip fourth
    # 计算节点编号: (fourth-2)/4 + 1
    set num [expr ((int($fourth) - 2) / 4) + 1]
    # 选择目标NOCC节点
    if {{ $num >= 1 && $num <= 8 }} {{
        set target [lindex $nocc_list 0]
    }} elseif {{ $num >= 9 && $num <= 20 }} {{
        set target [lindex $nocc_list 1]
    }} else {{
        set target [lindex $nocc_list 2]
    }}
    puts "传输 $file 到 NOCC节点 $target"
    # exec sshpass -p "passw0rd@123" scp -o StrictHostKeyChecking=no $file root@$target:/home/resource_manager/resource_info
    exec rm $file
}}


# 退出TSN的VM控制
sleep 1
send "exit\r"

sleep 1
send "exit\r"

"""
            expect_script = expect_template.format(
                dg_list=dg_ips_tcl_list,
                nocc_list=nocc_ips_tcl_list,
                tsn_vm_name=tsn_vm_name
            )
            # 将expect脚本保存到临时文件并执行
            import tempfile
            import os
            import subprocess

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.exp') as script_file:
                script_file.write(expect_script)
                script_path = script_file.name

            # 使脚本可执行
            os.chmod(script_path, 0o755)
            # 创建日志目录
            logs_dir = "scan_logs_4"
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

# root身份运行，确保注入脚本权限正常
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='动态网络拓扑管理')
    parser.add_argument('--csv_dir',default='csv_tsn_modify', help='包含CSV文件的目录路径,默认为csv_tsn_modify')
    parser.add_argument('--interval', type=int, default=60, help='更新间隔（秒），默认60秒')
    parser.add_argument('--container-tsn-prefix', default='clab-sat-network-TSN', 
                        help='TSN容器名称前缀，默认为clab-sat-network-TSN')
    parser.add_argument('--container-yg-prefix', default='clab-sat-network-YG', 
                        help='YG容器名称前缀，默认为clab-sat-network-YG')
    parser.add_argument('--container-xw-prefix', default='clab-sat-network-XW',
                        help='XW容器名称前缀，默认为clab-sat-network-XW')
    args = parser.parse_args()
    
    logger.info(f"启动网络拓扑管理，处理目录: {args.csv_dir}，更新间隔: {args.interval}秒")

    manager = NetworkTopologyManager(base_tsn_container_name=args.container_tsn_prefix,
                                    base_yg_container_name=args.container_yg_prefix,
                                    base_xw_container_name=args.container_xw_prefix,
                                    )
    manager.process_csv_directory(args.csv_dir, args.interval)

if __name__ == "__main__":
    main()
