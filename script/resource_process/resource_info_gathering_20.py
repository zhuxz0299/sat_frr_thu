#!/usr/bin/env python3
"""
将VM文件夹下的YAML文件转换成JSON文件
用法: python resource_info_gathering.py <vm_folder_path> <sat_type>
示例: python resource_info_gathering.py /home/sjtu/sat_frr_thu/resource_info/vm46 tsn

sat_type 必须是 "tsn", "xw", 或 "yg" 之一
输出文件将保存为 <vm_folder_path上一级目录>/<sat_type>_constellation.json
"""

import os
import sys
import yaml
import json
import random
import string
import datetime
import re
from glob import glob

# 完整任务文件路径
COMPLETE_TASK_JSON_PATH = "/root/ftp/double_ts/complete_task.json"
# COMPLETE_TASK_JSON_PATH = "temp/complete_task.json"

def ip_to_sat_id_and_name(ip_str, sat_type):
    """从IP地址反推卫星ID
    
    Args:
        ip_str: IP地址字符串，格式如 "10.0.64.46"
        sat_type: 卫星类型，"tsn", "xw", "yg" 之一
    
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
        if sat_type == 'tsn':
            sat_name = f"TSN_1_{idx}"
        elif sat_type == 'yg':
            sat_name = f"YG_1_{idx-8}"
        elif sat_type == 'xw':
            sat_name = f"XW_1_{idx-20}"
        else:
            # print(f"警告: 未知的卫星类型 '{sat_type}'，使用默认命名")
            sat_name = f"UNKNOWN_1_{idx}"
        return idx, sat_name

    except (ValueError, IndexError):
        return None
    

def extract_ip_from_yaml(yaml_data):
    """
    从YAML文件中提取名称
    文件中的 "name" 字段包含了卫星的 ip 地址
    """
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
    
    for _ in range(link_count):
        # 生成一个不同于当前卫星的随机目标卫星ID
        end_sat_id = random.randint(1, sat_count+1)
        while end_sat_id == sat_id:
            end_sat_id = random.randint(1, sat_count+1)
            
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

def apply_usage_fluctuation(base_value, min_limit=0.0, max_limit=100.0):
    """对使用率进行倍数浮动
    
    Args:
        base_value: 基础值
        min_limit: 最小限制
        max_limit: 最大限制
    
    Returns:
        浮动后的值
    """
    fluctuation = random.uniform(0.5, 2.0)
    return max(min_limit, min(max_limit, base_value * fluctuation))

def create_default_task(sat_id, sat_type, sat_count):
    """创建默认的任务信息
    
    Args:
        sat_id: 卫星ID
        sat_type: 卫星类型 ("tsn", "xw", "yg")
        sat_count: 总卫星数
        
    Returns:
        dict: 任务信息字典
    """
    # 当前时间戳
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 创建基本任务结构
    if sat_type == 'tsn':
        sat_name = f"{sat_type.upper()}_1_{sat_id}"
    elif sat_type == 'yg':
        sat_name = f"{sat_type.upper()}_1_{sat_id-8}"
    elif sat_type == 'xw':
        sat_name = f"{sat_type.upper()}_1_{sat_id-20}"
    else:
        sat_name = f"{sat_type.upper()}_1_{sat_id}"
    
    task = {
        "sat_id": sat_id,
        "sat_name": sat_name,
        "timestamp": current_time,
        
        # CPU使用情况 (使用率%)
        "cpu_usage": {
            "health": 1,
            "cpu_total_cores": random.choice([2, 4, 8]),
            "used": round(apply_usage_fluctuation(random.uniform(10, 60)), 1)
        },
        
        # 内存使用情况 (使用率%)
        "mem_usage": {
            "health": 1,
            "total": random.choice([4096, 8192, 16384]),
            "total_data_type": 1,  # MB
            "used": round(apply_usage_fluctuation(random.uniform(20, 70)), 1)
        },
        
        # 磁盘使用情况 (使用率%)
        "disk_usage": {
            "health": 1,
            "total": random.choice([50, 100, 200, 500]),
            "total_data_type": 2,  # GB
            "used": round(apply_usage_fluctuation(random.uniform(10, 50)), 1)
        },
        
        # 生成链接列表
        "linkList": generate_link_list(sat_id, sat_count)
    }
    
    # TSN类型不添加GPU字段，其他类型添加GPU字段
    if sat_type.lower() != 'tsn':
        task["gpu_usage"] = {
            "health": 1,
            "total": random.choice([4096, 8192, 16384]),
            "total_data_type": 1,  # MB
            "used": round(apply_usage_fluctuation(random.uniform(15, 80)), 1),  # 使用率%
            "gpu_occupied": random.choice([0, 1]),
        }
    
    # 根据卫星类型设置传感器
    if sat_type.lower() in ["yg", "xw", "tsn"]:
        task["sensors"] = get_sensors_from_tasks(sat_id, sat_type)
    else:
        task["sensors"] = []
    
    return task

def generate_random_sensors():
    """为遥感卫星生成随机传感器列表
    
    Returns:
        list: 传感器列表，包含SAR、红外、可见光三种传感器
    """
    sensors = []
    
    # 传感器类型定义
    sensor_types = [
        0,  # SAR合成孔径雷达
        1,  # HW红外
        2   # KJG可见光
    ]
    
    for sensor_type in sensor_types:
        sensor = {
            "sensor_type": sensor_type,
            "health": random.randint(0, 1),  # 0健康 1异常
            "occupied": random.randint(100, 999)  # 任务占用ID (100-999)
        }
        sensors.append(sensor)
    
    return sensors

def get_sensors_from_tasks(sat_id, sat_type):
    """从complete_task.json中读取传感器信息
    
    Args:
        sat_id: 卫星ID
        sat_type: 卫星类型，"tsn", "xw", "yg" 之一
    
    Returns:
        list: 传感器列表，包含相应类型的传感器
    """
    # 确保sat_id是整数
    sat_id = int(sat_id) if sat_id is not None else 0
    
    # 默认传感器列表为空
    default_sensors = []
    
    # 如果complete_task.json不存在，返回默认传感器（空列表）
    if not os.path.exists(COMPLETE_TASK_JSON_PATH):
        print(f"警告: {COMPLETE_TASK_JSON_PATH} 不存在，使用默认传感器配置（空列表）")
        return default_sensors
        
    try:
        # 读取complete_task.json
        with open(COMPLETE_TASK_JSON_PATH, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
        sensors = []  # 从空列表开始
        has_assignments = False
        
        # 遍历所有任务
        for task in task_data.get('task_info', []):
            # 遍历资源计划
            plan_list = task.get('rs_plan_res', {}).get('plan_list', [])
            for plan in plan_list:
                # 如果计划中的卫星ID与当前卫星ID匹配
                if plan.get('sat_id') == sat_id:
                    sensor_type = plan.get('sensors')
                    task_id = task.get('task_id')
                    
                    # 添加新的传感器
                    sensor = {
                        "sensor_type": sensor_type,
                        "health": 1,  # 默认健康
                        "occupied": task_id  # 设置为任务ID
                    }
                    
                    # 检查是否已存在相同类型的传感器
                    existing_sensor = next((s for s in sensors if s["sensor_type"] == sensor_type), None)
                    if existing_sensor:
                        # 更新已存在的传感器
                        existing_sensor["occupied"] = task_id
                    else:
                        # 添加新传感器
                        sensors.append(sensor)
                        
                    has_assignments = True
                    print(f"卫星{sat_id}({sat_type})的传感器{sensor_type}被任务{task_id}占用")
        
        if not has_assignments:
            print(f"卫星{sat_id}({sat_type})没有分配的任务，传感器列表为空")
            
        return sensors
        
    except Exception as e:
        print(f"从complete_task.json读取传感器信息时出错: {e}")
        import traceback
        traceback.print_exc()
        return []  # 出错时返回空列表

def convert_yaml_to_json(vm_folder_path, output_json_path, sat_type):
    """将VM文件夹下的YAML文件转换为JSON文件
    
    Args:
        vm_folder_path: VM文件夹路径
        output_json_path: 输出JSON文件路径
        sat_type: 卫星类型，必须是 "tsn", "xw", 或 "yg" 之一
    
    Returns:
        bool: 是否成功
    """
    # 获取所有YAML文件
    yaml_files = glob(os.path.join(vm_folder_path, "*.yaml"))
    
    # 准备JSON结构
    vm_name = os.path.basename(vm_folder_path)
    
    # 根据卫星类型设置file_id和constellation_name
    if sat_type.lower() == "tsn":
        file_id = 1
        constellation_name = "TSN"
    elif sat_type.lower() == "xw":
        file_id = 2
        constellation_name = "XINGWANG"
    elif sat_type.lower() == "yg":
        file_id = 3
        constellation_name = "YAOGAN"
    else:
        file_id = 0
        constellation_name = f"{sat_type.upper()}_CONSTELLATION"
    
    result = {
        "file_id": file_id,
        "constellation_name": constellation_name,
        "task_info": []
    }
    
    # 如果没有YAML文件，生成一个默认的JSON结构
    if not yaml_files:
        print(f"在 {vm_folder_path} 中没有找到YAML文件，将生成默认JSON结构")
        
        # 根据卫星类型设置ID范围
        if sat_type.lower() == "yg":
            sat_id_range = range(9, 21)  # YG: 9-20 (12个)
        elif sat_type.lower() == "xw":
            sat_id_range = range(21, 45)  # XW: 21-44 (24个)
        elif sat_type.lower() == "tsn":
            sat_id_range = range(1, 9)   # TSN: 1-8 (8个)
        else:
            sat_id_range = range(1, 9)   # 默认
        
        for sat_id in sat_id_range:
            # 创建默认任务信息
            task = create_default_task(sat_id, sat_type, len(sat_id_range))
            result["task_info"].append(task)
            print(f"为卫星{sat_id}({sat_type})创建默认任务信息")
    else:
        # 处理每个YAML文件
        sat_count = len(yaml_files)  # 总卫星数量
        processed_sat_ids = set()  # 记录已处理的sat_id
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    yaml_data = yaml.safe_load(f)
                
                if not yaml_data or 'spec' not in yaml_data:
                    print(f"跳过文件 {yaml_file}，格式不正确")
                    continue
                
                spec = yaml_data['spec']
                
                # 获取卫星名称
                sat_ip = extract_ip_from_yaml(yaml_data)
                if not sat_ip:
                    sat_ip = os.path.basename(yaml_file).replace('.yaml', '')
                
                # 从sat_ip中解析IP地址，然后获取sat_id
                derived_sat_id, derived_sat_name = ip_to_sat_id_and_name(sat_ip, sat_type)
                
                # 创建任务信息
                task = {
                    "sat_id": derived_sat_id if derived_sat_id is not None else None,
                    "sat_name": derived_sat_name,
                    "timestamp": convert_timestamp(spec.get('timestamp', '')),
                }
                
                # 记录已处理的sat_id
                if derived_sat_id is not None:
                    processed_sat_ids.add(derived_sat_id)
                    print(f"从 {sat_ip} 解析得到sat_id: {derived_sat_id}")
                else:
                    print(f"警告: 无法从 {sat_ip} 解析IP地址获取sat_id，跳过此文件")
                    continue
                
                # CPU使用情况 (使用率%)
                if 'cpuUsage' in spec:
                    cpu_cores = spec['cpuUsage'].get('cores', 2)
                    cpu_usage_str = spec['cpuUsage'].get('usage', '0%')
                    cpu_usage_percent = float(cpu_usage_str.strip('%'))
                    
                    # 对使用率进行倍数浮动 (0.5~2倍)
                    final_usage_percent = apply_usage_fluctuation(cpu_usage_percent, 0.0, 100.0)
                    
                    task["cpu_usage"] = {
                        "health": 1,
                        "cpu_total_cores": int(cpu_cores),  # 总核心数不变
                        "used": round(final_usage_percent, 1)  # 使用率%
                    }

                # 内存使用情况 (使用率%)
                if 'memoryUsage' in spec:
                    mem_total, total_type = convert_size_to_type(spec['memoryUsage'].get('total', '0MB'))
                    mem_used, _ = convert_size_to_type(spec['memoryUsage'].get('used', '0MB'))
                    
                    # 计算使用百分比
                    usage_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0.0
                    # 对使用百分比进行倍数浮动
                    final_usage_percent = apply_usage_fluctuation(usage_percent, 0.0, 100.0)
                    
                    task["mem_usage"] = {
                        "health": 1,
                        "total": mem_total,  # 总内存不变
                        "total_data_type": total_type,
                        "used": round(final_usage_percent, 1)  # 使用率%
                    }
                
                # 磁盘使用情况 (使用率%)
                if 'diskUsage' in spec:
                    disk_total, total_type = convert_size_to_type(spec['diskUsage'].get('total', '0MB'))
                    disk_used, _ = convert_size_to_type(spec['diskUsage'].get('used', '0MB'))
                    
                    # 计算使用百分比
                    usage_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0.0
                    # 对使用百分比进行倍数浮动
                    final_usage_percent = apply_usage_fluctuation(usage_percent, 0.0, 100.0)
                    
                    task["disk_usage"] = {
                        "health": 1,
                        "total": disk_total,  # 总磁盘容量不变
                        "total_data_type": total_type,
                        "used": round(final_usage_percent, 1)  # 使用率%
                    }
                
                # GPU使用情况 (TSN类型不添加GPU字段，其他类型使用率%)
                if sat_type.lower() != 'tsn':
                    if 'gpuUsage' in spec:
                        gpu_total, total_type = convert_size_to_type(spec['gpuUsage'].get('total', '0MB'))
                        gpu_used, _ = convert_size_to_type(spec['gpuUsage'].get('used', '0MB'))
                        
                        # 计算使用百分比
                        usage_percent = (gpu_used / gpu_total * 100) if gpu_total > 0 else 0.0
                        # 对使用百分比进行倍数浮动
                        final_usage_percent = apply_usage_fluctuation(usage_percent, 0.0, 100.0)
                        
                        task["gpu_usage"] = {
                            "health": 1,
                            "total": gpu_total,  # 总GPU内存不变
                            "total_data_type": total_type,
                            "used": round(final_usage_percent, 1),  # 使用率%
                            "gpu_occupied": (1 if final_usage_percent > 10 else 0),
                        }
                        
                
                # 添加链接列表
                # 从YAML文件中读取linkList，如果不存在则生成默认的
                sat_id_value = task["sat_id"]  # 提前定义sat_id_value变量
                if 'linkList' in spec and spec['linkList']:
                    # 直接使用YAML文件中的linkList，并进行格式处理
                    task["linkList"] = process_link_list_from_yaml(spec['linkList'])
                    print(f"从YAML文件读取到{len(spec['linkList'])}个链接")
                else:
                    # 如果YAML文件中没有linkList，则生成默认的
                    task["linkList"] = generate_link_list(sat_id_value, sat_count)
                    print(f"YAML文件中没有linkList，为卫星{sat_id_value}生成默认链接")
                
                # 添加传感器列表，根据卫星类型处理
                if sat_type.lower() in ["yg", "xw", "tsn"]:
                    # 从complete_task.json中获取传感器信息，使用task中的sat_id
                    task["sensors"] = get_sensors_from_tasks(sat_id_value, sat_type)
                else:
                    # 其他类型卫星使用空传感器列表
                    task["sensors"] = []
                
                # 添加到任务列表
                result["task_info"].append(task)
                
            except Exception as e:
                print(f"处理文件 {yaml_file} 时出错: {e}")
        
        # 补充缺失的卫星 (特别是YG类型)
        if sat_type.lower() == "yg":
            expected_sat_ids = set(range(9, 21))  # YG应该有sat_id 9-20
        elif sat_type.lower() == "xw":
            expected_sat_ids = set(range(21, 45))  # XW应该有sat_id 21-44
        elif sat_type.lower() == "tsn":
            expected_sat_ids = set(range(1, 9))   # TSN应该有sat_id 1-8
        else:
            expected_sat_ids = processed_sat_ids  # 其他类型不补充
        
        missing_sat_ids = expected_sat_ids - processed_sat_ids
        
        if missing_sat_ids:
            print(f"发现缺失的卫星ID: {sorted(missing_sat_ids)}，正在补充...")
            
            # 获取已有卫星的数据作为参考
            existing_tasks = [task for task in result["task_info"] if task.get("sat_id") in processed_sat_ids]
            
            for missing_sat_id in sorted(missing_sat_ids):
                # 基于已有数据创建缺失的卫星信息
                if existing_tasks:
                    # 随机选择一个已有任务作为模板
                    template_task = random.choice(existing_tasks)
                    
                    # 创建新任务，复制模板但修改关键信息
                    new_task = template_task.copy()
                    new_task["sat_id"] = missing_sat_id
                    
                    if sat_type == 'yg':
                        new_task["sat_name"] = f"YG_1_{missing_sat_id-8}"
                    elif sat_type == 'xw':
                        new_task["sat_name"] = f"XW_1_{missing_sat_id-20}"
                    elif sat_type == 'tsn':
                        new_task["sat_name"] = f"TSN_1_{missing_sat_id}"
                    
                    new_task["timestamp"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 为资源使用情况添加倍数浮动
                    if "cpu_usage" in new_task:
                        new_task["cpu_usage"] = new_task["cpu_usage"].copy()
                        base_usage_percent = new_task["cpu_usage"]["used"]
                        new_task["cpu_usage"]["used"] = round(apply_usage_fluctuation(base_usage_percent, 0.0, 100.0), 1)
                    
                    if "mem_usage" in new_task:
                        new_task["mem_usage"] = new_task["mem_usage"].copy()
                        base_usage_percent = new_task["mem_usage"]["used"]
                        new_task["mem_usage"]["used"] = round(apply_usage_fluctuation(base_usage_percent, 0.0, 100.0), 1)
                    
                    if "disk_usage" in new_task:
                        new_task["disk_usage"] = new_task["disk_usage"].copy()
                        base_usage_percent = new_task["disk_usage"]["used"]
                        new_task["disk_usage"]["used"] = round(apply_usage_fluctuation(base_usage_percent, 0.0, 100.0), 1)
                    
                    if "gpu_usage" in new_task and sat_type.lower() != 'tsn':
                        new_task["gpu_usage"] = new_task["gpu_usage"].copy()
                        base_usage_percent = new_task["gpu_usage"]["used"]
                        final_usage_percent = round(apply_usage_fluctuation(base_usage_percent, 0.0, 100.0), 1)
                        new_task["gpu_usage"]["used"] = final_usage_percent
                        new_task["gpu_usage"]["gpu_occupied"] = (1 if final_usage_percent > 10 else 0)
                    
                    # 生成新的链接列表
                    new_task["linkList"] = generate_link_list(missing_sat_id, len(expected_sat_ids))
                    
                    # 获取传感器信息
                    new_task["sensors"] = get_sensors_from_tasks(missing_sat_id, sat_type)
                    
                else:
                    # 如果没有已有任务作为模板，创建默认任务
                    new_task = create_default_task(missing_sat_id, sat_type, len(expected_sat_ids))
                
                result["task_info"].append(new_task)
                print(f"补充了缺失的卫星{missing_sat_id}({sat_type})信息")
        else:
            print(f"所有预期的{sat_type}卫星都已存在，无需补充")
    
    # 写入JSON文件
    with open(output_json_path, 'w') as f:
        json.dump(result, f, indent=4)
    
    print(f"成功创建JSON文件并保存到 {output_json_path}，包含 {len(result['task_info'])} 个卫星信息")
    return True

def process_link_list_from_yaml(link_list):
    """处理从YAML文件读取的linkList，确保格式正确
    
    Args:
        link_list: 从YAML文件读取的linkList
        
    Returns:
        list: 处理后的linkList
    """
    processed_links = []
    
    for link in link_list:
        processed_link = {
            "health": int(link.get('health', 1)),
            "type": str(link.get('type', 'laser')),
            "rate": float(link.get('rate', 25)),
            "rate_data_type": int(link.get('rate_data_type', 3)),
            "delay": float(link.get('delay', 100.0)),
            "jitter": float(link.get('jitter', 0.0)),
            "loss": float(link.get('loss', 0.0)),
            "end_sat_id": str(link.get('end_sat_id', '1'))  # 确保end_sat_id是字符串
        }
        processed_links.append(processed_link)
    
    return processed_links

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python resource_info_gathering.py <vm_folder_path> <sat_type>")
        print("示例: python resource_info_gathering.py /home/sjtu/sat_frr_thu/resource_info/vm46 tsn")
        print("sat_type 必须是 \"tsn\", \"xw\", 或 \"yg\" 之一")
        sys.exit(1)
    
    vm_folder_path = sys.argv[1]
    sat_type = sys.argv[2].lower()
    
    # # 验证卫星类型
    # if sat_type not in ["tsn", "xw", "yg"]:
    #     print(f"错误: 卫星类型 {sat_type} 无效，必须是 \"tsn\", \"xw\", 或 \"yg\" 之一")
    #     sys.exit(1)
    
    if not os.path.isdir(vm_folder_path):
        print(f"错误: 文件夹 {vm_folder_path} 不存在")
        sys.exit(1)
    
    # 检查complete_task.json是否存在
    if os.path.exists(COMPLETE_TASK_JSON_PATH):
        print(f"信息: 将从 {COMPLETE_TASK_JSON_PATH} 读取任务信息来生成传感器状态")
    else:
        print(f"警告: {COMPLETE_TASK_JSON_PATH} 不存在，将使用默认传感器配置")
    
    # 确定输出文件路径 (在输入文件夹的上一级目录)
    parent_dir = os.path.dirname(os.path.abspath(vm_folder_path))
    output_json_path = os.path.join(parent_dir, f"{sat_type}_constellation.json")
    
    print(f"开始处理卫星类型: {sat_type}，数据源: {vm_folder_path}")
    print(f"将使用从sat_ip中提取的IP地址来反推卫星ID")
    success = convert_yaml_to_json(vm_folder_path, output_json_path, sat_type)
    
    if success:
        print(f"处理完成: {sat_type} 星座JSON文件已生成到 {output_json_path}")
    else:
        print(f"错误: 生成 {sat_type} 星座JSON文件失败")
    
    sys.exit(0 if success else 1)
