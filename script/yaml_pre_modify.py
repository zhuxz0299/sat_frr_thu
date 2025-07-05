#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YAML文件预处理脚本
用于向node-status YAML文件中添加linkList字段
"""

import yaml
import random
import os
from typing import List, Dict, Any

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
            "health": 1, # 1 健康
            "type": config["type"],
            "rate": config["bw"],
            "rate_data_type": config["unit"],
            "delay": delay,
            "jitter": jitter,
            "loss": loss,
            "end_sat_id": end_sat_id
        }

    def generate_link_list(self, num_links: int = 3) -> List[Dict[str, Any]]:
        """
        生成链路列表
        
        Args:
            num_links: 生成的链路数量
            
        Returns:
            链路信息列表
        """
        link_list = []
        
        # 优先生成低轨相关的链路
        low_orbit_links = [
            "低轨星间", "低轨对地相控阵", "高低轨相控阵", 
            "中低轨相控阵", "低轨间相控阵", "低轨对地", "低轨对NOCC"
        ]
        

        for i in range(num_links):
            # 随机选择链路类型（优先低轨相关）
            if i < len(low_orbit_links):
                link_type = random.choice(low_orbit_links[:3])  # 主要使用前3种
            else:
                link_type = random.choice(list(self.link_configs.keys()))
            # 生成目标卫星ID
            end_sat_id = f"sat-{random.randint(10, 20):02d}"
            
            link_info = self.generate_link_info(link_type, end_sat_id)
            link_list.append(link_info)
        
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
            
            # 生成linkList
            link_list = self.generate_link_list()
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

def main():
    """主函数"""
    modifier = YAMLPreModifier()
    
    # 处理指定的文件
    target_file = "./resource_info/vm47/node-status-10.0.64.34.yaml"
    
    if os.path.exists(target_file):
        print(f"正在处理文件: {target_file}")
        modifier.modify_yaml_file(target_file)
    else:
        print(f"文件不存在: {target_file}")
    
    # 可选：批量处理整个目录
    # vm47_dir = "./resource_info/vm47/"
    # if os.path.exists(vm47_dir):
    #     print(f"\n批量处理目录: {vm47_dir}")
    #     modifier.process_directory(vm47_dir)

if __name__ == "__main__":
    main()