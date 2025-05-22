import argparse
import socket
import yaml
import json

# 附件中的YAML内容
yaml_content = '''messageInfo: 1
satID: 10.0.64.1
timestamp: "2025-05-21T00:00:00"
CPU:
  health: 1
  used: 50
MEM:
  health: 1
  used: 50
DISK:
  health: 1
  used: 50
LINK:
  num: 5
  links:
    - health: 1
      type: "laser"
      rate: 10000
      delay: 5
      jitter: 1
      loss: 0.01
      end: "1"
    - health: 1
      type: "microwave"
      rate: 1000
      delay: 20
      jitter: 5
      loss: 0.05
      end: "2"
    - health: 1
      type: "microwave"
      rate: 1000
      delay: 20
      jitter: 5
      loss: 0.05
      end: "3"
    - health: 1
      type: "rf"
      rate: 100
      delay: 30
      jitter: 10
      loss: 0.1
      end: "4"
    - health: 1
      type: "rf"
      rate: 100
      delay: 30
      jitter: 10
      loss: 0.1
      end: "5"
YG:
  startTime: "2025-05-21T00:00:00"
  endTime: "2025-05-21T10:00:00"
  num: 10
  type: 1
  health: 1
  occupied: 0
'''

def send_data_to_ip(target_ip, port=12345):
    # 读取文件夹中的yaml文件
    # try:
    #     with open('template.yaml', 'r',encoding='utf-8') as file:
    #         yaml_content = file.read()
    # except Exception as e:
    #     print(f"无法读取YAML文件: {e}")
    #     return False
    
    # 将yaml内容转换为json
    try:
        data = yaml.safe_load(yaml_content)
    except Exception as e:
        print(f"无法解析YAML内容: {e}")
        return False
    
    json_data = json.dumps(data, separators=(',', ':'))
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            bytes_data = json_data.encode('utf-8')
            print(f"准备发送 {len(bytes_data)} 字节的数据到 {target_ip}:{port}")
            
            s.sendto(bytes_data, (target_ip, port))
            print(f"数据已成功发送至 {target_ip}:{port}")
            return True
    except Exception as e:
        print(f"发送数据时出错: {e}")
        return False

def main():
    # 使用argparse解析命令行参数
    parser = argparse.ArgumentParser(description='UDP发送端程序，发送YAML数据转换的JSON')
    parser.add_argument('-ip', '--target_ip', required=True, help='目标IP地址')
    parser.add_argument('-p', '--port', type=int, default=12345, help='目标端口，默认12345')
    args = parser.parse_args()

    success = send_data_to_ip(args.target_ip, args.port)
    if success:
        print("操作完成，数据已发送")
    else:
        print("操作失败，未能发送数据")
        exit(1)

if __name__ == "__main__":
    main()
