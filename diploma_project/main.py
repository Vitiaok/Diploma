from network.config import NetworkConfig
from network.node import Node

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python main.py <node_id>")
        sys.exit(1)

    node_id = sys.argv[1]

    NetworkConfig.initialize(node_id)

    import time
    time.sleep(2)

    node = Node(node_id)
    try:
        node.start()
    except KeyboardInterrupt:
        print("\nShutting down node...")
        node.running = False