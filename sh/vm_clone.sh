for i in {1..44}; do
	virt-clone --original origin_vm --name "vm${i}" --file "/home/zmx/875/image/vm${i}.qcow2"
	sleep 20
	# nvram_file="/var/lib/libvirt/qemu/nvram/VM${i}_VARS.fd"
	# qemu-img resize --shrink -f raw "$nvram_file" 64M
	echo "VM${i} created"
	# sleep 3
done
