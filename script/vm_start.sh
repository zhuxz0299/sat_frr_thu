for i in {1..44}; do
	virsh start "vm${i}"
	sleep 5
done
