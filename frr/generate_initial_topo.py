import os
import shutil
import yaml
from yaml.representer import SafeRepresenter
# 初始化 Containerlab 的基础结构
lab = {
    "name": "sat-network",
    "mgmt": {
        "network": "sat_network",
        "ipv4-subnet": "166.167.0.0/16"
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
def validate_params(num_xw):
    if num_xw <= 0 or num_xw > 99:
        raise ValueError("单星网内卫星数量必须在 1 到 99 之间")


# 节点类型的通用逻辑
def create_xw_nodes(num_xw):
    # 使用空格而不是换行符连接命令行
    ospf_config = """vtysh -c 'conf t'
-c 'router ospf'
-c 'network 10.0.0.0/16 area 0'
-c 'exit'
-c 'exit'
-c 'write'
-c '!'"""


    # 创建 XW 节点
    for xw_id in range(1, num_xw + 1):
        node_name = f"XW{xw_id}"
        # 先计算xw与地面站的连接端口ip地址
        lab["topology"]["nodes"][node_name] = {
            "kind": "linux",
            "image": "frrouting/frr:v8.2.2",
            "binds": [f"sat_output/{node_name}/daemons:/etc/frr/daemons"],
            "exec": []
            
        }

        # 打印创建的节点信息
        print(f"Created initial XW node: {node_name}")
        lab["topology"]["nodes"][node_name]["exec"].append('mkdir -p /etc/frr')
        lab["topology"]["nodes"][node_name]["exec"].append('touch /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('echo "service integrated-vtysh-config" > /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('sleep 1')
        lab["topology"]["nodes"][node_name]["exec"].append(ospf_config)

def create_yg_nodes(num_yg):
    ospf_config = """vtysh -c 'conf t'
-c 'router ospf'
-c 'network 10.0.0.0/16 area 0'
-c 'exit'
-c 'exit'
-c 'write'
-c '!'"""
    # 创建 YG 节点
    for yg_id in range(1, num_yg + 1):
        node_name = f"YG{yg_id}"
        lab["topology"]["nodes"][node_name] = {
            "kind": "linux",
            "image": "frrouting/frr:v8.2.2",
            "binds": [f"sat_output/{node_name}/daemons:/etc/frr/daemons"],
            "exec": []
        }
        # 打印创建的节点信息
        print(f"Created initial YG node: {node_name}")
        lab["topology"]["nodes"][node_name]["exec"].append('mkdir -p /etc/frr')
        lab["topology"]["nodes"][node_name]["exec"].append('touch /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('echo "service integrated-vtysh-config" > /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('sleep 1')
        lab["topology"]["nodes"][node_name]["exec"].append(ospf_config)

def create_tsn_nodes(num_tsn):
    ospf_config = """vtysh -c 'conf t'
-c 'router ospf'
-c 'network 10.0.0.0/16 area 0'
-c 'exit'
-c 'exit'
-c 'write'
-c '!'"""
    # 创建 TSN 节点
    for tsn_id in range(1, num_tsn + 1):
        node_name = f"TSN{tsn_id}"
        lab["topology"]["nodes"][node_name] = {
            "kind": "linux",
            "image": "frrouting/frr:v8.2.2",
            "binds": [f"sat_output/{node_name}/daemons:/etc/frr/daemons"],
            "exec": []
        }
        # 打印创建的节点信息
        print(f"Created initial TSN node: {node_name}")
        lab["topology"]["nodes"][node_name]["exec"].append('mkdir -p /etc/frr')
        lab["topology"]["nodes"][node_name]["exec"].append('touch /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('echo "service integrated-vtysh-config" > /etc/frr/vtysh.conf')
        lab["topology"]["nodes"][node_name]["exec"].append('sleep 1')

        previous_node = tsn_id - 1 if tsn_id > 1 else num_tsn
        next_node = tsn_id + 1 if tsn_id < num_tsn else 1
        
        # 创建tsn环形链路veth及对应ip
        lab["topology"]["nodes"][node_name]["exec"].append(f"ip address add 10.0.{100+tsn_id}.2/30 dev tsn{tsn_id}-tsn{previous_node}")
        lab["topology"]["nodes"][node_name]["exec"].append(f"ip address add 10.0.{100+next_node}.1/30 dev tsn{tsn_id}-tsn{next_node}")

        lab["topology"]["nodes"][node_name]["exec"].append(ospf_config)

        


def create_tsn_links(num_tsn):
    # 创建TSN环形链路,其他链路根据时间片动态创建
    for tsn_id in range(1, num_tsn + 1):
        next_node = tsn_id + 1 if tsn_id < num_tsn else 1
        lab["topology"]["links"].append({
            "endpoints": [f"TSN{tsn_id}:tsn{tsn_id}-tsn{next_node}", f"TSN{next_node}:tsn{next_node}-tsn{tsn_id}"]
        })

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
    num_xw = int(input("请输入星网节点的数量 (1-99): "))
    num_yg = int(input("请输入遥感节点的数量 (1-99): "))
    num_tsn = int(input("请输入TSN节点的数量 (1-99): "))
    # 参数检查
    validate_params(num_xw)

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
    create_xw_nodes(num_xw)
    create_yg_nodes(num_yg)
    create_tsn_nodes(num_tsn)
    create_tsn_links(num_tsn)
    # 创建XW文件夹并复制文件
    create_and_copy(source_daemons_path, output_base_dir, "XW", num_xw)
    create_and_copy(source_daemons_path, output_base_dir, "YG", num_yg)
    create_and_copy(source_daemons_path, output_base_dir, "TSN", num_tsn)
    
    # 将配置保存为 YAML 文件
    with open("sat-initial-network.clab.yaml", "w") as file:
        yaml.dump(lab, file, Dumper=CustomDumper, default_flow_style=False, sort_keys=False)

    print("sat-initial-network.clab.yaml 已生成！")


# 执行主函数
if __name__ == "__main__":
    main()
