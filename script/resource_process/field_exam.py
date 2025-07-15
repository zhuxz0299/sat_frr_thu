#!/usr/bin/env python3
"""
校验YAML文件和JSON文件中字段值是否相等的工具
用法: python field_exam.py <yaml_path> <json_path> [sat_type]
示例: python field_exam.py /path/to/yaml_file.yaml /path/to/json_file.json tsn
      python field_exam.py /path/to/yaml_folder /path/to/json_file.json yg

yaml_path 可以是单个YAML文件路径或包含YAML文件的文件夹路径
json_path 是对应的JSON文件路径
sat_type 是卫星类型 (可选)，用于验证sat_id和sat_name的生成逻辑
"""

import os
import sys
import yaml
import json
import re
import datetime
from glob import glob
from typing import Dict, List, Tuple, Any

def extract_ip_from_yaml(yaml_data):
    """从YAML文件中提取IP地址"""
    if 'metadata' in yaml_data and 'name' in yaml_data['metadata']:
        return yaml_data['metadata']['name']
    return None

def extract_sat_info_from_yaml(yaml_data, sat_type):
    """从YAML文件中提取卫星ID和名称（复制自resource_info_gathering.py）"""
    if 'metadata' in yaml_data:
        metadata = yaml_data['metadata']
        
        if 'sat_id' in metadata:
            sat_id = metadata['sat_id']
            if 'sat_name' in metadata:
                sat_name = metadata['sat_name']
                return int(sat_id), sat_name
            else:
                if sat_type == 'tsn':
                    sat_name = f"TSN_1_{sat_id}"
                elif sat_type == 'yg':
                    sat_name = f"YG_1_{sat_id-8}"
                elif sat_type == 'xw':
                    sat_name = f"XW_1_{sat_id-20}"
                else:
                    sat_name = f"{sat_type.upper()}_1_{sat_id}"
                return int(sat_id), sat_name
    
    # 从IP地址推断
    sat_ip = extract_ip_from_yaml(yaml_data)
    if sat_ip:
        result = ip_to_sat_id_and_name(sat_ip, sat_type)
        if result:
            return result
    
    return None, None

def ip_to_sat_id_and_name(ip_str, sat_type):
    """从IP地址反推卫星ID（复制自resource_info_gathering.py）"""
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
        if sat_type == 'tsn':
            sat_name = f"TSN_1_{idx}"
        elif sat_type == 'yg':
            sat_name = f"YG_1_{idx-8}"
        elif sat_type == 'xw':
            sat_name = f"XW_1_{idx-20}"
        else:
            sat_name = f"UNKNOWN_1_{idx}"
        return idx, sat_name
    except (ValueError, IndexError):
        return None

def convert_size_to_type(size_str):
    """将带单位的大小字符串转换为数值和单位类型（复制自resource_info_gathering.py）"""
    if not size_str or size_str == "-MB" or size_str == "MB":
        return 0.0, 1
    
    size_str = size_str.strip('"')
    
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
        return 0.0, 1
    
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
        return value, 1

def convert_timestamp(timestamp_str):
    """将ISO格式的时间戳转换为标准格式（复制自resource_info_gathering.py）"""
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def load_yaml_file(yaml_path: str) -> Dict:
    """加载YAML文件"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"错误: 无法加载YAML文件 {yaml_path}: {e}")
        return {}

def load_json_file(json_path: str) -> Dict:
    """加载JSON文件"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"错误: 无法加载JSON文件 {json_path}: {e}")
        return {}

def find_task_by_sat_id(json_data: Dict, sat_id: int) -> Dict:
    """在JSON数据中根据sat_id查找对应的任务"""
    task_info = json_data.get('task_info', [])
    for task in task_info:
        if task.get('sat_id') == sat_id:
            return task
    return {}

