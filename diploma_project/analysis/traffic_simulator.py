import requests
import time
import threading
import random
import os
import io

def get_active_nodes(start_port=8080, max_nodes=20):
    print(f"Scanning for active nodes on localhost ports {start_port} to {start_port + max_nodes - 1}...")
    nodes = []
    for port in range(start_port, start_port + max_nodes):
        try:
            url = f"http://localhost:{port}/api/status"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "running":
                    nodes.append({
                        "web_port": port,
                        "node_id": data["node_id"],
                        "transfer_addr": f"{data['host']}:{data['port']}"
                    })
                    print(f"  [+] Found {data['node_id']} on port {port}")
        except requests.exceptions.RequestException:
            pass
    return nodes

def send_dummy_file(sender_node, target_addrs, file_size_kb=100, index=0):
    url = f"http://localhost:{sender_node['web_port']}/api/send-file"
    
    # Create a dummy file in memory
    filename = f"sim_load_{index}_{int(time.time())}.txt"
    file_content = os.urandom(file_size_kb * 1024)
    files = {'file': (filename, io.BytesIO(file_content), 'text/plain')}
    
    data = {}
    if target_addrs:
        import json
        data['targets'] = json.dumps(target_addrs)
        
    print(f"[Thread-{index}] Node '{sender_node['node_id']}' starting transfer of {file_size_kb}KB to {len(target_addrs) if target_addrs else 'ALL'} peers...")
    
    try:
        start_time = time.time()
        response = requests.post(url, files=files, data=data, timeout=30)
        duration = time.time() - start_time
        if response.status_code == 200 and response.json().get("success"):
            print(f"[Thread-{index}] [SUCCESS] Transfer completed in {duration:.2f}s")
        else:
            print(f"[Thread-{index}] [FAILED] HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[Thread-{index}] [ERROR] Request failed: {e}")

def run_simulation():
    print("=== P2P Traffic & Scalability Simulator ===")
    nodes = get_active_nodes()
    
    if len(nodes) < 2:
        print("Error: Need at least 2 active nodes to run simulation.")
        return
        
    print(f"\nDiscovered {len(nodes)} active nodes.")
    print("This script will simulate SIMULTANEOUS file transfers across the network.")
    print("This will trigger chain divergence and force the consensus algorithm to resolve conflicts (auto-heal).\n")
    
    try:
        concurrent = int(input("Enter number of SIMULTANEOUS transfers to trigger (e.g. 5): "))
        file_size = int(input("Enter dummy file size in KB (e.g. 100): "))
    except ValueError:
        print("Invalid input.")
        return

    print(f"\nStarting {concurrent} simultaneous transfers of {file_size}KB each in 3 seconds...\n")
    time.sleep(3)
    
    threads = []
    for i in range(concurrent):
        sender = random.choice(nodes)
        
        # Optionally, pick specific targets (or None to broadcast to all)
        # Let's send to all peers to maximize network stress
        target_addrs = None 
        
        t = threading.Thread(target=send_dummy_file, args=(sender, target_addrs, file_size, i))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("\n=== Simulation Complete ===")
    print("Check the UI of your nodes or the metrics CSV files to analyze consensus resolution times!")

if __name__ == "__main__":
    run_simulation()
