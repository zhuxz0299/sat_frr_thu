import pandas as pd
import subprocess
import logging
import os
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NetworkTopologyManager:
    def __init__(self, base_tsn_container_name="clab-sat-network-TSN",
                 base_yg_container_name="clab-sat-network-YG",
                 base_xw_container_name="clab-sat-network-XW"):
        """
        初始化网络拓扑管理器，仅保留删除链路功能
        """
        self.base_tsn_container_name = base_tsn_container_name
        self.base_yg_container_name = base_yg_container_name
        self.base_xw_container_name = base_xw_container_name
        self.ip_mapping = {}  # 节点对到IP地址映射（用于日志）
        logger.info("网络拓扑管理器初始化完成")

    def read_matrix_from_csv(self, csv_file):
        """从CSV文件读取链路矩阵"""
        try:
            df = pd.read_csv(csv_file, header=None, sep=',', dtype=float)
            matrix = df.values
            rows, cols = matrix.shape
            logger.info(f"成功读取矩阵，大小: {rows}x{cols}")
            return matrix
        except Exception as e:
            logger.error(f"读取CSV文件错误: {e}")
            return None

    def generate_ip_addresses(self, node1, node2):
        """根据节点编号生成唯一的IP地址对，用于日志显示"""
        original_node1, original_node2 = node1 + 1, node2 + 1
        key = (original_node1, original_node2)
        if key in self.ip_mapping:
            return self.ip_mapping[key]
        third_byte = (original_node1 * original_node2) // 64
        fourth_byte = (original_node1 * original_node2) % 64 * 4 + 1
        ip1 = f"10.0.{third_byte}.{fourth_byte}/30"
        ip2 = f"10.0.{third_byte}.{fourth_byte + 1}/30"
        self.ip_mapping[key] = (ip1, ip2)
        return ip1, ip2

    def delete_link(self, node1, node2):
        """删除两个节点之间的链路"""
        original_node1 = node1 + 1
        ip1, ip2 = self.generate_ip_addresses(node1, node2)

        if node2 < 12:
            original_node2 = node2 + 1
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
        # 删除宿主机上的veth接口，忽略错误
        sudo ip link del {veth_tsn} 2>/dev/null || true
        sudo ip link del {veth_dg} 2>/dev/null || true

        # 获取容器PID
        n1_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {tsn_container_name} 2>/dev/null)
        n2_pid=$(docker inspect -f '{{{{.State.Pid}}}}' {dg_container_name} 2>/dev/null)

        # 删除容器内接口，容器不存在或接口不存在不报错
        if [ -n "$n1_pid" ] && [ "$n1_pid" != "<no value>" ]; then
            sudo nsenter -t $n1_pid -n ip link del {veth_tsn} 2>/dev/null || true
        else
            echo "容器 {tsn_container_name} 不存在或无法获取PID"
        fi

        if [ -n "$n2_pid" ] && [ "$n2_pid" != "<no value>" ]; then
            sudo nsenter -t $n2_pid -n ip link del {veth_dg} 2>/dev/null || true
        else
            echo "容器 {dg_container_name} 不存在或无法获取PID"
        fi
        """
        return self.execute_script(script)

    def execute_script(self, script):
        """执行bash脚本"""
        try:
            result = subprocess.run(script, shell=True, check=True,
                                    stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            logger.debug(f"脚本执行成功，输出: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"执行脚本错误: {e}")
            logger.error(f"错误输出: {e.stderr.decode().strip() if e.stderr else 'N/A'}")
            return False

    def delete_links_from_csv(self, csv_file):
        """根据CSV文件删除所有非负标记的链路"""
        matrix = self.read_matrix_from_csv(csv_file)
        if matrix is None:
            logger.error("读取矩阵失败，无法删除链路")
            return False

        rows, cols = matrix.shape
        links_to_delete = []
        for i in range(rows):
            for j in range(cols):
                if matrix[i, j] >= 0:
                    links_to_delete.append((i, j))

        total = len(links_to_delete)
        logger.info(f"准备删除 {total} 条链路")
        success_count = 0
        batch_size = 20
        for i in range(0, total, batch_size):
            batch = links_to_delete[i:i+batch_size]
            logger.info(f"删除链路批次 {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
            for node1, node2 in batch:
                if self.delete_link(node1, node2):
                    success_count += 1
            time.sleep(0.5)  # 防止系统过载

        logger.info(f"链路删除完成: 成功 {success_count}/{total}")
        return success_count == total

def main():
    import argparse

    parser = argparse.ArgumentParser(description='基于CSV文件删除原有网络链路')
    parser.add_argument('--csv_file', required=True, help='待处理的CSV文件路径')
    parser.add_argument('--container-tsn-prefix', default='clab-sat-network-TSN',
                        help='TSN容器名称前缀，默认clab-sat-network-TSN')
    parser.add_argument('--container-yg-prefix', default='clab-sat-network-YG',
                        help='YG容器名称前缀，默认clab-sat-network-YG')
    parser.add_argument('--container-xw-prefix', default='clab-sat-network-XW',
                        help='XW容器名称前缀，默认clab-sat-network-XW')
    args = parser.parse_args()

    if not os.path.isfile(args.csv_file):
        logger.error(f"指定的CSV文件不存在: {args.csv_file}")
        return

    manager = NetworkTopologyManager(
        base_tsn_container_name=args.container_tsn_prefix,
        base_yg_container_name=args.container_yg_prefix,
        base_xw_container_name=args.container_xw_prefix
    )

    logger.info(f"开始处理CSV文件: {args.csv_file}")
    success = manager.delete_links_from_csv(args.csv_file)
    if success:
        logger.info("所有链路删除操作完成")
    else:
        logger.error("链路删除过程中出现错误")

if __name__ == "__main__":
    main()
