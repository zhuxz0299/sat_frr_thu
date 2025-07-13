#!/usr/bin/env python3
"""
星座资源分析脚本
用法: python constellation_resource_analyzer.py [资源类型]
功能: 分析 tsn_constellation.json, xw_constellation.json, yg_constellation.json 文件
资源类型选项: cpu, gpu, memory, disk, gpu_mem, link, sensor, all
输出: 指定资源类型的分类统计
"""

import json
import os
import sys
import argparse
from collections import defaultdict
from typing import Dict, List, Set, Tuple

class ConstellationResourceAnalyzer:
    def __init__(self):
        # 链路配置定义 (从yaml_pre_modify.py中复制)
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
        
        # 传感器类型定义
        self.sensor_types = {
            0: "SAR合成孔径雷达",
            1: "HW红外",
            2: "KJG可见光"
        }
        
        # 数据单位定义
        self.data_units = {
            0: "bps",
            1: "Kbps", 
            2: "Mbps",
            3: "Gbps",
            4: "Tbps"
        }
        
        # 存储分析结果
        self.resource_types = defaultdict(set)   # 资源种类 -> 卫星ID集合
        
    def load_constellation_data(self, file_path: str) -> Dict:
        """
        加载constellation JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            解析后的JSON数据
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"成功加载文件: {file_path}")
            return data
        except Exception as e:
            print(f"加载文件 {file_path} 失败: {e}")
            return {}
    
    def get_link_type_name(self, rate: float, rate_data_type: int) -> str:
        """
        根据rate和rate_data_type获取链路类型名称
        
        Args:
            rate: 传输速率值
            rate_data_type: 传输速率单位类型
            
        Returns:
            链路类型名称，如果找不到匹配的则返回自定义名称
        """
        for link_name, config in self.link_configs.items():
            if config["bw"] == rate and config["unit"] == rate_data_type:
                return link_name
        
        # 如果找不到匹配的预定义类型，生成自定义名称
        unit_name = self.data_units.get(rate_data_type, "unknown")
        return f"自定义链路_{rate}_{unit_name}"
    
    def analyze_resource_types(self, constellation_data: Dict):
        """
        分析资源种类
        
        Args:
            constellation_data: constellation数据
        """
        task_info = constellation_data.get('task_info', [])
        
        for satellite in task_info:
            sat_id = satellite.get('sat_id')
            if sat_id is None:
                continue
            
            # CPU资源
            if 'cpu_usage' in satellite:
                self.resource_types['cpu'].add(sat_id)
            
            # GPU资源、GPU内存资源
            if 'gpu_usage' in satellite:
                self.resource_types['gpu'].add(sat_id)
                self.resource_types['gpu_mem'].add(sat_id)
            
            # 磁盘资源
            if 'disk_usage' in satellite:
                self.resource_types['disk'].add(sat_id)
            
            # 内存资源
            if 'mem_usage' in satellite:
                self.resource_types['memory'].add(sat_id)
            
            # 传感器资源
            sensors = satellite.get('sensors', [])
            for sensor in sensors:
                sensor_type = sensor.get('sensor_type')
                if sensor_type is not None:
                    sensor_name = self.sensor_types.get(sensor_type, f"未知传感器_{sensor_type}")
                    resource_key = f"sensor_{sensor_name}"
                    self.resource_types[resource_key].add(sat_id)
            
            # 链路资源
            link_list = satellite.get('linkList', [])
            for link in link_list:
                rate = link.get('rate')
                rate_data_type = link.get('rate_data_type')
                if rate is not None and rate_data_type is not None:
                    link_type_name = self.get_link_type_name(rate, rate_data_type)
                    resource_key = f"link_{link_type_name}"
                    self.resource_types[resource_key].add(sat_id)
    
    def add_all_predefined_link_types(self):
        """
        添加所有预定义的链路类型到资源种类中，即使它们在JSON中没有出现
        """
        for link_name in self.link_configs.keys():
            resource_key = f"link_{link_name}"
            if resource_key not in self.resource_types:
                self.resource_types[resource_key] = set()
    
    def analyze_all_constellations(self, specific_file=None):
        """
        分析所有constellation文件或指定文件
        
        Args:
            specific_file: 指定要分析的文件路径，如果为None则分析所有默认文件
        """
        if specific_file:
            # 分析指定的单个文件
            if os.path.exists(specific_file):
                data = self.load_constellation_data(specific_file)
                if data:
                    print(f"分析指定文件: {specific_file}")
                    self.analyze_resource_types(data)
                else:
                    print(f"加载文件失败: {specific_file}")
            else:
                print(f"文件不存在: {specific_file}")
                return
        else:
            # 分析默认的constellation文件
            base_dir = "resource_info"
            files = {
                'tsn': f"{base_dir}/tsn_constellation.json",
                'xw': f"{base_dir}/xw_constellation.json", 
                'yg': f"{base_dir}/yg_constellation.json"
            }
            
            # 分析每个constellation文件
            for constellation_type, file_path in files.items():
                if os.path.exists(file_path):
                    data = self.load_constellation_data(file_path)
                    if data:
                        print(f"分析 {constellation_type} 星座...")
                        self.analyze_resource_types(data)
                else:
                    print(f"文件不存在: {file_path}")
        
        # 添加所有预定义的链路类型
        self.add_all_predefined_link_types()
    
    def print_results(self, resource_filter=None):
        """
        打印分析结果
        
        Args:
            resource_filter: 资源类型过滤器，如果为None则显示所有资源
        """
        print("\n" + "="*80)
        print("星座资源分析结果")
        print("="*80)
        
        if resource_filter == 'cpu' or resource_filter == 'all' or resource_filter is None:
            self._print_basic_resource('cpu', 'CPU资源')
        
        if resource_filter == 'gpu' or resource_filter == 'all' or resource_filter is None:
            self._print_basic_resource('gpu', 'GPU资源')
        
        if resource_filter == 'memory' or resource_filter == 'all' or resource_filter is None:
            self._print_basic_resource('memory', '内存资源')
        
        if resource_filter == 'disk' or resource_filter == 'all' or resource_filter is None:
            self._print_basic_resource('disk', '磁盘资源')
        
        if resource_filter == 'gpu_mem' or resource_filter == 'all' or resource_filter is None:
            self._print_basic_resource('gpu_mem', 'GPU内存资源')
        
        if resource_filter == 'sensor' or resource_filter == 'all' or resource_filter is None:
            self._print_sensor_resources()
        
        if resource_filter == 'link' or resource_filter == 'all' or resource_filter is None:
            self._print_link_resources()
        
        # 统计信息
        if resource_filter == 'all' or resource_filter is None:
            print("\n【统计信息】")
            print("-" * 50)
            print(f"资源种类数量: {len(self.resource_types)}")
    
    def _print_basic_resource(self, resource_key: str, resource_name: str):
        """
        打印基础资源信息
        
        Args:
            resource_key: 资源键名
            resource_name: 资源显示名称
        """
        print(f"\n【{resource_name}】")
        print("-" * 50)
        if resource_key in self.resource_types:
            sat_ids = sorted(list(self.resource_types[resource_key]))
            print(f"拥有{resource_name}的卫星: {sat_ids}")
            print(f"数量: {len(sat_ids)}")
        else:
            print(f"无卫星拥有{resource_name}")
    
    def _print_sensor_resources(self):
        """
        打印传感器资源信息
        """
        print("\n【传感器资源】")
        print("-" * 50)
        sensor_resources = [k for k in self.resource_types.keys() if k.startswith('sensor_')]
        if sensor_resources:
            for resource in sorted(sensor_resources):
                sat_ids = sorted(list(self.resource_types[resource]))
                resource_name = resource.replace('sensor_', '')
                if sat_ids:
                    print(f"{resource_name}: {sat_ids} (数量: {len(sat_ids)})")
                else:
                    print(f"{resource_name}: 无卫星")
        else:
            print("无传感器资源")
    
    def _print_link_resources(self):
        """
        打印链路资源信息
        """
        print("\n【链路资源】")
        print("-" * 50)
        link_resources = [k for k in self.resource_types.keys() if k.startswith('link_')]
        if link_resources:
            for resource in sorted(link_resources):
                sat_ids = sorted(list(self.resource_types[resource]))
                resource_name = resource.replace('link_', '')
                if sat_ids:
                    print(f"{resource_name}: {sat_ids} (数量: {len(sat_ids)})")
                else:
                    print(f"{resource_name}: 无卫星")
        else:
            print("无链路资源")

def parse_arguments():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(
        description='星座资源分析脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
资源类型说明：
  cpu      - CPU资源
  gpu      - GPU资源
  memory   - 内存资源
  disk     - 磁盘资源
  gpu_mem  - GPU内存资源
  sensor   - 传感器资源
  link     - 链路资源
  all      - 所有资源（默认）

使用示例：
  python constellation_resource_analyzer.py                        # 分析所有资源（默认文件）
  python constellation_resource_analyzer.py cpu                    # 仅分析CPU资源（默认文件）
  python constellation_resource_analyzer.py sensor                 # 仅分析传感器资源（默认文件）
  python constellation_resource_analyzer.py -f file.json           # 分析指定文件的所有资源
  python constellation_resource_analyzer.py cpu -f file.json       # 分析指定文件的CPU资源
        """
    )
    
    parser.add_argument(
        'resource_type',
        nargs='?',
        default='all',
        choices=['cpu', 'gpu', 'memory', 'disk', 'gpu_mem', 'sensor', 'link', 'all'],
        help='要分析的资源类型 (默认: all)'
    )
    
    parser.add_argument(
        '-f', '--file',
        type=str,
        help='指定要分析的JSON文件路径。如果不指定，则分析默认的三个constellation文件'
    )
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_arguments()
    
    print(f"开始分析星座配置文件...")
    if args.resource_type != 'all':
        print(f"资源类型过滤器: {args.resource_type}")
    
    if args.file:
        print(f"指定文件: {args.file}")
    else:
        print("分析模式: 默认文件（tsn、xw、yg星座）")
    
    analyzer = ConstellationResourceAnalyzer()
    analyzer.analyze_all_constellations(specific_file=args.file)
    analyzer.print_results(resource_filter=args.resource_type)
    
    print("\n分析完成!")

if __name__ == "__main__":
    main()
