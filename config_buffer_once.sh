sudo sysctl -w net.core.rmem_max=268435456
sudo sysctl -w net.core.rmem_default=4194304
sudo sysctl -w net.core.wmem_max=268435456
sudo sysctl -w net.core.wmem_default=4194304
sudo sysctl -w net.core.netdev_max_backlog=250000

