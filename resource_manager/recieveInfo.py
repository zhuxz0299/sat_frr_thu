import socket
import json
import yaml
import os
from pathlib import Path
import concurrent.futures
import threading

# 配置服务器参数
HOST = '0.0.0.0'  # 监听所有网络接口
PORT = 12345      # 指定端口号
BUFFER_SIZE = 8192  # 接收缓冲区大小
SAVE_DIR = '/home/zmx/875/resource_manager/resource_info'  # 保存目录
MAX_CONCURRENT_REQUESTS = 20  # 最大并发处理请求数

# 确保保存目录存在
Path(SAVE_DIR).mkdir(parents=True, exist_ok=True)

# 创建线程池，限制最大并发数为20
executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)

# 状态信息的锁
print_lock = threading.Lock()

def process_data(data, sender_addr):
    """处理收到的数据并保存为YAML文件"""
    try:
        # 解析JSON数据
        json_data = json.loads(data.decode('utf-8'))
        
        # 获取satID字段作为文件名
        sat_id = json_data.get('satID')
        if not sat_id:
            with print_lock:
                print(f"错误：来自 {sender_addr} 的数据中没有satID字段")
            return
        
        # 将JSON转换回YAML格式
        yaml_data = yaml.dump(json_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        # 构建保存路径
        save_path = os.path.join(SAVE_DIR, f"{sat_id}.yaml")
        
        # 保存YAML文件
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(yaml_data)
        
        with print_lock:
            print(f"已处理来自 {sender_addr} 的数据，保存为 {save_path}")
            
    except json.JSONDecodeError as e:
        with print_lock:
            print(f"JSON解析错误 (来自 {sender_addr}): {e}")
    except Exception as e:
        with print_lock:
            print(f"处理数据错误 (来自 {sender_addr}): {e}")

def start_server():
    """启动UDP服务器，使用线程池处理请求"""
    # 创建UDP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 设置socket选项
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # 绑定地址和端口
        server_socket.bind((HOST, PORT))
        print(f"UDP服务器启动，监听 {HOST}:{PORT}")
        print(f"最大并发处理数: {MAX_CONCURRENT_REQUESTS}")
        
        while True:
            # 接收数据
            data, sender_addr = server_socket.recvfrom(BUFFER_SIZE)
            
            # 提交到线程池处理
            with print_lock:
                active_count = threading.active_count()
                queue_size = executor._work_queue.qsize()
                print(f"收到来自 {sender_addr} 的数据。当前活动线程: {active_count}, 队列中任务: {queue_size}")
            
            executor.submit(process_data, data, sender_addr)
            
    except KeyboardInterrupt:
        print("接收到中断信号，服务器关闭中...")
    except Exception as e:
        print(f"服务器错误: {e}")
    finally:
        server_socket.close()
        executor.shutdown(wait=False)
        print("服务器已关闭")

if __name__ == "__main__":
    start_server()
