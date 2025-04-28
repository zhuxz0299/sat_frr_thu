import os
import shutil
import yaml
from yaml.representer import SafeRepresenter
# 初始化 Containerlab 的基础结构
lab = {
    "name": "sat-network",
    "mgmt": {
        "network": "my_network",
        "ipv4-subnet": "192.0.0.0/2"
    },
    "topology": {
        "nodes": {},
        "links": []
    }
}

# 添加这些导入和定义到你的代码顶部
class FoldedScalarWithDash(str):
    pass


# 自定义 Dumper，确保多行列表格式正确
class CustomDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(CustomDumper, self).increase_indent(flow, False)
# 将表示器添加到你的自定义Dumper

def str_presenter(dumper, data):
    if '\n' in data:
        # 分割字符串为行，过滤掉空行，然后重新合并
        lines = [line for line in data.splitlines() if line.strip()]
        clean_data = '\n'.join(lines)
        return dumper.represent_scalar('tag:yaml.org,2002:str', clean_data, style='>')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

CustomDumper.add_representer(str, str_presenter)

# 参数检查
def validate_params(server_id, num_meo, leo_groups, leo_ports):
    if server_id <= 0 or server_id > 15:
        raise ValueError("服务器序号必须在 1 到 15 之间")
    if num_meo <= 0 or num_meo > 99:
        raise ValueError("MEO 数量必须在 1 到 99 之间")
    if any(leo_count <= 0 or leo_count > 50 for leo_count in leo_groups):
        raise ValueError("每个 MEO 内的 LEO 数量必须在 1 到 50 之间")
    if leo_ports <= 0 or leo_ports > 5:
        raise ValueError("LEO 的端口数必须在 1 到 5 之间")


# 节点类型的通用逻辑
def create_nodes(server_id, num_meo, leo_groups, leo_ports, subnet):
    # 使用空格而不是换行符连接命令行
    ospf_config = """vtysh -c 'conf t'
-c 'router ospf'
-c 'network 192.0.0.0/2 area 0'
-c 'exit'
-c 'exit'
-c 'write'
-c '!'"""


    # 创建GROUND节点
    lab["topology"]["nodes"]["GROUND"] = {
            "kind": "linux",
            "image": "frrouting/frr:v8.2.2",
            "binds": ["sat_output/GROUND1/daemons:/etc/frr/daemons"],
            "exec": []
        }
    for meo_id in range(1, num_meo + 1):
        # 计算地面站向MEO连接的端口ip地址
        ip = f"{192+server_id}.200.0.{meo_id}/{subnet}"
        lab["topology"]["nodes"]["GROUND"]["exec"].append(f"ip address add {ip} dev e{meo_id}")
        # 打印创建的节点信息
        print(f"Created GROUND node with IP {ip}")
    lab["topology"]["nodes"]["GROUND"]["exec"].append(ospf_config)


    # 创建 MEO 节点
    for meo_id in range(1, num_meo + 1):
        node_name = f"MEO{meo_id}"
        # 先计算MEO与地面站的连接端口ip地址
        ground_ip = f"{192+server_id}.{100+meo_id}.0.254/{subnet}"
        lab["topology"]["nodes"][node_name] = {
            "kind": "linux",
            "image": "frrouting/frr:v8.2.2",
            "binds": [f"sat_output/{node_name}/daemons:/etc/frr/daemons"],
            "exec": [f"ip address add {ground_ip} dev e{meo_id}"]
        }
        # 计算MEO节点与其星座内所有LEO端口互联的接口ip地址
        for leo_id in range(1, leo_groups[meo_id - 1] + 1):
             for port_id in range(1, leo_ports + 1):
                # 计算 IP 地址
                ip = f"{192+server_id}.{100+meo_id}.0.{(leo_id-1)*leo_ports+port_id}/{subnet}"
                lab["topology"]["nodes"][node_name]["exec"].append(f"ip address add {ip} dev e{leo_id}_{port_id}")
                # 打印创建的节点信息
                print(f"Created MEO node: {node_name} with IP {ip}")
        
        lab["topology"]["nodes"][node_name]["exec"].append(ospf_config)
    # 创建 LEO 节点
    for meo_id, leo_count in enumerate(leo_groups, start=1):
        for leo_id in range(1, leo_count + 1):
            node_name = f"LEO{meo_id}_{leo_id}"
            lab["topology"]["nodes"][node_name] = {
                "kind": "linux",
                "image": "frrouting/frr:v8.2.2",
                "binds": [f"sat_output/{node_name}/daemons:/etc/frr/daemons"],
                "exec": []
            }
            for port_id in range(1, leo_ports + 1):
                ip = f"{192+server_id}.{100+meo_id}.{leo_id}.{port_id}/{subnet}"
                lab["topology"]["nodes"][node_name]["exec"].append(f"ip address add {ip} dev e{leo_id}_{port_id}")
                print(f"Created LEO node: {node_name} with IP {ip}")
            lab["topology"]["nodes"][node_name]["exec"].append(ospf_config)


