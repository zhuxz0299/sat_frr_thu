#!/usr/bin/env python3
"""
YAML文件批量生成脚本
用于在resource_info/vm_demo底下生成1000个node-status YAML文件
文件格式参考resource_info/vm46底下的yaml文件
"""

import os
import yaml
import random
import datetime
from typing import List, Dict, Any

class YAMLGenerator:
    def __init__(self):
        # 链路配置定义
        self.link_configs = {
            # 激光链路
            "低轨星间": {"bw": 15, "unit": 3, "type": "laser", "source_types": ["XW", "YG"], "target_types": ["XW", "YG"]},
            "中轨星间": {"bw": 10, "unit": 3, "type": "laser", "source_types": ["TSN"], "target_types": ["TSN"]},
            "高轨星间": {"bw": 30, "unit": 3, "type": "laser", "source_types": ["HEO"], "target_types": ["HEO"]},
            "中低轨间": {"bw": 25, "unit": 3, "type": "laser", "source_types": ["TSN"], "target_types": ["XW", "YG"]},
            "高低": {"bw": 20, "unit": 3, "type": "laser", "source_types": ["HEO"], "target_types": ["XW", "YG"]},
            "高中": {"bw": 3, "unit": 3, "type": "laser", "source_types": ["HEO"], "target_types": ["TSN"]},
            
            # Ka波段（相控阵）
            "低轨对地相控阵": {"bw": 200, "unit": 2, "type": "Ka", "source_types": ["XW", "YG"], "target_types": ["GROUND"]},
            "中轨对地相控阵": {"bw": 300, "unit": 2, "type": "Ka", "source_types": ["TSN"], "target_types": ["GROUND"]},
            "高轨对地机械": {"bw": 301, "unit": 2, "type": "Ka", "source_types": ["HEO"], "target_types": ["GROUND"]},
            "高轨对地相控阵": {"bw": 500, "unit": 2, "type": "Ka", "source_types": ["HEO"], "target_types": ["GROUND"]},
            "高低轨相控阵": {"bw": 201, "unit": 2, "type": "Ka", "source_types": ["HEO"], "target_types": ["XW", "YG"]},
            "中低轨相控阵": {"bw": 202, "unit": 2, "type": "Ka", "source_types": ["TSN"], "target_types": ["XW", "YG"]},
            "低轨间相控阵": {"bw": 150, "unit": 2, "type": "Ka", "source_types": ["XW", "YG"], "target_types": ["XW", "YG"]},
            
            # Ku波段
            "高轨对地": {"bw": 100, "unit": 2, "type": "Ku", "source_types": ["HEO"], "target_types": ["GROUND"]},
            
            # L/S波段
            "高低轨机械": {"bw": 50, "unit": 2, "type": "L/S", "source_types": ["HEO"], "target_types": ["XW", "YG"]},
            "高轨对地_LS": {"bw": 101, "unit": 2, "type": "L/S", "source_types": ["HEO"], "target_types": ["GROUND"]},
            "中轨对地_LS": {"bw": 102, "unit": 2, "type": "L/S", "source_types": ["TSN"], "target_types": ["GROUND"]},
            "低轨对地": {"bw": 51, "unit": 2, "type": "L/S", "source_types": ["XW", "YG"], "target_types": ["GROUND"]},
            
            # X波段
            "中轨对地": {"bw": 52, "unit": 2, "type": "X", "source_types": ["TSN"], "target_types": ["GROUND"]},
            
            # C馈电
            "高轨对NOCC_C": {"bw": 501, "unit": 2, "type": "C", "source_types": ["HEO"], "target_types": ["NOCC"]},
            
            # Ka馈电
            "低轨对NOCC": {"bw": 1000, "unit": 2, "type": "Ka", "source_types": ["XW", "YG"], "target_types": ["NOCC"]},
            "中轨对NOCC": {"bw": 1001, "unit": 2, "type": "Ka", "source_types": ["TSN"], "target_types": ["NOCC"]},
            "高轨对NOCC": {"bw": 1002, "unit": 2, "type": "Ka", "source_types": ["HEO"], "target_types": ["NOCC"]},
        }

        # 传感器类型定义
        self.sensor_types = {
            0: "SAR合成孔径雷达",
            1: "HW红外",
            2: "KJG可见光"
        }
        
        # 卫星类型配置 - XW数量最多，YG次之，其他较少
        self.satellite_configs = {
            "XW": {"count": 600, "percentage": 0.60},        # 低轨，占60%
            "YG": {"count": 300, "percentage": 0.30},        # 低轨，占30%
            "TSN": {"count": 40, "percentage": 0.04},        # 中轨，占4%
            "HEO": {"count": 30, "percentage": 0.03},        # 高轨，占3%
            "NOCC": {"count": 15, "percentage": 0.015},      # NOCC，占1.5%
            "GROUND": {"count": 15, "percentage": 0.015}     # 地面，占1.5%
        }
        
        # 预设的IP地址基础
        self.base_ip = "10.0.64"
        
        # 目标目录
        self.output_dir = "resource_info/vm_demo"
        
        # 用于记录已使用的链路，确保所有链路类型都被包含
        self.used_link_types = set()
        self.all_satellites = []  # 存储所有卫星信息
        self.generated_links = {}  # 存储已生成的链路，用于确保双向一致性 {(sat_id1, sat_id2): link_info}
        
    def generate_random_linkList(self, sat_id: int, total_sats: int) -> List[Dict[str, Any]]:
        """
        为指定卫星生成符合约束的随机链路列表
        确保双向链路的一致性
        
        Args:
            sat_id: 当前卫星ID
            total_sats: 总卫星数量
            
        Returns:
            链路列表
        """
        current_sat = self.get_satellite_by_id(sat_id)
        if not current_sat:
            return []
        
        current_sat_type = current_sat["sat_type"]
        links = []
        
        # 首先检查是否已经有其他卫星指向当前卫星的链路
        # 如果有，需要创建反向链路
        existing_reverse_links = []
        # 创建generated_links的副本来避免迭代时修改字典
        generated_links_copy = dict(self.generated_links)
        for (source_id, target_id), link_info in generated_links_copy.items():
            if target_id == sat_id:
                # 找到指向当前卫星的链路，创建反向链路
                reverse_link = {
                    "delay": link_info["delay"],
                    "end_sat_id": source_id,
                    "health": link_info["health"],
                    "jitter": link_info["jitter"],
                    "loss": link_info["loss"],
                    "rate": link_info["rate"],
                    "rate_data_type": link_info["rate_data_type"],
                    "type": link_info["type"]
                }
                existing_reverse_links.append(reverse_link)
                # 记录这个反向链路
                self.generated_links[(sat_id, source_id)] = reverse_link
        
        links.extend(existing_reverse_links)
        
        # 获取适用于当前卫星类型的链路配置
        applicable_links = []
        for link_name, config in self.link_configs.items():
            if current_sat_type in config["source_types"]:
                applicable_links.append((link_name, config))
        
        if not applicable_links:
            return links
        
        # 随机生成新的链路（确保不超过总数限制）
        max_new_links = max(0, 3 - len(links))  # 总共不超过3个链路
        if max_new_links > 0:
            num_new_links = random.randint(1, min(max_new_links, len(applicable_links)))
            selected_link_configs = random.sample(applicable_links, num_new_links)
            
            for link_name, config in selected_link_configs:
                # 找到符合目标类型的卫星
                target_satellites = []
                for target_type in config["target_types"]:
                    target_satellites.extend(self.get_satellites_by_type(target_type))
                
                # 排除自己和已经有链路的目标
                existing_targets = {link["end_sat_id"] for link in links}
                target_satellites = [sat for sat in target_satellites 
                                   if sat["sat_id"] != sat_id and sat["sat_id"] not in existing_targets]
                
                if target_satellites:
                    target_sat = random.choice(target_satellites)
                    
                    # 生成链路信息
                    link = {
                        "delay": round(random.uniform(50.0, 150.0), 1),
                        "end_sat_id": target_sat["sat_id"],
                        "health": 1,
                        "jitter": round(random.uniform(0.0, 2.0), 1),
                        "loss": round(random.uniform(0.0, 1.0), 1),
                        "rate": config["bw"],
                        "rate_data_type": config["unit"],
                        "type": config["type"]
                    }
                    links.append(link)
                    
                    # 记录这个链路，用于后续生成反向链路
                    self.generated_links[(sat_id, target_sat["sat_id"])] = link
                    
                    # 记录使用的链路类型
                    self.used_link_types.add(link_name)
        
        return links
    
    def generate_ip_from_id(self, sat_id: int) -> str:
        """
        根据卫星ID生成IP地址
        
        Args:
            sat_id: 卫星ID
            
        Returns:
            IP地址字符串
        """
        # 按照现有的IP分配规律：(sat_id - 1) * 4 + 2
        fourth_byte = (sat_id - 1) * 4 + 2
        return f"{self.base_ip}.{fourth_byte}"
    
    def generate_yaml_content(self, sat_id: int, total_sats: int = 1000) -> Dict[str, Any]:
        """
        生成单个YAML文件的内容
        
        Args:
            sat_id: 卫星ID
            total_sats: 总卫星数量
            
        Returns:
            YAML内容字典
        """
        sat_info = self.get_satellite_by_id(sat_id)
        if not sat_info:
            return {}
        
        ip_address = sat_info["ip"]
        sat_name = sat_info["sat_name"]
        sat_type = sat_info["sat_type"]
        
        # 生成随机资源使用情况
        cpu_cores = random.choice([2, 4, 8])
        cpu_usage_percent = random.randint(0, 80)
        
        total_memory = random.choice([983, 1024, 2048, 4096])
        used_memory = random.randint(400, int(total_memory * 0.8))
        free_memory = total_memory - used_memory
        
        total_disk = random.choice([16706, 20480, 40960])
        used_disk = random.randint(5000, int(total_disk * 0.7))
        free_disk = total_disk - used_disk
        
        # 生成GPU使用情况
        total_gpu = 4096
        used_gpu = random.randint(100, 1000)
        free_gpu = total_gpu - used_gpu
        
        # 生成当前时间戳
        current_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        yaml_content = {
            "metadata": {
                "name": f"node-status-{ip_address}",
                "sat_id": sat_id,
                "sat_name": sat_name
            },
            "spec": {
                "cpuUsage": {
                    "cores": cpu_cores,
                    "usage": f"{cpu_usage_percent}%"
                },
                "diskUsage": {
                    "free": f"{free_disk}MB",
                    "total": f"{total_disk}MB",
                    "used": f"{used_disk}MB"
                },
                "gpuUsage": {
                    "free": f"{free_gpu}.0MB",
                    "total": f"{total_gpu}MB",
                    "used": f"{used_gpu}.0MB",
                    "util": ""
                },
                "linkList": self.generate_random_linkList(sat_id, total_sats),
                "memoryUsage": {
                    "free": f"{free_memory}MB",
                    "total": f"{total_memory}MB",
                    "used": f"{used_memory}MB"
                },
                "timestamp": current_time
            }
        }
        
        # 为YG卫星添加sensors字段
        if sat_type == "YG":
            yaml_content["spec"]["sensors"] = self.generate_sensors_for_yg()
        
        return yaml_content
    
    def create_output_directory(self):
        """
        创建输出目录
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"创建目录: {self.output_dir}")
        else:
            print(f"目录已存在: {self.output_dir}")
    
    def generate_all_files(self, num_files: int = 1000):
        """
        生成所有YAML文件
        
        Args:
            num_files: 要生成的文件数量
        """
        print(f"开始生成 {num_files} 个YAML文件...")
        
        # 创建输出目录
        self.create_output_directory()
        
        # 初始化卫星信息
        self.initialize_satellites(num_files)
        
        # 重置链路类型使用记录和已生成链路记录
        self.used_link_types = set()
        self.generated_links = {}
        
        success_count = 0
        
        for sat_id in range(1, num_files + 1):
            try:
                # 生成YAML内容
                yaml_content = self.generate_yaml_content(sat_id, num_files)
                
                if not yaml_content:
                    print(f"跳过卫星ID {sat_id}（无法生成内容）")
                    continue
                
                # 生成文件名
                sat_info = self.get_satellite_by_id(sat_id)
                ip_address = sat_info["ip"]
                filename = f"node-status-{ip_address}.yaml"
                filepath = os.path.join(self.output_dir, filename)
                
                # 写入文件
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                success_count += 1
                
                # 每100个文件打印一次进度
                if sat_id % 100 == 0:
                    print(f"已生成 {sat_id}/{num_files} 个文件...")
                    
            except Exception as e:
                print(f"生成文件 {sat_id} 时出错: {e}")
        
        # 确保所有链路类型都被使用
        print("检查并补充未使用的链路类型...")
        self.ensure_all_link_types_used()
        
        # 修复双向链路不一致性
        self.fix_bidirectional_inconsistencies()
        
        print(f"生成完成！成功创建 {success_count}/{num_files} 个YAML文件")
        print(f"文件保存在: {self.output_dir}")
        
        # 验证双向链路一致性
        self.verify_bidirectional_links()
        
        # 打印卫星类型统计
        type_counts = {}
        for sat in self.all_satellites:
            sat_type = sat["sat_type"]
            type_counts[sat_type] = type_counts.get(sat_type, 0) + 1
        
        print("\n卫星类型统计:")
        for sat_type, count in type_counts.items():
            print(f"  {sat_type}: {count} 个")
        
        print(f"\n链路类型使用统计: {len(self.used_link_types)}/{len(self.link_configs)} 种链路类型被使用")
    
    def generate_sample_files(self, num_samples: int = 10):
        """
        生成少量样本文件用于测试
        
        Args:
            num_samples: 样本文件数量
        """
        print(f"生成 {num_samples} 个样本文件用于测试...")
        self.generate_all_files(num_samples)
    
    def initialize_satellites(self, total_sats: int):
        """
        初始化所有卫星信息
        
        Args:
            total_sats: 总卫星数量
        """
        self.all_satellites = []
        sat_id = 1
        
        # 按比例分配卫星数量，XW最多，YG次之，其他较少
        allocated_counts = {}
        remaining_sats = total_sats
        
        # 按顺序分配：XW -> YG -> TSN -> HEO -> NOCC -> GROUND
        priority_order = ["XW", "YG", "TSN", "HEO", "NOCC", "GROUND"]
        
        for sat_type in priority_order:
            if sat_type in self.satellite_configs:
                config = self.satellite_configs[sat_type]
                
                if sat_type == "GROUND":
                    # 最后剩余的都分配给地面站
                    count = max(1, remaining_sats)
                else:
                    # 按比例计算数量
                    count = int(total_sats * config["percentage"])
                    # 确保不超过剩余数量
                    count = min(count, remaining_sats - 1)  # 至少为地面站留1个
                
                allocated_counts[sat_type] = count
                remaining_sats -= count
                
                if remaining_sats <= 0:
                    break
        
        # 生成卫星信息
        for sat_type in priority_order:
            if sat_type not in allocated_counts:
                continue
                
            count = allocated_counts[sat_type]
            
            for i in range(count):
                if sat_id > total_sats:
                    break
                    
                if sat_type in ["XW", "YG"]:
                    sat_name = f"{sat_type}_1_{i+1}"
                elif sat_type == "TSN":
                    sat_name = f"{sat_type}_1_{i+1}"
                elif sat_type == "HEO":
                    sat_name = f"{sat_type}_1_{i+1}"
                elif sat_type == "NOCC":
                    sat_name = f"NOCC_{i+1}"
                else:  # GROUND
                    sat_name = f"GROUND_{i+1}"
                
                self.all_satellites.append({
                    "sat_id": sat_id,
                    "sat_name": sat_name,
                    "sat_type": sat_type,
                    "ip": self.generate_ip_from_id(sat_id)
                })
                sat_id += 1
        
        # 打印分配统计
        print(f"初始化了 {len(self.all_satellites)} 个卫星")
        print("分配详情:")
        for sat_type in priority_order:
            if sat_type in allocated_counts:
                count = allocated_counts[sat_type]
                percentage = (count / total_sats) * 100
                print(f"  {sat_type}: {count} 个 ({percentage:.1f}%)")
        
        
    def get_satellite_by_id(self, sat_id: int) -> Dict[str, Any]:
        """
        根据卫星ID获取卫星信息
        """
        for sat in self.all_satellites:
            if sat["sat_id"] == sat_id:
                return sat
        return None
    
    def get_satellites_by_type(self, sat_type: str) -> List[Dict[str, Any]]:
        """
        根据卫星类型获取所有该类型的卫星
        """
        return [sat for sat in self.all_satellites if sat["sat_type"] == sat_type]
    
    def generate_sensors_for_yg(self) -> List[Dict[str, Any]]:
        """
        为YG卫星生成传感器信息
        
        Returns:
            传感器列表
        """
        sensors = []
        # YG卫星随机生成1-3个传感器
        num_sensors = random.randint(1, 3)
        sensor_types = random.sample(list(self.sensor_types.keys()), num_sensors)
        
        for sensor_type in sensor_types:
            sensor = {
                "sensor_type": sensor_type,
                "health": 1,  # 默认健康
                "occupied": random.randint(100, 999)  # 随机任务编号
            }
            sensors.append(sensor)
        
        return sensors

    def ensure_all_link_types_used(self):
        """
        确保所有链路类型都被使用，如果有遗漏的链路类型，强制生成
        """
        unused_link_types = set(self.link_configs.keys()) - self.used_link_types
        
        if unused_link_types:
            print(f"发现未使用的链路类型: {unused_link_types}")
            
            for link_name in unused_link_types:
                config = self.link_configs[link_name]
                
                # 找到符合源类型的卫星
                source_satellites = []
                for source_type in config["source_types"]:
                    source_satellites.extend(self.get_satellites_by_type(source_type))
                
                # 找到符合目标类型的卫星
                target_satellites = []
                for target_type in config["target_types"]:
                    target_satellites.extend(self.get_satellites_by_type(target_type))
                
                if source_satellites and target_satellites:
                    source_sat = random.choice(source_satellites)
                    # 排除源卫星本身
                    valid_targets = [sat for sat in target_satellites if sat["sat_id"] != source_sat["sat_id"]]
                    
                    if valid_targets:
                        target_sat = random.choice(valid_targets)
                        
                        # 为源卫星添加这个链路
                        source_filename = f"node-status-{source_sat['ip']}.yaml"
                        source_filepath = os.path.join(self.output_dir, source_filename)
                        
                        if os.path.exists(source_filepath):
                            # 读取现有文件
                            with open(source_filepath, 'r', encoding='utf-8') as f:
                                yaml_content = yaml.safe_load(f)
                            
                            # 添加新链路
                            new_link = {
                                "delay": round(random.uniform(50.0, 150.0), 1),
                                "end_sat_id": target_sat["sat_id"],
                                "health": 1,
                                "jitter": round(random.uniform(0.0, 2.0), 1),
                                "loss": round(random.uniform(0.0, 1.0), 1),
                                "rate": config["bw"],
                                "rate_data_type": config["unit"],
                                "type": config["type"]
                            }
                            yaml_content["spec"]["linkList"].append(new_link)
                            
                            # 写回文件
                            with open(source_filepath, 'w', encoding='utf-8') as f:
                                yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                            
                            # 同时为目标卫星添加反向链路
                            target_filename = f"node-status-{target_sat['ip']}.yaml"
                            target_filepath = os.path.join(self.output_dir, target_filename)
                            
                            if os.path.exists(target_filepath):
                                # 读取目标文件
                                with open(target_filepath, 'r', encoding='utf-8') as f:
                                    target_yaml_content = yaml.safe_load(f)
                                
                                # 添加反向链路
                                reverse_link = {
                                    "delay": new_link["delay"],
                                    "end_sat_id": source_sat["sat_id"],
                                    "health": new_link["health"],
                                    "jitter": new_link["jitter"],
                                    "loss": new_link["loss"],
                                    "rate": new_link["rate"],
                                    "rate_data_type": new_link["rate_data_type"],
                                    "type": new_link["type"]
                                }
                                target_yaml_content["spec"]["linkList"].append(reverse_link)
                                
                                # 写回目标文件
                                with open(target_filepath, 'w', encoding='utf-8') as f:
                                    yaml.dump(target_yaml_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                            
                            print(f"为卫星 {source_sat['sat_name']} 和 {target_sat['sat_name']} 添加了双向链路: {link_name}")
                            self.used_link_types.add(link_name)
        
        print(f"最终使用的链路类型: {len(self.used_link_types)}/{len(self.link_configs)}")
        print(f"使用的链路类型: {sorted(self.used_link_types)}")
        if unused_link_types - self.used_link_types:
            print(f"仍未使用的链路类型: {unused_link_types - self.used_link_types}")

    def verify_bidirectional_links(self):
        """
        验证生成的链路是否满足双向一致性
        """
        print("验证双向链路一致性...")
        
        # 统计所有已生成的链路
        all_links = {}  # {sat_id: [links]}
        
        for sat_id in range(1, len(self.all_satellites) + 1):
            sat_info = self.get_satellite_by_id(sat_id)
            if not sat_info:
                continue
                
            ip_address = sat_info["ip"]
            filename = f"node-status-{ip_address}.yaml"
            filepath = os.path.join(self.output_dir, filename)
            
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        yaml_content = yaml.safe_load(f)
                    
                    links = yaml_content.get("spec", {}).get("linkList", [])
                    all_links[sat_id] = links
                except Exception as e:
                    print(f"读取文件 {filename} 时出错: {e}")
        
        # 检查双向一致性
        inconsistent_pairs = []
        
        for source_id, links in all_links.items():
            for link in links:
                target_id = link["end_sat_id"]
                
                # 检查目标卫星是否有反向链路
                target_links = all_links.get(target_id, [])
                reverse_link_found = False
                
                for target_link in target_links:
                    # 确保比较时数据类型一致
                    if int(target_link["end_sat_id"]) == int(source_id):
                        # 检查链路参数是否一致
                        if (target_link["rate"] == link["rate"] and
                            target_link["rate_data_type"] == link["rate_data_type"] and
                            target_link["type"] == link["type"] and
                            target_link["delay"] == link["delay"] and
                            target_link["jitter"] == link["jitter"] and
                            target_link["loss"] == link["loss"]):
                            reverse_link_found = True
                            break
                
                if not reverse_link_found:
                    inconsistent_pairs.append((source_id, target_id))
        
        if inconsistent_pairs:
            print(f"发现 {len(inconsistent_pairs)} 对不一致的链路:")
            for source_id, target_id in inconsistent_pairs[:10]:  # 只显示前10个
                print(f"  卫星 {source_id} -> 卫星 {target_id} 缺少反向链路")
        else:
            print("✓ 所有链路都满足双向一致性")
        
        return len(inconsistent_pairs) == 0

    def fix_bidirectional_inconsistencies(self):
        """
        修复双向链路不一致的问题
        """
        print("修复双向链路不一致性...")
        
        # 第一次扫描：找到所有不一致的链路
        inconsistent_links = []
        
        for sat_id in range(1, len(self.all_satellites) + 1):
            sat_info = self.get_satellite_by_id(sat_id)
            if not sat_info:
                continue
                
            ip_address = sat_info["ip"]
            filename = f"node-status-{ip_address}.yaml"
            filepath = os.path.join(self.output_dir, filename)
            
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        yaml_content = yaml.safe_load(f)
                    
                    links = yaml_content.get("spec", {}).get("linkList", [])
                    
                    for link in links:
                        target_id = int(link["end_sat_id"])
                        
                        # 检查目标卫星是否有反向链路
                        target_sat = self.get_satellite_by_id(target_id)
                        if target_sat:
                            target_filename = f"node-status-{target_sat['ip']}.yaml"
                            target_filepath = os.path.join(self.output_dir, target_filename)
                            
                            if os.path.exists(target_filepath):
                                with open(target_filepath, 'r', encoding='utf-8') as f:
                                    target_yaml_content = yaml.safe_load(f)
                                
                                target_links = target_yaml_content.get("spec", {}).get("linkList", [])
                                reverse_link_found = False
                                
                                for target_link in target_links:
                                    if int(target_link["end_sat_id"]) == int(sat_id):
                                        reverse_link_found = True
                                        break
                                
                                if not reverse_link_found:
                                    # 记录需要添加的反向链路
                                    inconsistent_links.append((sat_id, target_id, link, target_filepath))
                        
                except Exception as e:
                    print(f"读取文件 {filename} 时出错: {e}")
        
        # 第二次扫描：添加所有缺失的反向链路
        fixed_count = 0
        
        for source_id, target_id, original_link, target_filepath in inconsistent_links:
            try:
                # 重新读取目标文件（可能已被其他修复更新）
                with open(target_filepath, 'r', encoding='utf-8') as f:
                    target_yaml_content = yaml.safe_load(f)
                
                # 再次检查是否已有反向链路（避免重复添加）
                target_links = target_yaml_content.get("spec", {}).get("linkList", [])
                reverse_link_exists = False
                
                for target_link in target_links:
                    if int(target_link["end_sat_id"]) == int(source_id):
                        reverse_link_exists = True
                        break
                
                if not reverse_link_exists:
                    # 添加反向链路
                    reverse_link = {
                        "delay": original_link["delay"],
                        "end_sat_id": source_id,
                        "health": original_link["health"],
                        "jitter": original_link["jitter"],
                        "loss": original_link["loss"],
                        "rate": original_link["rate"],
                        "rate_data_type": original_link["rate_data_type"],
                        "type": original_link["type"]
                    }
                    target_yaml_content["spec"]["linkList"].append(reverse_link)
                    
                    # 写回目标文件
                    with open(target_filepath, 'w', encoding='utf-8') as f:
                        yaml.dump(target_yaml_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    fixed_count += 1
                    # print(f"修复链路: 卫星{target_id} -> 卫星{source_id}")
                    
            except Exception as e:
                print(f"修复链路时出错: {e}")
        
        # print(f"修复了 {fixed_count} 个不一致的链路")

def main():
    """主函数"""
    generator = YAMLGenerator()
    
    print("YAML文件批量生成器")
    print("=" * 50)
    print("1. 生成1000个文件")
    print("2. 生成10个样本文件(测试用)")
    print("3. 自定义数量")
    
    try:
        choice = input("请选择操作 (1/2/3): ").strip()
        
        if choice == "1":
            generator.generate_all_files(1000)
        elif choice == "2":
            generator.generate_sample_files(10)
        elif choice == "3":
            num = int(input("请输入要生成的文件数量: "))
            if num > 0:
                generator.generate_all_files(num)
            else:
                print("错误: 文件数量必须大于0")
        else:
            print("无效选择，默认生成10个样本文件")
            generator.generate_sample_files(10)
            
    except KeyboardInterrupt:
        print("\n用户取消操作")
    except ValueError as e:
        print(f"输入错误: {e}")
    except Exception as e:
        print(f"运行时错误: {e}")

if __name__ == "__main__":
    main()
