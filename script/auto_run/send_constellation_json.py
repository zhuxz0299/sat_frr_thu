#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
星座信息传输脚本
将资源信息JSON文件传输到Windows电脑的指定目录
每10秒执行一次
"""

import os
import sys
import time
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path


class ConstellationSender:
    def __init__(self, ip="192.168.200.254", user="123", password="", interval=10):
        # 获取项目根目录
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent.parent
        
        # 设置工作目录为项目根目录
        os.chdir(self.project_root)
        
        # 连接参数
        self.ip = ip
        self.user = user
        self.password = password
        self.interval = interval
        
        # 脚本路径
        self.resource_info_gathering_py = "./script/resource_process/resource_info_gathering.py"
        
        # 源文件路径
        self.source_dir = "./resource_info"
        self.yg_file = f"{self.source_dir}/yg_constellation.json"
        self.xw_file = f"{self.source_dir}/xw_constellation.json"
        self.tsn_file = f"{self.source_dir}/tsn_constellation.json"
        
        # 目标路径
        self.yg_dest = "D:/temp/qinghua/yg"
        self.xw_dest = "D:/temp/qinghua/xw"
        self.tsn_dest = "D:/temp/qinghua/tsn"
        
        # 日志文件
        self.log_dir = self.project_root / "log"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "constellation_sender_log.txt"
        
        # 文件配置映射
        self.file_configs = [
            {
                "source": self.yg_file,
                "dest": f"{self.yg_dest}/yg_constellation.json",
                "dest_dir": self.yg_dest,
                "vm_dir": f"{self.source_dir}/vm47",
                "type": "yg",
                "name": "yg_constellation.json"
            },
            {
                "source": self.xw_file,
                "dest": f"{self.xw_dest}/xw_constellation.json",
                "dest_dir": self.xw_dest,
                "vm_dir": f"{self.source_dir}/vm46",
                "type": "xw",
                "name": "xw_constellation.json"
            },
            {
                "source": self.tsn_file,
                "dest": f"{self.tsn_dest}/tsn_constellation.json",
                "dest_dir": self.tsn_dest,
                "vm_dir": f"{self.source_dir}/vm45",
                "type": "tsn",
                "name": "tsn_constellation.json"
            }
        ]
    
    def log_message(self, message, also_print=True):
        """写入日志文件并可选择性打印到控制台"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
        
        if also_print:
            print(log_entry)
    
    def log_separator(self, title=""):
        """在日志中添加分隔符"""
        separator = "=" * 60
        if title:
            self.log_message(separator, also_print=False)
            self.log_message(f" {title} ", also_print=False)
            self.log_message(separator, also_print=False)
        else:
            self.log_message(separator, also_print=False)
    
    def generate_json_files(self):
        """生成JSON文件"""
        self.log_message("开始生成JSON文件...")
        
        # 检查脚本是否存在
        if not os.path.exists(self.resource_info_gathering_py):
            error_msg = f"错误: 找不到脚本 {self.resource_info_gathering_py}"
            self.log_message(error_msg)
            return False
        
        success_count = 0
        total_count = len(self.file_configs)
        
        for config in self.file_configs:
            vm_dir = config["vm_dir"]
            file_type = config["type"]
            
            self.log_message(f"处理 {file_type} 类型 ({vm_dir})...")
            
            try:
                result = subprocess.run(
                    ["python3", self.resource_info_gathering_py, vm_dir, file_type],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=self.project_root
                )
                
                if result.returncode == 0:
                    success_count += 1
                    self.log_message(f"✓ {file_type} 类型处理成功")
                    if result.stdout.strip():
                        self.log_message(f"  输出: {result.stdout.strip()}", also_print=False)
                else:
                    self.log_message(f"✗ {file_type} 类型处理失败，返回码: {result.returncode}")
                    if result.stderr.strip():
                        self.log_message(f"  错误: {result.stderr.strip()}", also_print=False)
                        
            except subprocess.TimeoutExpired:
                self.log_message(f"✗ {file_type} 类型处理超时")
            except Exception as e:
                self.log_message(f"✗ {file_type} 类型处理异常: {str(e)}")
        
        self.log_message(f"JSON文件生成完成，成功: {success_count}/{total_count}")
        return success_count > 0
    
    def transfer_file(self, source, dest, dest_dir, name):
        """传输单个文件"""
        if not os.path.exists(source):
            self.log_message(f"⚠ 文件不存在，跳过: {name}")
            return False
        
        self.log_message(f"正在传输 {name} 到 {dest_dir}...")
        
        try:
            # 构建scp命令
            if self.password:
                cmd = [
                    "sshpass", "-p", self.password,
                    "scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                    source, f"{self.user}@{self.ip}:{dest}"
                ]
            else:
                cmd = [
                    "scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                    source, f"{self.user}@{self.ip}:{dest}"
                ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.log_message(f"✓ {name} 传输成功")
                return True
            else:
                self.log_message(f"✗ {name} 传输失败，返回码: {result.returncode}")
                if result.stderr.strip():
                    self.log_message(f"  错误: {result.stderr.strip()}", also_print=False)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_message(f"✗ {name} 传输超时")
            return False
        except Exception as e:
            self.log_message(f"✗ {name} 传输异常: {str(e)}")
            return False
    
    def transfer_all_files(self):
        """传输所有文件"""
        self.log_message("开始传输文件...")
        
        success_count = 0
        total_count = len(self.file_configs)
        
        for config in self.file_configs:
            if self.transfer_file(
                config["source"],
                config["dest"],
                config["dest_dir"],
                config["name"]
            ):
                success_count += 1
        
        self.log_message(f"文件传输完成，成功: {success_count}/{total_count}")
        return success_count, total_count
    
    def process_and_transfer(self):
        """执行一次完整的处理和传输流程"""
        cycle_start = datetime.now()
        
        self.log_separator(f"开始处理周期: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 生成JSON文件
        if not self.generate_json_files():
            self.log_message("JSON文件生成失败，跳过传输")
            return False, 0, 0
        
        # 2. 传输文件
        success_count, total_count = self.transfer_all_files()
        
        cycle_end = datetime.now()
        duration = cycle_end - cycle_start
        
        self.log_message(f"处理周期完成，耗时: {duration.total_seconds():.1f} 秒")
        self.log_separator()
        
        return True, success_count, total_count
    
    def run_once(self):
        """运行一次"""
        print("单次运行模式")
        print(f"目标主机: {self.ip}")
        print(f"用户名: {self.user}")
        print(f"日志文件: {self.log_file}")
        
        success, transferred, total = self.process_and_transfer()
        
        if success:
            print(f"运行完成，传输 {transferred}/{total} 个文件")
        else:
            print("运行失败")
    
    def run_continuous(self):
        """持续运行"""
        print("持续运行模式")
        print(f"目标主机: {self.ip}")
        print(f"用户名: {self.user}")
        print(f"执行间隔: {self.interval} 秒")
        print(f"日志文件: {self.log_file}")
        print("按 Ctrl+C 停止运行")
        
        self.log_message("星座信息传输器启动")
        self.log_message(f"目标主机: {self.ip}, 用户: {self.user}, 间隔: {self.interval}秒")
        
        try:
            # 首次运行
            self.process_and_transfer()
            
            # 定期运行
            while True:
                next_time = (datetime.now() + timedelta(seconds=self.interval)).strftime('%H:%M:%S')
                print(f"\n等待 {self.interval} 秒... (下次运行: {next_time})")
                time.sleep(self.interval)
                
                self.process_and_transfer()
                
        except KeyboardInterrupt:
            print(f"\n\n收到停止信号，正在退出...")
            self.log_message("收到中断信号，星座信息传输器停止")
            print("传输器已停止")
        except Exception as e:
            error_msg = f"运行过程中出现错误: {str(e)}"
            print(f"\n\n{error_msg}")
            self.log_message(error_msg)
            sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='星座信息传输器')
    parser.add_argument('--ip', '-i', default='192.168.200.254', help='目标主机IP地址')
    parser.add_argument('--user', '-u', default='123', help='用户名')
    parser.add_argument('--password', '-p', default='', help='密码（不提供则默认为空）')
    parser.add_argument('--interval', '-t', type=int, default=10, help='运行间隔（秒），默认10秒')
    parser.add_argument('--once', '-o', action='store_true', help='只运行一次，不持续循环')
    
    args = parser.parse_args()
    
    # 创建传输器
    sender = ConstellationSender(
        ip=args.ip,
        user=args.user,
        password=args.password,
        interval=args.interval
    )
    
    # 运行
    if args.once:
        sender.run_once()
    else:
        sender.run_continuous()


if __name__ == "__main__":
    main()