# 创建 MEO 和 LEO 之间的链接
def create_links(num_meo, leo_groups, leo_ports):

    for meo_id in range(1, num_meo + 1):
        for leo_id in range(1, leo_groups[meo_id - 1] + 1):
            for port_id in range(1, leo_ports + 1):
                lab["topology"]["links"].append({
                    "endpoints": [f"MEO{meo_id}:e{leo_id}_{port_id}", f"LEO{meo_id}_{leo_id}:e{leo_id}_{port_id}"]
                })

    # 为 GROUND 创建与 MEO 的链接
    for meo_id in range(1, num_meo + 1):
        lab["topology"]["links"].append({
            "endpoints": [f"GROUND:e{meo_id}", f"MEO{meo_id}:e{meo_id}"]
        })

    print(f"Created {len(lab['topology']['links'])} links.")


# 创建目标文件夹并复制文件
def create_and_copy(source_path, output_dir, prefix, count):
    for i in range(1, count + 1):
        # 创建目标文件夹路径
        target_dir = os.path.join(output_dir, f"{prefix}{i}")
        os.makedirs(target_dir, exist_ok=True)
        try:
            # 复制文件到目标文件夹
            target_file = os.path.join(target_dir, "daemons")
            shutil.copy(source_path, target_file)
            print(f"成功复制到 {target_dir}")
        except Exception as e:
            print(f"错误: 无法复制到 {target_dir} - {e}")


# 修改 main 函数，接收自定义输入
def main():
    # 接收用户输入参数
    server_id = int(input("请输入服务器序号 (1-15): "))
    num_meo = int(input("请输入 MEO 节点的数量 (1-99): "))
    

    # 接收每个 MEO 的 LEO 分组数量
    print(f"请输入每个 MEO 的 LEO 节点数量（1-50）:")
    leo_groups = []
    for i in range(1, num_meo + 1):
        group_size = int(input(f"  MEO{i} 的 LEO 节点数量: "))
        leo_groups.append(group_size)
        
    leo_ports = int(input("请输入每个 LEO 节点的端口数 (1-5): "))
    # 参数检查
    validate_params(server_id, num_meo, leo_groups, leo_ports)

    # 原始 daemons 文件所在的路径
    source_daemons_path = "./router/daemons"

    # 检查原始 daemons 文件是否存在
    if not os.path.exists(source_daemons_path):
        print(f"错误: 找不到文件 {source_daemons_path}")
        exit(1)

    # 输出的目标文件夹路径
    output_base_dir = "./sat_output"

    # 创建根输出文件夹
    os.makedirs(output_base_dir, exist_ok=True)

    # 创建节点
    create_nodes(server_id, num_meo, leo_groups, leo_ports,2)

    # 创建链接
    create_links(num_meo, leo_groups, leo_ports)

    # 创建MEO文件夹并复制文件
    create_and_copy(source_daemons_path, output_base_dir, "MEO", num_meo)
    # 创建LEO文件夹并复制文件
    for meo_id, leo_count in enumerate(leo_groups, start=1):
        create_and_copy(source_daemons_path, output_base_dir, f"LEO{meo_id}_", leo_count)
    # 创建 GROUND 的文件夹并复制文件
    create_and_copy(source_daemons_path, output_base_dir, "GROUND", 1)
    # 将配置保存为 YAML 文件
    with open("sat-network.clab.yaml", "w") as file:
        yaml.dump(lab, file, Dumper=CustomDumper, default_flow_style=False, sort_keys=False)

    print("sat-network.clab.yaml 已生成！")


# 执行主函数
if __name__ == "__main__":
    main()
