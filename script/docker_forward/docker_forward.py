# transfer_point_server.py
from flask import Flask, request
import json
import os
import subprocess
import requests
import argparse
import sys

app = Flask(__name__)

# 默认参数，可以通过命令行参数修改
VM_IP = "10.0.64.182"
VM_USER = "root"
VM_PASSWORD = "passw0rd@123"
DEST_PATH = "/home/resource_manager/resource_info"


@app.route('/receive_file', methods=['POST'])
def receive_file():
    """接收文件并转发到虚拟机"""
    if 'file' not in request.files:
        return "No file", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400
    
    # 保存文件到Docker
    filename = f"received_{file.filename}"
    file.save(filename)
    print(f"文件 {file.filename} 已保存到Docker")
    
    # 转发到虚拟机
    forward_file_to_vm(filename, file.filename)
    
    return "File received and forwarded"


def forward_file_to_vm(local_path, original_filename):
    """使用SCP转发文件到虚拟机"""
    try:
        destination_path = f"/home/resource_manager/resource_info/{original_filename}"  # 根据需要修改目标路径
        
        # 使用sshpass避免交互式密码输入
        scp_command = [
            "sshpass", "-p", VM_PASSWORD,
            "scp", "-o", "StrictHostKeyChecking=no",
            local_path,
            f"{VM_USER}@{VM_IP}:{destination_path}"
        ]
        
        # 执行SCP命令
        result = subprocess.run(scp_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"文件 {original_filename} 成功通过SCP转发到虚拟机")
            # 可选：删除Docker中的临时文件
            os.remove(local_path)
            print(f"删除Docker中的临时文件: {local_path}")
        else:
            print(f"SCP转发失败: {result.stderr}")
            
    except Exception as e:
        print(f"SCP转发错误: {e}")

if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Docker文件转发服务器')
    parser.add_argument('--vm-ip', help='虚拟机IP地址', default="10.0.64.182")
    args = parser.parse_args()
    VM_IP = args.vm_ip

    app.run(host='0.0.0.0', port=9000, debug=True)