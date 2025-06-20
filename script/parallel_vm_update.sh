#!/bin/bash
# 这个脚本用于并行执行auto_update_resource_manager.exp

# 配置
BATCH_SIZE=10
VM_COUNT=47
SOURCE_DIR="./resource_manager"
LOG_DIR="./vm_update_logs"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 创建一个总体日志文件
MAIN_LOG="$LOG_DIR/update_summary.log"
echo "开始更新虚拟机 $(date)" > "$MAIN_LOG"

# 创建一个处理单个虚拟机的expect脚本
cat > /tmp/process_single_vm.exp << 'EOL'
#!/usr/bin/expect -f

# 设置超时时间
set timeout 120

# 获取命令行参数
if {$argc != 2} {
    puts "用法: $argv0 <虚拟机名称> <源目录>"
    exit 1
}

set vm_name [lindex $argv 0]
set source_dir [lindex $argv 1]

puts "正在处理虚拟机: $vm_name"

# 获取源目录中的所有文件（不包含子目录）
spawn bash -c "ls -1 $source_dir"
set files ""
expect -re "(.*)\n" {
    append files "[string trim $expect_out(1,string)] "
    exp_continue
} eof {}
set files [string trim $files]

if {$files == ""} {
    puts "源目录中没有文件，跳过此虚拟机"
    exit 0
}

# 检查虚拟机状态
spawn virsh domstate $vm_name
expect {
    "运行中" {
        puts "虚拟机正在运行，正在关闭..."
        spawn virsh shutdown $vm_name
        expect eof
        # 等待虚拟机完全关闭
        set wait_count 0
        set max_wait 300
        while {$wait_count < $max_wait} {
            spawn virsh domstate $vm_name
            expect {
                "关闭" {
                    break
                }
                eof
            }
            incr wait_count
            sleep 2
        }
    }
    "关闭" {
        puts "虚拟机已关闭，继续操作..."
    }
    eof
}

# 逐个传输文件
foreach file [split $files] {
    set full_path "$source_dir/$file"
    puts "传输文件: $full_path 到 $vm_name:/home/resource_manager/"
    spawn virt-copy-in -d $vm_name $full_path /home/resource_manager/
    expect {
        "error:" {
            puts "无法传输文件 $file 到 $vm_name，错误!"
            continue
        }
        eof
    }
}

# 重新启动虚拟机
spawn virsh start $vm_name
expect eof
sleep 5

# 连接到虚拟机控制台
spawn virsh console $vm_name
sleep 2
send "\r"

# 登录到虚拟机
expect {
    "login:" {
        send "root\r"
        expect "密码："
        send "passw0rd@123\r"
    }
    timeout {
        puts "登录超时，跳过此虚拟机"
        exit 1
    }
}

expect "# "

# 对每个传输的文件执行chmod +x
foreach file [split $files] {
    send "chmod +x /home/resource_manager/$file\r"
    expect "# "
    send "ls -la /home/resource_manager/$file\r"
    expect "# "
}

# 退出虚拟机控制台
send "exit\r"
sleep 1
send "exit\r"
sleep 1

puts "完成处理虚拟机: $vm_name"
exit 0
EOL

chmod +x /tmp/process_single_vm.exp

# 按批次处理虚拟机
for ((i=1; i<=$VM_COUNT; i+=$BATCH_SIZE)); do
    pids=()
    
    # 启动一批处理
    end=$((i+BATCH_SIZE-1))
    if [ $end -gt $VM_COUNT ]; then
        end=$VM_COUNT
    fi
    
    echo "开始处理批次: $i 到 $end" | tee -a "$MAIN_LOG"
    
    for ((j=i; j<=end; j++)); do
        vm_name="vm$j"
        echo "启动处理 $vm_name" | tee -a "$MAIN_LOG"
        /tmp/process_single_vm.exp "$vm_name" "$SOURCE_DIR" >> "$LOG_DIR/${vm_name}.log" 2>&1 &
        pids+=($!)
    done
    
    # 等待所有进程完成
    echo "等待批次完成 ($i 到 $end)..." | tee -a "$MAIN_LOG"
    for pid in "${pids[@]}"; do
        wait $pid
        echo "进程 $pid 已完成" | tee -a "$MAIN_LOG"
    done
    
    echo "批次 $i 到 $end 处理完成" | tee -a "$MAIN_LOG"
done

echo "所有虚拟机处理完成" | tee -a "$MAIN_LOG"
echo "各虚拟机的日志保存在 $LOG_DIR 目录下" | tee -a "$MAIN_LOG"
echo "完成时间: $(date)" | tee -a "$MAIN_LOG"

# 清理临时文件
rm -f /tmp/process_single_vm.exp
