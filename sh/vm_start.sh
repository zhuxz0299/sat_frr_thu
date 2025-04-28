for i in {1..43}; do
	virsh start "vm${i}"
	sleep 5
done
