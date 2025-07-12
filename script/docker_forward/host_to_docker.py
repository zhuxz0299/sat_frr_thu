#!/usr/bin/env python3
# host_to_docker.py - 宿主机向Docker传输文件
import os
import requests
import json
import sys
import argparse
from pathlib import Path


def send_file_to_docker(file_path, docker_host="10.0.64.185", docker_port=9000):
    """
    将文件发送到Docker容器
    """
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False
    
    # 直接传输文件
    url = f"http://{docker_host}:{docker_port}/receive_file"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            response = requests.post(url, files=files, timeout=10)
        
        if response.status_code == 200:
            print(f"文件 {os.path.basename(file_path)} 成功发送到Docker")
            return True
        else:
            print(f"发送失败，状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"发送文件到Docker时出错: {e}")
        return False


def send_folder_to_docker(folder_path, docker_host="10.0.64.185", docker_port=9000):
    """
    将文件夹中的所有文件发送到Docker容器
    """
    if not os.path.exists(folder_path):
        print(f"文件夹不存在: {folder_path}")
        return
    
    folder = Path(folder_path)
    success_count = 0
    total_count = 0
    
    # 遍历文件夹中的所有文件
    for file_path in folder.rglob('*'):
        if file_path.is_file():
            total_count += 1
            print(f"正在发送: {file_path}")
            if send_file_to_docker(str(file_path), docker_host, docker_port):
                success_count += 1
    
    print(f"\n传输完成: {success_count}/{total_count} 个文件成功传输")


if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将文件夹中的文件发送到Docker容器')
    parser.add_argument('folder_path', help='要传输的文件夹路径')
    parser.add_argument('docker_host', help='Docker容器的IP地址')
    parser.add_argument('--port', '-p', type=int, default=9000, help='Docker容器的端口号 (默认: 9000)')
    
    args = parser.parse_args()
    
    # 发送文件夹到Docker
    send_folder_to_docker(args.folder_path, args.docker_host, args.port)
    
    print(f"文件夹: {args.folder_path}")
    print(f"目标Docker: {args.docker_host}:{args.port}")
    print("-" * 50)

    # vm47 10.0.64.186 docker 166.167.0.27
    # vm46 10.0.64.182 docker 166.167.0.34
    # vm45 10.0.64.178 docker 166.167.0.43
