# 卫星网络仿真系统说明

本项目是一个基于FRR(Free Range Routing)和ContainerLab的卫星网络仿真系统，支持TSN(低轨)、XW(中轨)、YG(高轨)三种类型卫星的动态网络拓扑管理和资源监控。

## 仓库结构

### 根目录文件
- `.gitignore` Git忽略文件配置
- `README.md` 项目说明文档
### frr
包含所有和frr网络控制相关代码
- `clab-sat-network` clab配置frr网络自动生成
  - `ansible-inventory.yml` Ansible清单配置文件
  - `authorized_keys` SSH密钥文件
  - `topology-data.json` 网络拓扑数据文件
  - `.tls/ca/` TLS证书目录，包含ca.key和ca.pem证书文件
- `clab-sat-xw-network` XW网络的clab配置
  - 结构同上，包含对应的TLS证书和配置文件
- `csv_tsn/tsn_modify/xw` 可见性矩阵及TSN分域表，modify为处理后TSN分域，每个卫星同时只属于一个TSN域
- `router` 生成frr初始网络时需要复制的配置，无其他作用
- `sat_output` 由 `router` 复制而来，每个frr容器配置一份
- `csv_modify_tsn.py` 读取 `csv_tsn` 里的分域，修改后传输到 `csv_tsn_modify` 中
- `dynamic_frr_tsn_scan_multi_thread.py` 读取 `csv_tsn_modify` 目录下的TSN分域表，动态建立每个时间片下TSN与XW、YG之间的frr链路，并在建链后以多线程的方式，让每个TSN对应VM扫描当前与其建立连接的XW/YG对应VM,收集资源状态文件传回TSN VM
- `dynamic_frr_tsn_undo.py` 用于测试时复原frr链路到初始化状态。如果读到某个时间片csv程序终止，执行该代码传入对应csv路径，将删除在该时间片下frr建立的所有veth-pair连接，方便重新测试
- `dynamic_frr_xw.py` 读取csv_xw下的xw可见性矩阵，动态增删改frr链路，实现xw间网络动态拓扑控制
- `excel_to_csv.py` 将xlsx格式文件转换为csv文件
- `frr_network_builder.py`: 实现了 `dynamic_frr_tsn_scan_multi_thread.py` 中构建 frr 网络的功能，并且加入了生成分域表写入 tsn 的功能
- `generate_initial_topo.py` clab在启动frr容器时需要读取一个预定义拓扑的yaml文件，该代码用于生成此yaml文件，初始化拓扑指定TSN/XW/YG个数，并在TSN中建立环形链路，其他容器间不做任何链路连接，由后续dynamic_frr_xw.py/dynamic_frr_tsn_scan_multi_thread.py根据可见性动态建链
- `sat-initial-network.clab.yaml` 此文件即为generate_initial_topo.py执行后生成的yaml文件，要启动该yaml中指定的frr容器网络拓扑，执行 clab deploy -t sat-initial-network.clab.yaml即可，删除所有容器执行clab destroy -t sat-initial-network.clab.yaml，删除和创建时的yaml要保持一致
- `sat-initial-network.clab.yaml.bak` 初始网络配置文件的备份
- `start_nocc_udp_receiver.py` 启动NOCC UDP接收器，用于接收来自TSN的资源信息
- `tsn_scanner.py`：实现了 `dynamic_frr_tsn_scan_multi_thread.py` 中让 tsn 扫描低轨卫星的功能，tsn 之后会将低轨卫星上的信息传给 nocc。 

### image
由于体积过大没有上传repo，内部存有用于启动vm的麒麟os镜像，以及存放克隆vm的qcow2文件

### resource_manager
需要部署在vm中的所有资源纳管脚本，该目录下的所有脚本，可由 `script/data_synchro` 文件夹下的 `auto_update_resource_manager.exp` 脚本或者 `parallel_vm_update.sh` 脚本自动传输到系统中的vm1-vm44虚拟机指定目录中，方便后续继续更新脚本。

- `resource_request.sh` 用于tsn vm向与其连接的XW/YG vm请求资源状态yaml文件，需指定目标XW/YG vm的ip地址，然后远程ssh触发对方vm中的 `status_sender_activate.sh`，做一次资源纳管并回传
- `status_sender_activate.sh` 主动响应式资源纳管脚本，接收来自tsn的资源请求后，自动读取一次资源状态，生成为yaml文件回传给tsn
  - 目前使用了 UDP 传输数据
- `status_sender.sh` 主动更新资源纳管脚本，其他功能与 `status_sender_activate.sh` 相同。
  - 保持 SSH 数据传输
- `template.yaml` 资源状态YAML文件模板，定义了虚拟机资源信息的标准格式
- `udp_receive.sh` 开放某个端口，不断读取 udp 端口接收到的信息，并且将信息写入 `/home/resource_manager/resource_info` 文件夹中
- `udp_send.sh` 将某个文件使用 udp 发送走

### script
存储一系列自动控制脚本，包括在宿主机中运行的虚拟机自动化控制脚本，虚拟机与宿主机之间数据传输脚本，以及资源处理脚本。

#### auto_run
自动运行相关脚本：
- `mod_and_send_yml.py` YAML配置修改和发送工具
- `send_constellation_json.py` 星座配置JSON发送脚本

