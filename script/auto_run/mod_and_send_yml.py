#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动运行脚本
每隔一分钟自动运行 yaml_pre_modify.py 和 host_to_docker.py 脚本
"""

import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path


class AutoRunner:
    def __init__(self):
        # 获取项目根目录（假设脚本在 script/auto_run 目录下）
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent.parent
        
        # 设置工作目录为项目根目录
        os.chdir(self.project_root)
        
        # 日志文件路径
        self.log_dir = self.project_root / "log"
        self.log_dir.mkdir(exist_ok=True)
        
        self.yaml_log_file = self.log_dir / "yaml_pre_modify_log.txt"
        self.docker_log_file = self.log_dir / "host_to_docker_log.txt"
        
        # 脚本路径
        self.yaml_script = "./script/resource_process/yaml_pre_modify.py"
        self.docker_script = "./script/docker_forward/host_to_docker.py"
        
        # Docker传输配置
        self.docker_configs = [
            {"folder": "./resource_info/vm45", "host": "166.167.0.43"},
            {"folder": "./resource_info/vm46", "host": "166.167.0.34"},
            {"folder": "./resource_info/vm47", "host": "166.167.0.27"}
        ]
    
    def log_timestamp(self, log_file):
        """在日志文件中添加时间戳"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"运行时间: {timestamp}\n")
            f.write(f"{'='*50}\n")
    
    def run_yaml_modifier(self):
        """运行 yaml_pre_modify.py 脚本"""
        try:
            self.log_timestamp(self.yaml_log_file)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始运行 yaml_pre_modify.py...")
            
            # 运行脚本并将输出追加到日志文件
            with open(self.yaml_log_file, 'a', encoding='utf-8') as log_f:
                result = subprocess.run(
                    ["python3", self.yaml_script],
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=self.project_root
                )
            
            if result.returncode == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] yaml_pre_modify.py 运行成功")
                with open(self.yaml_log_file, 'a', encoding='utf-8') as f:
                    f.write("\n✓ 脚本运行成功\n")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] yaml_pre_modify.py 运行失败，返回码: {result.returncode}")
                with open(self.yaml_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n✗ 脚本运行失败，返回码: {result.returncode}\n")
                    
        except Exception as e:
            error_msg = f"运行 yaml_pre_modify.py 时出错: {str(e)}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
            with open(self.yaml_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n✗ {error_msg}\n")
    
    def run_docker_transfers(self):
        """运行所有 host_to_docker.py 传输任务"""
        try:
            self.log_timestamp(self.docker_log_file)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始运行 Docker 文件传输...")
            
            success_count = 0
            total_count = len(self.docker_configs)
            
            with open(self.docker_log_file, 'a', encoding='utf-8') as log_f:
                for i, config in enumerate(self.docker_configs, 1):
                    folder = config["folder"]
                    host = config["host"]
                    
                    log_f.write(f"\n--- 传输任务 {i}/{total_count} ---\n")
                    log_f.write(f"文件夹: {folder}\n")
                    log_f.write(f"目标主机: {host}\n")
                    log_f.flush()
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 传输 {folder} 到 {host}...")
                    
                    # 运行传输脚本
                    result = subprocess.run(
                        ["python3", self.docker_script, folder, host],
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=self.project_root
                    )
                    
                    if result.returncode == 0:
                        success_count += 1
                        log_f.write(f"✓ 传输成功\n")
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {folder} 传输成功")
                    else:
                        log_f.write(f"✗ 传输失败，返回码: {result.returncode}\n")
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {folder} 传输失败")
                    
                    log_f.flush()
                
                # 写入总结
                log_f.write(f"\n传输总结: {success_count}/{total_count} 个任务成功\n")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Docker 传输完成: {success_count}/{total_count} 成功")
                    
        except Exception as e:
            error_msg = f"运行 Docker 传输时出错: {str(e)}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
            with open(self.docker_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n✗ {error_msg}\n")
    
    def run_once(self):
        """执行一次完整的运行周期"""
        cycle_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"开始新的运行周期: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # 1. 运行 YAML 修改脚本
        self.run_yaml_modifier()
        
        # 2. 运行 Docker 传输脚本
        self.run_docker_transfers()
        
        cycle_end = datetime.now()
        duration = cycle_end - cycle_start
        print(f"\n运行周期完成，耗时: {duration.total_seconds():.1f} 秒")
    
    def run_continuous(self, interval=60):
        """持续运行，按指定间隔执行"""
        print("自动运行器启动")
        print(f"项目根目录: {self.project_root}")
        print(f"YAML 日志: {self.yaml_log_file}")
        print(f"Docker 日志: {self.docker_log_file}")
        print(f"运行间隔: {interval} 秒")
        print("按 Ctrl+C 停止运行")
        
        try:
            while True:
                self.run_once()
                
                # 计算下次运行时间
                next_time = (datetime.now() + timedelta(seconds=interval)).strftime('%H:%M:%S')
                print(f"\n等待 {interval} 秒... (下次运行: {next_time})")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n收到停止信号，正在退出...")
            print("自动运行器已停止")
        except Exception as e:
            print(f"\n\n运行过程中出现错误: {str(e)}")
            sys.exit(1)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='自动运行 YAML 修改和 Docker 传输脚本')
    parser.add_argument('--once', '-o', action='store_true', help='只运行一次，不持续循环')
    parser.add_argument('--interval', '-i', type=int, default=60, help='运行间隔（秒），默认60秒')
    
    args = parser.parse_args()
    
    runner = AutoRunner()
    
    if args.once:
        print("单次运行模式")
        runner.run_once()
    else:
        print(f"持续运行模式，间隔 {args.interval} 秒")
        runner.run_continuous(args.interval)


if __name__ == "__main__":
    main()
