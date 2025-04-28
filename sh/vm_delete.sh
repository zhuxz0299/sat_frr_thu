for i in {1..8}; do
	virsh shutdown "vm${i}"
    virsh undefine "vm${i}" --remove-all-storage
	sleep 2
done