#!/usr/bin/env python3
"""
将VM文件夹下的YAML文件转换成JSON文件
用法: python resource_info_gathering.py <vm_folder_path> <output_json_path>
示例: python resource_info_gathering.py /home/sjtu/sat_frr_thu/resource_info/vm46 /home/sjtu/sat_frr_thu/resource_info/vm46_status.json
"""

import os
import sys
import yaml
import json
import random
import string
import datetime
from glob import glob

def extract_name_from_yaml(yaml_data):
    """从YAML文件中提取名称"""
    if 'metadata' in yaml_data and 'name' in yaml_data['metadata']:
        return yaml_data['metadata']['name']
    return None

def convert_size_to_type(size_str):
    """将带单位的大小字符串转换为数值和单位类型
    
    返回: (数值, 单位类型)
    单位类型: 0=KB, 1=MB, 2=GB, 3=TB
    """
    if not size_str or size_str == "-MB" or size_str == "MB":
        return 0.0, 1  # 默认为0MB
    
    # 处理可能的格式错误
    size_str = size_str.strip('"')
    
    # 查找数字部分和单位部分
    num = ""
    unit = ""
    for char in size_str:
        if char.isdigit() or char == '.':
            num += char
        else:
            unit += char

    try:
        value = float(num)
    except ValueError:
        return 0.0, 1  # 默认为0MB
    
    unit = unit.strip().upper()
    if "KB" in unit:
        return value, 0
    elif "MB" in unit:
        return value, 1
    elif "GB" in unit:
        return value, 2
    elif "TB" in unit:
        return value, 3
    else:
        return value, 1  # 默认为MB

def convert_timestamp(timestamp_str):
    """将ISO格式的时间戳转换为 'YYYY-MM-DD HH:MM:SS' 格式"""
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        # 如果转换失败，返回当前时间
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def generate_link_list(sat_id, sat_count):
    """生成链接列表"""
    link_count = random.randint(1, 3)  # 生成1-3个链接
    links = []
    print(f"DEBUG: link_count: {link_count}; sat_count: {sat_count}")
    
    for _ in range(link_count):
        # 生成一个不同于当前卫星的随机目标卫星ID
        end_sat_id = random.randint(0, sat_count)
        while end_sat_id == sat_id:
            end_sat_id = random.randint(0, sat_count)
            
        link = {
            "health": 1,
            "type": "microwave",
            "rate": 50,
            "rate_data_type": 1,
            "delay": round(random.uniform(60, 80), 1),
            "jitter": 0,
            "loss": 0,
            "end_sat_id": str(end_sat_id)
        }
        links.append(link)

    
    return links

def convert_yaml_to_json(vm_folder_path, output_json_path):
    """将VM文件夹下的YAML文件转换为JSON文件"""
    # 获取所有YAML文件
    yaml_files = glob(os.path.join(vm_folder_path, "*.yaml"))
    
    if not yaml_files:
        print(f"在 {vm_folder_path} 中没有找到YAML文件")
        return False
    
    # 准备JSON结构
    vm_name = os.path.basename(vm_folder_path)
    result = {
        "file_id": random.randint(1, 100),
        "constellation_name": vm_name.upper(),
        "task_info": []
    }
    
    # 处理每个YAML文件
    sat_count = len(yaml_files)  # 总卫星数量
    sat_id_counter = 1  # 从1开始计数
    
    for yaml_file in yaml_files:
        try:
            with open(yaml_file, 'r') as f:
                yaml_data = yaml.safe_load(f)
            
            if not yaml_data or 'spec' not in yaml_data:
                print(f"跳过文件 {yaml_file}，格式不正确")
                continue
            
            spec = yaml_data['spec']
            
            # 获取卫星名称
            sat_name = extract_name_from_yaml(yaml_data)
            if not sat_name:
                sat_name = os.path.basename(yaml_file).replace('.yaml', '')
            
            # 创建任务信息
            task = {
                "sat_id": str(sat_id_counter),  # 从1开始递增
                "sat_name": sat_name,
                "timestamp": convert_timestamp(spec.get('timestamp', '')),
            }

            print("DEBUG：创建task完成")
            
            sat_id_counter += 1
            
            # CPU使用情况
            if 'cpuUsage' in spec:
                cpu_cores = spec['cpuUsage'].get('cores', 0)
                cpu_usage_str = spec['cpuUsage'].get('usage', '0%')
                cpu_usage = float(cpu_usage_str.strip('%')) / 100.0
                
                task["cpu_usage"] = {
                    "health": 1,
                    "cpu_total_cores": int(cpu_cores),
                    "used": round(float(cpu_cores) * cpu_usage, 1)
                }
            
            # 内存使用情况
            if 'memoryUsage' in spec:
                mem_total, total_type = convert_size_to_type(spec['memoryUsage'].get('total', '0MB'))
                mem_used, _ = convert_size_to_type(spec['memoryUsage'].get('used', '0MB'))
                
                task["mem_usage"] = {
                    "health": 1,
                    "total": mem_total,
                    "total_data_type": total_type,
                    "used": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0.0
                }
            
            # 磁盘使用情况
            if 'diskUsage' in spec:
                disk_total, total_type = convert_size_to_type(spec['diskUsage'].get('total', '0MB'))
                disk_used, _ = convert_size_to_type(spec['diskUsage'].get('used', '0MB'))
                
                task["disk_usage"] = {
                    "health": 1,
                    "total": disk_total,
                    "total_data_type": total_type,
                    "used": round(disk_used / disk_total * 100, 1) if disk_total > 0 else 0.0
                }
            
            # GPU使用情况
            if 'gpuUsage' in spec:
                gpu_total, total_type = convert_size_to_type(spec['gpuUsage'].get('total', '0MB'))
                gpu_used, used_type = convert_size_to_type(spec['gpuUsage'].get('used', '0MB'))
                
                task["gpu_usage"] = {
                    "health": 1,
                    "total": gpu_total,
                    "total_data_type": total_type,
                    "used": gpu_used,
                    "used_data_type": used_type
                }

            print("DEBUG: 信息读取完成")
            
            # 添加链接列表
            task["linkList"] = generate_link_list(sat_id_counter-1, sat_count)

            print("DEBUG: linkList 生成完成")
            
            # 添加空的传感器列表，保持格式一致
            task["sensors"] = []
            
            # 添加到任务列表
            result["task_info"].append(task)
            
        except Exception as e:
            print(f"处理文件 {yaml_file} 时出错: {e}")
    
    # 写入JSON文件
    with open(output_json_path, 'w') as f:
        json.dump(result, f, indent=4)
    
    print(f"成功将 {len(result['task_info'])} 个YAML文件转换为JSON并保存到 {output_json_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python resource_info_gathering.py <vm_folder_path> <output_json_path>")
        print("示例: python resource_info_gathering.py /home/sjtu/sat_frr_thu/resource_info/vm46 /home/sjtu/sat_frr_thu/resource_info/vm46_status.json")
        sys.exit(1)
    
    vm_folder_path = sys.argv[1]
    output_json_path = sys.argv[2]
    
    if not os.path.isdir(vm_folder_path):
        print(f"错误: 文件夹 {vm_folder_path} 不存在")
        sys.exit(1)
    
    success = convert_yaml_to_json(vm_folder_path, output_json_path)
    sys.exit(0 if success else 1)
