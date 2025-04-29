#!/usr/bin/expect

# 定义变量
set vm_container_list {
    {vm1 clab-sat-network-TSN1} 
    {vm2 clab-sat-network-TSN2}
    {vm3 clab-sat-network-TSN3}
    {vm4 clab-sat-network-TSN4}
    {vm5 clab-sat-network-TSN5}
    {vm6 clab-sat-network-TSN6}
    {vm7 clab-sat-network-TSN7}
    {vm8 clab-sat-network-TSN8}
    {vm9 clab-sat-network-YG1}
    {vm10 clab-sat-network-YG2}
    {vm11 clab-sat-network-YG3}
    {vm12 clab-sat-network-YG4}
    {vm13 clab-sat-network-YG5}
    {vm14 clab-sat-network-YG6}
    {vm15 clab-sat-network-YG7}
    {vm16 clab-sat-network-YG8}
    {vm17 clab-sat-network-YG9}
    {vm18 clab-sat-network-YG10}
    {vm19 clab-sat-network-YG11}
    {vm20 clab-sat-network-YG12}
    {vm21 clab-sat-network-XW1}
    {vm22 clab-sat-network-XW2}
    {vm23 clab-sat-network-XW3}
    {vm24 clab-sat-network-XW4}
    {vm25 clab-sat-network-XW5}
    {vm26 clab-sat-network-XW6}
    {vm27 clab-sat-network-XW7}
    {vm28 clab-sat-network-XW8}
    {vm29 clab-sat-network-XW9}
    {vm30 clab-sat-network-XW10}
    {vm31 clab-sat-network-XW11}
    {vm32 clab-sat-network-XW12}
    {vm33 clab-sat-network-XW13}
    {vm34 clab-sat-network-XW14}
    {vm35 clab-sat-network-XW15}
    {vm36 clab-sat-network-XW16}
    {vm37 clab-sat-network-XW17}
    {vm38 clab-sat-network-XW18}
    {vm39 clab-sat-network-XW19}
    {vm40 clab-sat-network-XW20}
    {vm41 clab-sat-network-XW21}
    {vm42 clab-sat-network-XW22}
    {vm43 clab-sat-network-XW23}
    {vm44 clab-sat-network-XW24}
}
set index 0
set user "root"
set psw "zmx"
set user_vm "root"
set psw_vm "passw0rd@123"
set eth "ens2"
set xml_file "/home/zmx/875/vm/temp_config.xml"
# 遍历每一对 VM 和容器
foreach pair $vm_container_list {
    # 获取当前 VM 和容器名
    set vm_name [lindex $pair 0]
    set container_name [lindex $pair 1]

    # Step 1: 创建 veth 对
    set veth_vm "veth-$vm_name"
    set container_suffix [regsub {.*-} $container_name ""]
    set veth_cont "veth-cont$container_suffix"
    sleep 1
    spawn sudo ip link add $veth_vm type veth peer name $veth_cont
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof

    # Step 2: 获取容器 PID 并将 veth-cont 移动到容器命名空间
    sleep 1
    spawn sudo docker inspect -f '{{.State.Pid}}' $container_name
    # expect "password for $user:"
    # send "$psw\r"
    expect -re {(\d+)}
    set container_pid $expect_out(1,string)
    sleep 1
    spawn sudo ip link set $veth_cont netns $container_pid
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof

    # Step 3: 在容器命名空间中启用并配置 veth-cont
    sleep 1
    spawn sudo nsenter -t $container_pid -n ip link set $veth_cont up
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof
    set ip_suffix_cont [expr {$index * 4 + 1}]
    set ip_address_cont "10.0.64.$ip_suffix_cont"
    sleep 1
    spawn sudo nsenter -t $container_pid -n ip addr add ${ip_address_cont}/30 dev $veth_cont
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof

    # Step 4: 启用 veth-vm
    sleep 1
    spawn sudo ip link set $veth_vm up
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof

    # Step 5: 修改虚拟机的网络配置文件
    set ip_suffix_vm [expr {$index * 4 + 2}]
    set ip_address_vm "10.0.64.$ip_suffix_vm"
    sleep 1
    spawn sudo virsh console $vm_name
    # expect "password for $user:"
    # send "$psw\r"

    sleep 1
    send "\r"

    expect "localhost login:"
    send "$user_vm\r"
    expect "Password:"
    send "$psw_vm\r"

    expect "# "
    send "echo 'TYPE=Ethernet' > /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'DEVICE=$eth' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'ONBOOT=yes' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'BOOTPROTO=static' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'IPADDR=${ip_address_vm}' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'NETMASK=255.255.255.252' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "echo 'GATEWAY=${ip_address_cont}' >> /etc/sysconfig/network-scripts/ifcfg-$eth\r"
    expect "# "
    send "exit\r"

    # Step 6: 编辑虚拟机的 XML 配置文件
    
    set new_interface "<interface type='direct'>\\n      <source dev='$veth_vm' mode='bridge'/>\\n      <model type='virtio'/>\\n    </interface>"
    
    sleep 1
    spawn sudo virsh shutdown $vm_name
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof
    sleep 1

    spawn virsh net-destroy default
    spawn virsh net-autostart default --disable
    
    spawn bash -c "sudo virsh dumpxml $vm_name > $xml_file"
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof
    
    sleep 1
    spawn bash
    set cmd "perl -i -0777pe \"s|<interface.*interface>|$new_interface|sg\" $xml_file"
    #puts $cmd
    send "$cmd\n"
    expect eof

    sleep 1
    spawn sudo virsh undefine $vm_name 
    # expect "password for $user:"
    # send "$psw\r"

    sleep 1
    spawn sudo virsh define $xml_file
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof
    
    # Step 7: 重启虚拟机
    sleep 1
    spawn sudo virsh start $vm_name
    # expect "password for $user:"
    # send "$psw\r"
    # expect eof
    incr index

}

puts "All VM and container connections have been established."