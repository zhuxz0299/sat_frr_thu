import yaml
import math

# 初始化 Containerlab 的基础结构
lab = {
    "name": "test-topo-network",
    "mgmt": {
        "network": "my_network",
        "ipv4-subnet": "166.166.0.0/16"
    },
    "topology": {
        "nodes": {},
        "links": []
    }
}

# 自定义 Dumper，确保多行列表格式正确
class CustomDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(CustomDumper, self).increase_indent(flow, False)

node_name = "TSN_NOCC"
lab["topology"]["nodes"][node_name] = {
"kind": "linux",
"image": "frrouting/frr:v8.2.2",
"binds": [f"sat_output2/{node_name}/daemons:/etc/frr/daemons"],
"exec": []
}

node_name = "TX_NOCC"
lab["topology"]["nodes"][node_name] = {
"kind": "linux",
"image": "frrouting/frr:v8.2.2",
"binds": [f"sat_output2/{node_name}/daemons:/etc/frr/daemons"],
"exec": []
}

node_name = "YG_NOCC"
lab["topology"]["nodes"][node_name] = {
"kind": "linux",
"image": "frrouting/frr:v8.2.2",
"binds": [f"sat_output2/{node_name}/daemons:/etc/frr/daemons"],
"exec": []
}

# 创建 TSN 节点
for i in range(1, 4):
    node_name = f"TSN{i}"
    lab["topology"]["nodes"][node_name] = {
    "kind": "linux",
    "image": "frrwithpy:v8.2.2",
    "binds": [f"sat_output2/{node_name}/daemons:/etc/frr/daemons"],
    "exec": []
    }

# 创建 DG 节点
for i in range(1, 11):
    node_name = f"DG{i}"
    lab["topology"]["nodes"][node_name] = {
    "kind": "linux",
    "image": "frrwithpy:v8.2.2",
    "binds": [f"sat_output2/{node_name}/daemons:/etc/frr/daemons"],
    "exec": []
    }


# 创建链接：TSN连接形成环形
lab["topology"]["links"].append({ "endpoints": ["TSN1:e1_2", "TSN2:e2_1"] })
lab["topology"]["nodes"]["TSN1"]["exec"].append(f"ip address add 193.168.4.1/24 dev e1_2")
lab["topology"]["nodes"]["TSN2"]["exec"].append(f"ip address add 193.168.4.2/24 dev e2_1")

lab["topology"]["links"].append({ "endpoints": ["TSN2:e2_3", "TSN3:e3_2"] })
lab["topology"]["nodes"]["TSN2"]["exec"].append(f"ip address add 193.168.5.1/24 dev e2_3")
lab["topology"]["nodes"]["TSN3"]["exec"].append(f"ip address add 193.168.5.2/24 dev e3_2")

lab["topology"]["links"].append({ "endpoints": ["TSN3:e3_1", "TSN1:e1_3"] })
lab["topology"]["nodes"]["TSN3"]["exec"].append(f"ip address add 193.168.6.1/24 dev e3_1")
lab["topology"]["nodes"]["TSN1"]["exec"].append(f"ip address add 193.168.6.2/24 dev e1_3")

# 创建链接：TSN与各NOCC相连
lab["topology"]["links"].append({ "endpoints": ["TSN1:e1_YG", "YG_NOCC:eYG_1"] })
lab["topology"]["nodes"]["TSN1"]["exec"].append(f"ip address add 193.168.3.2/24 dev e1_YG")
lab["topology"]["nodes"]["YG_NOCC"]["exec"].append(f"ip address add 193.168.3.1/24 dev eYG_1")

lab["topology"]["links"].append({ "endpoints": ["TSN2:e2_TSN", "TSN_NOCC:eTSN_2"] })
lab["topology"]["nodes"]["TSN2"]["exec"].append(f"ip address add 193.168.1.2/24 dev e2_TSN")
lab["topology"]["nodes"]["TSN_NOCC"]["exec"].append(f"ip address add 193.168.1.1/24 dev eTSN_2")

lab["topology"]["links"].append({ "endpoints": ["TSN3:e3_TX", "TX_NOCC:eTX_3"] })
lab["topology"]["nodes"]["TSN3"]["exec"].append(f"ip address add 193.168.2.2/24 dev e3_TX")
lab["topology"]["nodes"]["TX_NOCC"]["exec"].append(f"ip address add 193.168.2.1/24 dev eTX_3")

# 配置路由
lab["topology"]["nodes"]["TSN1"]["exec"].append("ip route del default")
lab["topology"]["nodes"]["TSN2"]["exec"].append("ip route del default")
lab["topology"]["nodes"]["TSN3"]["exec"].append("ip route del default")
lab["topology"]["nodes"]["YG_NOCC"]["exec"].append("ip route del default")
lab["topology"]["nodes"]["TX_NOCC"]["exec"].append("ip route del default")
lab["topology"]["nodes"]["TSN_NOCC"]["exec"].append("ip route del default")

lab["topology"]["nodes"]["TSN1"]["exec"].append("ip route add default via 193.168.4.2 dev e1_2")
lab["topology"]["nodes"]["TSN2"]["exec"].append("ip route add default via 193.168.5.2 dev e2_3")
lab["topology"]["nodes"]["TSN3"]["exec"].append("ip route add default via 193.168.6.2 dev e3_1")

lab["topology"]["nodes"]["YG_NOCC"]["exec"].append("ip route add default via 193.168.3.2 dev eYG_1")
lab["topology"]["nodes"]["TX_NOCC"]["exec"].append("ip route add default via 193.168.2.2 dev eTX_3")
lab["topology"]["nodes"]["TSN_NOCC"]["exec"].append("ip route add default via 193.168.1.2 dev eTSN_2")

# 将配置保存为 YAML 文件
with open("test-topo-network.clab.yaml", "w") as file:
    yaml.dump(lab, file, Dumper=CustomDumper , default_flow_style=False, sort_keys=False)

print("sat-network.clab.yaml 已生成！")