"""Smoke test for the new package structure."""
from blockchain.block import Block
from blockchain.chain import Chain
from blockchain.keys import generate_and_save_keys, sign_data
from security.encryption import generate_aes_key, encrypt_data, decrypt_data
from analysis.logger import NodeLogger
from analysis.metrics import MetricsCollector
from analysis.simulation import NetworkSimulator

print("All imports OK")

# Test encryption
key = generate_aes_key()
enc = encrypt_data(b"blockchain test", key)
assert decrypt_data(enc, key) == b"blockchain test"
print("Encryption OK")

# Test simulation
sim = NetworkSimulator(3)
results = sim.run_benchmark(2, 1024)
ok = sum(1 for r in results if r["success"])
print(f"Simulation OK: {len(results)} transfers, {ok} successful")
stats = sim.network_stats()
print(f"Chain consistency: {stats['chains_consistent']}")
print("All tests passed!")