#### data_synchro
数据同步脚本：
- `auto_update_resource_manager.exp` 自动将`resource_manager`文件夹下的所有文件传输到所有虚拟机的`/home/resource_manager`目录下，实现所有vm更新资源纳管脚本的自动化
- `copy_resource_info.exp` 用于将 nocc 虚拟机中 `/home/resource_manager/resource_info` 文件夹下的文件复制到宿主机中
- `parallel_vm_update.sh` `auto_update_resource_manager.exp` 的并行化版本

#### docker_forward
Docker 转发工具：
- `docker_forward.py` Docker 端口转发工具
  - 放在 docker 中后台运行
  - 使用 http 接收数据，并且使用 scp 将数据转发至对应虚拟机
  - 在 frr docker 中运行该程序的时候，需要指定虚拟机在 frr 网络中的 ip 地址
- `host_to_docker.py` 主机到 Docker 的网络转发
  - 需要制定转发的文件夹路径，以及 Docker 的 ip 地址。
  - 使用 http 发送数据

#### resource_process
资源处理工具：
- `constellation_analyzer.py` 分析资源视图中包含的卫星种类以及资源种类
- `constellation_resource_analyzer.py` 分析资源视图中包含的资源种类
  - 可以指定某种特定资源类型，包括：`cpu, gpu, memory, disk, gpu_mem, link, sensor, all`，默认为 `all`
  - 可以指定资源视图路径，即 `-f <path_to_json>`
- `field_exam.py` 检查 `.yaml` 文件以及资源视图 `.json` 文件的字段值是否相同
  - 支持两个文件进行校验；也支持一个包含若干 `.yaml` 文件的文件夹与一个 `.json` 文件视图进行校验
- `resource_info_gathering.py` 将宿主机收集到的 `.yaml` 文件构建为前端需要的 `.json` 资源视图
  - 支持单个文件的构建，也支持整个文件夹的构建
- `resource_info_gathering_20.py` 用于提供清华方面需要的特定场景的资源视图，基本功能和原版类似
- `yaml_pre_modify.py` YAML文件预处理修改工具
  - 利用 `.csv` 中的信息构建链路
  - 利用 `task_completion.json` 的信息调整 `gpuUsage` 以及加入 `sensor` 字段
  - 自动利用 ip 解析得到 `sat_id` 以及 `sat_name`

#### vm
虚拟机管理脚本：
- `auto_exit_vm.exp` 将8个tsn对应的虚拟机退出登录
- `vm_clone.sh` 自动批量克隆虚拟机
- `vm_delete.sh` 自动批量删除虚拟机
- `vm_start.sh` 自动批量启动虚拟机
  
### vm
目前用于存放控制frr和vm之间veth-pair连接的自动化工具，除sh外，其他为输出日志和临时xml文件

- `auto_vm_frr_veth.sh` 自动建立frr容器和其对应vm之间的veth-pair连接
- `out.log` 输出日志文件
- `temp_config.xml` 临时XML配置文件

### resource_info
存储星座配置信息和虚拟机资源状态文件

#### 星座配置文件
- `tsn_constellation.json` TSN星座资源视图
- `xw_constellation.json` XW星座资源视图
- `yg_constellation.json` YG星座资源视图

#### 虚拟机状态文件
- `vm45/` 虚拟机45的节点状态文件，包含多个node-status-IP地址.yaml文件
- `vm46/` 虚拟机46的节点状态文件
- `vm47/` 虚拟机47的节点状态文件

### temp
临时文件存储目录

- `complete_task.json` 完成任务记录文件
- `nocc_send_test.exp` NOCC发送测试脚本
- `tsn_scan_test.exp` TSN扫描测试脚本
- `yaml_generator.py` YAML配置生成器

### log
日志文件存储目录

- `vm_update_logs/` 虚拟机更新日志存储目录

## 启动流程

1. 环境创建

- 初始vm环境配置：创建一个模板origin_vm，用于后续批量克隆。创建/home/resource_manager 和 /home/resource_manager/resource_info 两级目录，/home/resource_manager下存放资源纳管脚本resource_request.sh/status_sender.sh/status_sender_activate.sh,/home/resource_manager/resource_info目录下用于存放后续脚本执行生成的yaml资源状态文件。同时安装sshpass工具，用于自动化远程ssh控制。

- 批量克隆vm：执行`script/vm/vm_clone.sh`脚本，用于克隆所需数量的vm，执行前自行修改脚本内的参数。克隆后默认是关机状态，使用`script/vm/vm_start.sh`脚本自动启动所有vm。

- 创建frr配置yaml：执行generate_initial_topo.py，输入总数和vm数量相等的tsn、xw、yg数，该文件会生成一份sat-initial-network.clab.yaml，该文件中定义了初始状态的frr容器集群配置。

- 使用clab创建frr容器集群：执行clab deploy -t sat-initial-network.clab.yaml，clab会根据之前生成的yaml配置自动创建出frr容器，并建立预定义的链路（tsn环状链路）。

- 建立vm和frr之间的veth-pair连接：在所有vm和frr都正常启动后，需要建立每个vm和frr之间的一对一veth-pair连接，使frr充当对应vm的router，将vm发出的流量路由到目标vm。修改/vm/auto_vm_frr_veth.sh开头的vm-frr对应关系列表,以root身份启动该脚本即可自动建立连接。