def compare_cpu_usage(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较CPU使用情况"""
    errors = []
    
    if 'cpuUsage' in yaml_spec:
        yaml_cpu = yaml_spec['cpuUsage']
        json_cpu = json_task.get('cpu_usage', {})
        
        # 检查核心数
        yaml_cores = yaml_cpu.get('cores', 0)
        json_cores = json_cpu.get('cpu_total_cores', 0)
        if int(yaml_cores) != int(json_cores):
            errors.append(f"CPU核心数不匹配: YAML={yaml_cores}, JSON={json_cores}")
        
        # 检查使用率计算
        yaml_usage_str = yaml_cpu.get('usage', '0%')
        yaml_usage = float(yaml_usage_str.strip('%')) / 100.0
        expected_used = round(float(yaml_cores) * yaml_usage, 1)
        json_used = json_cpu.get('used', 0)
        if abs(expected_used - json_used) > 0.1:
            errors.append(f"CPU使用量计算不匹配: 期望={expected_used}, JSON={json_used}")
    
    return errors

def compare_memory_usage(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较内存使用情况"""
    errors = []
    
    if 'memoryUsage' in yaml_spec:
        yaml_mem = yaml_spec['memoryUsage']
        json_mem = json_task.get('mem_usage', {})
        
        # 检查总内存
        yaml_total, yaml_total_type = convert_size_to_type(yaml_mem.get('total', '0MB'))
        json_total = json_mem.get('total', 0)
        json_total_type = json_mem.get('total_data_type', 1)
        
        if abs(yaml_total - json_total) > 0.1 or yaml_total_type != json_total_type:
            errors.append(f"内存总量不匹配: YAML={yaml_total}(类型{yaml_total_type}), JSON={json_total}(类型{json_total_type})")
        
        # 检查使用量百分比
        yaml_used, _ = convert_size_to_type(yaml_mem.get('used', '0MB'))
        expected_used_percent = round(yaml_used / yaml_total * 100, 1) if yaml_total > 0 else 0.0
        json_used_percent = json_mem.get('used', 0)
        
        if abs(expected_used_percent - json_used_percent) > 0.1:
            errors.append(f"内存使用百分比不匹配: 期望={expected_used_percent}%, JSON={json_used_percent}%")
    
    return errors

def compare_disk_usage(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较磁盘使用情况"""
    errors = []
    
    if 'diskUsage' in yaml_spec:
        yaml_disk = yaml_spec['diskUsage']
        json_disk = json_task.get('disk_usage', {})
        
        # 检查总磁盘空间
        yaml_total, yaml_total_type = convert_size_to_type(yaml_disk.get('total', '0MB'))
        json_total = json_disk.get('total', 0)
        json_total_type = json_disk.get('total_data_type', 1)
        
        if abs(yaml_total - json_total) > 0.1 or yaml_total_type != json_total_type:
            errors.append(f"磁盘总量不匹配: YAML={yaml_total}(类型{yaml_total_type}), JSON={json_total}(类型{json_total_type})")
        
        # 检查使用量百分比
        yaml_used, _ = convert_size_to_type(yaml_disk.get('used', '0MB'))
        expected_used_percent = round(yaml_used / yaml_total * 100, 1) if yaml_total > 0 else 0.0
        json_used_percent = json_disk.get('used', 0)
        
        if abs(expected_used_percent - json_used_percent) > 0.1:
            errors.append(f"磁盘使用百分比不匹配: 期望={expected_used_percent}%, JSON={json_used_percent}%")
    
    return errors

def compare_gpu_usage(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较GPU使用情况"""
    errors = []
    
    if 'gpuUsage' in yaml_spec:
        yaml_gpu = yaml_spec['gpuUsage']
        json_gpu = json_task.get('gpu_usage', {})
        
        # 检查总GPU内存
        yaml_total, yaml_total_type = convert_size_to_type(yaml_gpu.get('total', '0MB'))
        json_total = json_gpu.get('total', 0)
        json_total_type = json_gpu.get('total_data_type', 1)
        
        if abs(yaml_total - json_total) > 0.1 or yaml_total_type != json_total_type:
            errors.append(f"GPU总内存不匹配: YAML={yaml_total}(类型{yaml_total_type}), JSON={json_total}(类型{json_total_type})")
        
        # 检查使用量
        yaml_used, yaml_used_type = convert_size_to_type(yaml_gpu.get('used', '0MB'))
        json_used = json_gpu.get('used', 0)
        json_used_type = json_gpu.get('used_data_type', 1)
        
        if abs(yaml_used - json_used) > 0.1 or yaml_used_type != json_used_type:
            errors.append(f"GPU使用量不匹配: YAML={yaml_used}(类型{yaml_used_type}), JSON={json_used}(类型{json_used_type})")
        
        # 检查GPU占用状态
        expected_occupied = 1 if yaml_used > 104 else 0
        json_occupied = json_gpu.get('gpu_occupied', 0)
        if expected_occupied != json_occupied:
            errors.append(f"GPU占用状态不匹配: 期望={expected_occupied}, JSON={json_occupied}")
    
    return errors

def compare_timestamp(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较时间戳"""
    errors = []
    
    yaml_timestamp = yaml_spec.get('timestamp', '')
    json_timestamp = json_task.get('timestamp', '')
    
    if yaml_timestamp:
        expected_timestamp = convert_timestamp(yaml_timestamp)
        if expected_timestamp != json_timestamp:
            errors.append(f"时间戳不匹配: 期望={expected_timestamp}, JSON={json_timestamp}")
    
    return errors

def compare_link_list(yaml_spec: Dict, json_task: Dict) -> List[str]:
    """比较链路列表"""
    errors = []
    
    yaml_links = yaml_spec.get('linkList', [])
    json_links = json_task.get('linkList', [])
    
    if yaml_links:
        if len(yaml_links) != len(json_links):
            errors.append(f"链路数量不匹配: YAML={len(yaml_links)}, JSON={len(json_links)}")
        
        for i, (yaml_link, json_link) in enumerate(zip(yaml_links, json_links)):
            link_errors = []
            
            # 检查各个字段
            fields_to_check = ['health', 'type', 'rate', 'rate_data_type', 'delay', 'jitter', 'loss', 'end_sat_id']
            for field in fields_to_check:
                yaml_val = yaml_link.get(field)
                json_val = json_link.get(field)
                
                # 对于数值字段进行类型转换比较
                if field in ['health', 'rate_data_type']:
                    yaml_val = int(yaml_val) if yaml_val is not None else 0
                    json_val = int(json_val) if json_val is not None else 0
                elif field in ['rate', 'delay', 'jitter', 'loss']:
                    yaml_val = float(yaml_val) if yaml_val is not None else 0.0
                    json_val = float(json_val) if json_val is not None else 0.0
                elif field == 'end_sat_id':
                    yaml_val = str(yaml_val) if yaml_val is not None else ""
                    json_val = str(json_val) if json_val is not None else ""
                
                if yaml_val != json_val:
                    link_errors.append(f"链路{i+1}的{field}不匹配: YAML={yaml_val}, JSON={json_val}")
            
            errors.extend(link_errors)
    
    return errors

def compare_single_yaml_json(yaml_path: str, json_path: str, sat_type: str = None) -> Tuple[bool, List[str]]:
    """比较单个YAML文件和JSON文件"""
    # 加载文件
    yaml_data = load_yaml_file(yaml_path)
    json_data = load_json_file(json_path)
    
    if not yaml_data or not json_data:
        return False, ["文件加载失败"]
    
    if 'spec' not in yaml_data:
        return False, ["YAML文件格式不正确，缺少spec字段"]
    
    spec = yaml_data['spec']
    errors = []
    
    # 获取卫星ID和名称
    sat_id, sat_name = extract_sat_info_from_yaml(yaml_data, sat_type)
    if sat_id is None:
        errors.append("无法从YAML文件中获取或推断sat_id")
        return False, errors
    
    # 在JSON中查找对应的任务
    json_task = find_task_by_sat_id(json_data, sat_id)
    if not json_task:
        errors.append(f"JSON文件中未找到sat_id={sat_id}的任务")
        return False, errors
    
    print(f"检验卫星ID={sat_id}, 名称={sat_name}")
    
    # 检查sat_name
    json_sat_name = json_task.get('sat_name', '')
    if sat_name != json_sat_name:
        errors.append(f"卫星名称不匹配: 期望={sat_name}, JSON={json_sat_name}")
    
    # 比较各个字段
    errors.extend(compare_cpu_usage(spec, json_task))
    errors.extend(compare_memory_usage(spec, json_task))
    errors.extend(compare_disk_usage(spec, json_task))
    errors.extend(compare_gpu_usage(spec, json_task))
    errors.extend(compare_timestamp(spec, json_task))
    errors.extend(compare_link_list(spec, json_task))
    
    return len(errors) == 0, errors

def compare_folder_json(yaml_folder: str, json_path: str, sat_type: str = None) -> Tuple[bool, List[str]]:
    """比较文件夹中的YAML文件和JSON文件"""
    if not os.path.isdir(yaml_folder):
        return False, [f"YAML路径不是有效的文件夹: {yaml_folder}"]
    
    yaml_files = glob(os.path.join(yaml_folder, "*.yaml"))
    if not yaml_files:
        return False, [f"文件夹中没有找到YAML文件: {yaml_folder}"]
    
    json_data = load_json_file(json_path)
    if not json_data:
        return False, ["JSON文件加载失败"]
    
    all_errors = []
    success_count = 0
    total_count = len(yaml_files)
    
    print(f"开始检验文件夹 {yaml_folder} 中的 {total_count} 个YAML文件")
    
    for yaml_file in yaml_files:
        print(f"\n检验文件: {os.path.basename(yaml_file)}")
        
        yaml_data = load_yaml_file(yaml_file)
        if not yaml_data or 'spec' not in yaml_data:
            all_errors.append(f"文件 {yaml_file} 格式不正确")
            continue
        
        spec = yaml_data['spec']
        
        # 获取卫星ID和名称
        sat_id, sat_name = extract_sat_info_from_yaml(yaml_data, sat_type)
        if sat_id is None:
            all_errors.append(f"文件 {yaml_file} 无法获取sat_id")
            continue
        
        # 在JSON中查找对应的任务
        json_task = find_task_by_sat_id(json_data, sat_id)
        if not json_task:
            all_errors.append(f"JSON文件中未找到sat_id={sat_id}的任务 (对应文件: {yaml_file})")
            continue
        
        print(f"  -> 卫星ID={sat_id}, 名称={sat_name}")
        
        # 检查字段
        file_errors = []
        
        # 检查sat_name
        json_sat_name = json_task.get('sat_name', '')
        if sat_name != json_sat_name:
            file_errors.append(f"卫星名称不匹配: 期望={sat_name}, JSON={json_sat_name}")
        
        # 比较各个字段
        file_errors.extend(compare_cpu_usage(spec, json_task))
        file_errors.extend(compare_memory_usage(spec, json_task))
        file_errors.extend(compare_disk_usage(spec, json_task))
        file_errors.extend(compare_gpu_usage(spec, json_task))
        file_errors.extend(compare_timestamp(spec, json_task))
        file_errors.extend(compare_link_list(spec, json_task))
        
        if file_errors:
            all_errors.append(f"文件 {yaml_file} 存在错误:")
            all_errors.extend([f"  - {error}" for error in file_errors])
        else:
            success_count += 1
            print(f"  -> ✓ 检验通过")
    
    print(f"\n检验完成: {success_count}/{total_count} 个文件通过检验")
    
    return len(all_errors) == 0, all_errors

def main():
    """主函数"""
    if len(sys.argv) < 3:
        print("用法: python field_exam.py <yaml_path> <json_path> [sat_type]")
        print("示例: python field_exam.py /path/to/yaml_file.yaml /path/to/json_file.json tsn")
        print("      python field_exam.py /path/to/yaml_folder /path/to/json_file.json yg")
        print()
        print("参数说明:")
        print("  yaml_path: 单个YAML文件路径或包含YAML文件的文件夹路径")
        print("  json_path: 对应的JSON文件路径")
        print("  sat_type:  卫星类型 (可选)，用于验证sat_id和sat_name的生成逻辑")
        sys.exit(1)
    
    yaml_path = sys.argv[1]
    json_path = sys.argv[2]
    sat_type = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(yaml_path):
        print(f"错误: YAML路径不存在: {yaml_path}")
        sys.exit(1)
    
    if not os.path.exists(json_path):
        print(f"错误: JSON文件不存在: {json_path}")
        sys.exit(1)
    
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("字段值校验工具")
    print("="*80)
    print(f"YAML路径: {yaml_path}")
    print(f"JSON文件: {json_path}")
    if sat_type:
        print(f"卫星类型: {sat_type}")
    print("-"*80)
    
    # 判断是单个文件还是文件夹
    if os.path.isfile(yaml_path):
        if not yaml_path.endswith('.yaml'):
            print("错误: 输入的文件不是YAML文件")
            sys.exit(1)
        
        print("模式: 单文件检验")
        success, errors = compare_single_yaml_json(yaml_path, json_path, sat_type)
    else:
        print("模式: 文件夹检验")
        success, errors = compare_folder_json(yaml_path, json_path, sat_type)
    
    print("\n" + "="*80)
    print("检验结果")
    print("="*80)
    
    if success:
        print("✓ 所有字段值校验通过！")
        sys.exit(0)
    else:
        print("✗ 发现字段值不匹配:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)

if __name__ == "__main__":
    main()
