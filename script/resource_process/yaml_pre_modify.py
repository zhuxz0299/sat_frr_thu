#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

"""
YAML文件预处理脚本
用于向node-status YAML文件中添加linkList字段
"""

import yaml
import random
import os
import csv
from typing import List, Dict, Any, Tuple

class YAMLPreModifier:
    def __init__(self):
        # 链路类型和带宽配置（使用BW值，按波段分类通信类型）
        self.link_configs = {
            # 激光链路
            "低轨星间": {"bw": 15, "unit": 3, "type": "laser"},  # BW值15, 15Gbps
            "中轨星间": {"bw": 10, "unit": 3, "type": "laser"},  # BW值10, 10Gbps
            "高轨星间": {"bw": 30, "unit": 3, "type": "laser"},  # BW值30, 30Gbps
            "中低轨间": {"bw": 25, "unit": 3, "type": "laser"},  # BW值25, 25Gbps
            "高低": {"bw": 20, "unit": 3, "type": "laser"},     # BW值20, 20Gbps
            "高中": {"bw": 3, "unit": 3, "type": "laser"},      # BW值3, 3Gbps
            
            # Ka波段（相控阵）
            "低轨对地相控阵": {"bw": 200, "unit": 2, "type": "Ka"},    # BW值200, 200M
            "中轨对地相控阵": {"bw": 300, "unit": 2, "type": "Ka"},    # BW值300, 300M
            "高轨对地机械": {"bw": 301, "unit": 2, "type": "Ka"},      # BW值301, 300M
            "高轨对地相控阵": {"bw": 500, "unit": 2, "type": "Ka"},    # BW值500, 500M
            "高低轨相控阵": {"bw": 201, "unit": 2, "type": "Ka"},      # BW值201, 200M
            "中低轨相控阵": {"bw": 202, "unit": 2, "type": "Ka"},      # BW值202, 200M
            "低轨间相控阵": {"bw": 150, "unit": 2, "type": "Ka"},      # BW值150, 150M
            
            # Ku波段
            "高轨对地": {"bw": 100, "unit": 2, "type": "Ku"},          # BW值100, 100M
            
            # L/S波段
            "高低轨机械": {"bw": 50, "unit": 2, "type": "L/S"},        # BW值50, 50M
            "高轨对地_LS": {"bw": 101, "unit": 2, "type": "L/S"},     # BW值101, 100M
            "中轨对地_LS": {"bw": 102, "unit": 2, "type": "L/S"},     # BW值102, 100M
            "低轨对地": {"bw": 51, "unit": 2, "type": "L/S"},          # BW值51, 50M
            
            # X波段
            "中轨对地": {"bw": 52, "unit": 2, "type": "X"},            # BW值52, 50M
            
            # C馈电
            "高轨对NOCC_C": {"bw": 501, "unit": 2, "type": "C"},      # BW值501, 500M
            
            # Ka馈电
            "低轨对NOCC": {"bw": 1000, "unit": 2, "type": "Ka"},      # BW值1000, 1G
            "中轨对NOCC": {"bw": 1001, "unit": 2, "type": "Ka"},      # BW值1001, 1G
            "高轨对NOCC": {"bw": 1002, "unit": 2, "type": "Ka"},      # BW值1002, 1G
        }
        
        # 数据传输速率单位映射
        # 0 bps, 1 Kbps, 2 Mbps, 3 Gbps, 4 Tbps
        self.rate_unit_map = {
            0: "bps",
            1: "Kbps", 
            2: "Mbps",
            3: "Gbps",
            4: "Tbps"
        }
        
        # 载入CSV数据
        self.tsn_connections = self.load_csv_matrix("./frr/dynamic_frr/csv_tsn_modify/output_1.csv")
        self.xw_connections = self.load_csv_matrix("./frr/dynamic_frr/csv_xw/output_1.csv")

    def load_csv_matrix(self, csv_path: str) -> List[List[float]]:
        """
        载入CSV文件并转换为矩阵
        
        Args:
            csv_path: CSV文件路径
            
        Returns:
            二维列表表示的矩阵
        """
        matrix = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    float_row = []
                    for cell in row:
                        try:
                            val = float(cell.strip())
                            float_row.append(val)
                        except ValueError:
                            float_row.append(-1.0)
                    matrix.append(float_row)
            print(f"成功载入CSV文件: {csv_path}, 大小: {len(matrix)}x{len(matrix[0]) if matrix else 0}")
        except Exception as e:
            print(f"载入CSV文件 {csv_path} 失败: {str(e)}")
            matrix = []
        return matrix

    def ip_to_sat_id(self, ip_str: str) -> int:
        """从IP地址反推卫星ID
        
        Args:
            ip_str: IP地址字符串，格式如 "10.0.64.46"
        
        Returns:
            int: 卫星ID，如果无法解析则返回None
        """
        # 提取IP地址
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_str)
        if not ip_match:
            return None
        
        ip = ip_match.group(1)
        parts = ip.split('.')
        if len(parts) != 4:
            return None
        
        try:
            fourth_byte = int(parts[3])
            idx = (fourth_byte - 2) // 4 + 1
            return idx
        except (ValueError, IndexError):
            return None

    def get_connections_for_sat(self, sat_id: int) -> List[Tuple[int, str]]:
        """
        获取指定卫星的连接信息
        
        Args:
            sat_id: 卫星ID
            
        Returns:
            连接列表，每个元素是(目标卫星ID, 链路类型)的元组
        """
        connections = []
        
        # 检查TSN连接 (ID 1-8 与 9-44)
        if self.tsn_connections:
            # 如果是1-8的卫星，检查与9-44的连接
            if 1 <= sat_id <= 8:
                row_idx = sat_id - 1
                if row_idx < len(self.tsn_connections):
                    row = self.tsn_connections[row_idx]
                    for col_idx, value in enumerate(row):
                        if value > 0:  # 有连接
                            target_sat_id = col_idx + 9  # 列索引对应9-44
                            if target_sat_id <= 44:
                                connections.append((target_sat_id, "中低轨间"))
            
            # 如果是9-44的卫星，检查与1-8的连接
            elif 9 <= sat_id <= 44:
                col_idx = sat_id - 9
                for row_idx, row in enumerate(self.tsn_connections):
                    if col_idx < len(row) and row[col_idx] > 0:
                        source_sat_id = row_idx + 1  # 行索引对应1-8
                        if source_sat_id <= 8:
                            connections.append((source_sat_id, "中低轨间"))
        
        # 检查XW连接 (ID 21-44 之间)
        if self.xw_connections and 21 <= sat_id <= 44:
            row_idx = sat_id - 21
            if row_idx < len(self.xw_connections):
                row = self.xw_connections[row_idx]
                for col_idx, value in enumerate(row):
                    if value > 0:  # 有连接
                        target_sat_id = col_idx + 21  # 列索引对应21-44
                        if target_sat_id <= 44 and target_sat_id != sat_id:
                            connections.append((target_sat_id, "低轨星间"))
        
        return connections

    def generate_link_info(self, link_type: str, end_sat_id: str) -> Dict[str, Any]:
        """
        生成单个链路信息
        
        Args:
            link_type: 链路类型
            end_sat_id: 目标卫星ID
            
        Returns:
            链路信息字典
        """
        config = self.link_configs.get(link_type, self.link_configs["低轨星间"])
        
        # 生成随机的时延、抖动、丢包率
        base_delay = 50.0 if "星间" in link_type else 100.0
        delay = round(random.uniform(base_delay, base_delay + 30), 1)
        jitter = round(random.uniform(0, 2.0), 1)
        loss = round(random.uniform(0, 1.0), 1)
        
        return {
            "health": 1,  # 1 健康
            "type": config["type"],
            "rate": config["bw"],
            "rate_data_type": config["unit"],
            "delay": delay,
            "jitter": jitter,
            "loss": loss,
            "end_sat_id": end_sat_id
        }

    def generate_link_list_for_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        根据文件路径中的IP地址生成链路列表
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            链路信息列表
        """
        link_list = []
        
        # 从文件名中提取IP地址并推断卫星ID
        sat_id = self.ip_to_sat_id(file_path)
        
        if sat_id is None:
            print(f"无法从文件路径 {file_path} 中提取有效的卫星ID")
            return link_list
        
        print(f"文件 {file_path} 对应卫星ID: {sat_id}")
        
        # 获取该卫星的连接信息
        connections = self.get_connections_for_sat(sat_id)
        
        if not connections:
            print(f"卫星ID {sat_id} 没有找到连接信息")
            return link_list
        
        # 为每个连接生成链路信息
        for target_sat_id, link_type in connections:
            end_sat_id = target_sat_id
            link_info = self.generate_link_info(link_type, end_sat_id)
            link_list.append(link_info)
        
        print(f"为卫星ID {sat_id} 生成了 {len(link_list)} 个连接")
        return link_list
    
    def modify_yaml_file(self, file_path: str, output_path: str = None) -> bool:
        """
        修改YAML文件，添加linkList字段
        
        Args:
            file_path: 源YAML文件路径
            output_path: 输出文件路径，如果为None则覆盖原文件
            
        Returns:
            是否成功
        """
        try:
            # 读取原YAML文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                data = {}
            
            # 确保spec字段存在
            if 'spec' not in data:
                data['spec'] = {}
            
            # 根据文件路径生成linkList
            link_list = self.generate_link_list_for_file(file_path)
            data['spec']['linkList'] = link_list
            
            # 写入文件
            output_file = output_path if output_path else file_path
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"成功修改文件: {output_file}")
            print(f"添加了 {len(link_list)} 个链路信息")
            
            return True
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {str(e)}")
            return False

    def process_directory(self, dir_path: str, pattern: str = "node-status-*.yaml") -> int:
        """
        批量处理目录中的YAML文件
        
        Args:
            dir_path: 目录路径
            pattern: 文件名模式
            
        Returns:
            成功处理的文件数量
        """
        import glob
        
        pattern_path = os.path.join(dir_path, pattern)
        files = glob.glob(pattern_path)
        
        success_count = 0
        for file_path in files:
            if self.modify_yaml_file(file_path):
                success_count += 1
        
        print(f"批量处理完成，成功处理 {success_count}/{len(files)} 个文件")
        return success_count
    
    def process_all_directories(self) -> int:
        """
        处理所有指定目录中的YAML文件
        
        Returns:
            成功处理的文件总数
        """
        directories = [
            "./resource_info/vm45/",
            "./resource_info/vm46/", 
            "./resource_info/vm47/"
        ]
        
        total_success = 0
        
        for dir_path in directories:
            if os.path.exists(dir_path):
                print(f"\n处理目录: {dir_path}")
                success_count = self.process_directory(dir_path)
                total_success += success_count
            else:
                print(f"目录不存在，跳过: {dir_path}")
        
        print(f"\n总计成功处理 {total_success} 个文件")
        return total_success

def main():
    """主函数"""
    modifier = YAMLPreModifier()
    
    # 处理所有指定目录中的YAML文件
    modifier.process_all_directories()

if __name__ == "__main__":
    main()