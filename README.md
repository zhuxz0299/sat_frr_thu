# 说明
## 仓库结构
### frr
#### dynamic_frr
包含所有和frr网络控制相关代码
- clab-sat-network clab配置frr网络自动生成
- csv_tsn/tsn_modify/xw 可见性矩阵及TSN分域表，modify为处理后TSN分域，每个卫星同时只属于一个TSN域
- router 生成frr初始网络时需要复制的配置，无其他作用
- sat_output 由router复制而来，每个frr容器配置一份
- csv_modify_tsn.py 读取csv_tsn里的分域，修改后传输到csv_tsn_modify中
- dynamic_frr_tsn_scan_multi_thread.py 读取csv_tsn_modify目录下的TSN分域表，动态建立每个时间片下TSN与XW、YG之间的frr链路，并在建链后以多线程的方式，让每个TSN对应VM扫描当前与其建立连接的XW/YG对应VM,收集资源状态文件传回TSN VM
- dynamic_frr_tsn_undo.py 用于测试时复原frr链路到初始化状态。如果读到某个时间片csv程序终止，执行该代码传入对应csv路径，将删除在该时间片下frr建立的所有veth-pair连接，方便重新测试
- dynamic_frr_xw.py 读取csv_xw下的xw可见性矩阵，动态增删改frr链路，实现xw间网络动态拓扑控制
- excel_to_csv.py 将xlsx格式文件转换为csv文件
- generate_initial_topo.py clab在启动frr容器时需要读取一个预定义拓扑的yaml文件，该代码用于生成此yaml文件，初始化拓扑指定TSN/XW/YG个数，并在TSN中建立环形链路，其他容器间不做任何链路连接，由后续dynamic_frr_xw.py/dynamic_frr_tsn_scan_multi_thread.py根据可见性动态建链
- sat-initial-network.clab.yaml 此文件即为generate_initial_topo.py执行后生成的yaml文件，要启动该yaml中指定的frr容器网络拓扑，执行 clab deploy -t sat-initial-network.clab.yaml即可，删除所有容器执行clab destroy -t sat-initial-network.clab.yaml，删除和创建时的yaml要保持一致
#### frr_generator/frr_tsn_circle/test
为初期开发generate_initial_topo.py时的测试版本，所有功能已经集成到上述代码中，暂时无用
### image
由于体积过大没有上传repo，内部存有用于启动vm的麒麟os镜像，以及存放克隆vm的qcow2文件

### resource_manager
需要部署在vm中的所有资源纳管脚本，该目录下的所有脚本，可由sh文件夹下的auto_update_resource_manager.exp脚本自动传输到系统中的vm1-vm44虚拟机指定目录中，方便后续继续更新脚本。

- status_sender_activate.sh 主动响应式资源纳管脚本，接收来自tsn的资源请求后，自动读取一次资源状态，生成为yaml文件回传给tsn
- status_sender.sh 周期性主动更新资源纳管脚本，按设定周期主动读取本机资源状态并更新资源yaml，但不向外传输

### sh
存储一系列自动控制脚本，包括在虚拟机中运行的资源纳管脚本，以及在宿主机中运行的虚拟机自动化控制脚本

- auto_update_resource_manager.exp 自动将resource_manager文件夹下的所有文件传输到所有虚拟机的/home/resource_manager目录下，实现所有vm更新资源纳管脚本的自动化
- resource_request.sh 用于tsn vm向与其连接的XW/YG vm请求资源状态yaml文件，需指定目标XW/YG vm的ip地址，然后远程ssh触发对方vm中的status_sender_activate.sh，做一次资源纳管并回传
- status_sender_activate.sh 同上，主动响应式资源纳管脚本，接收来自tsn的资源请求后，自动读取一次资源状态，生成为yaml文件回传给tsn
- status_sender.sh 同上，周期性主动更新资源纳管脚本，按设定周期主动读取本机资源状态并更新资源yaml，但不向外传输
- tsn_scan_test.exp 测试单台tsn vm向其他已连接vm请求资源状态文件是否正常
- vm_clone.sh 自动批量克隆虚拟机
- vm_delete.sh 自动批量删除虚拟机
- vm_start.sh 自动批量启动虚拟机
  
### vm
目前用于存放控制frr和vm之间veth-pair连接的自动化工具，除sh外，其他为输出日志和临时xml文件

- auto_vm_frr_veth.sh 自动建立frr容器和其对应vm之间的veth-pair连接

## 启动流程

1. 环境创建

- 初始vm环境配置：创建一个模板origin_vm，用于后续批量克隆。创建/home/resource_manager 和 /home/resource_manager/resource_info 两级目录，/home/resource_manager下存放资源纳管脚本resource_request.sh/status_sender.sh/status_sender_activate.sh,/home/resource_manager/resource_info目录下用于存放后续脚本执行生成的yaml资源状态文件。同时安装sshpass工具，用于自动化远程ssh控制。

- 批量克隆vm：执行vm_clone脚本，用于克隆所需数量的vm，执行前自行修改脚本内的参数。克隆后默认是关机状态，使用vm_start.sh脚本自动启动所有vm。

- 创建frr配置yaml：执行generate_initial_topo.py，输入总数和vm数量相等的tsn、xw、yg数，该文件会生成一份sat-initial-network.clab.yaml，该文件中定义了初始状态的frr容器集群配置。

- 使用clab创建frr容器集群：执行clab deploy -t sat-initial-network.clab.yaml，clab会根据之前生成的yaml配置自动创建出frr容器，并建立预定义的链路（tsn环状链路）。

- 建立vm和frr之间的veth-pair连接：在所有vm和frr都正常启动后，需要建立每个vm和frr之间的一对一veth-pair连接，使frr充当对应vm的router，将vm发出的流量路由到目标vm。修改/vm/auto_vm_frr_veth.sh开头的vm-frr对应关系列表,以root身份启动该脚本即可自动建立连接。