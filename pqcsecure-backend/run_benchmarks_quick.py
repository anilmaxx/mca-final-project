import json
import benchmark

kem_results = benchmark.run_kem_benchmark(iterations=10)
print("--- KEM BENCHMARKS ---")
print(json.dumps(kem_results, indent=2))

stego_results = benchmark.run_end_to_end_benchmark()
print("\n--- E2E LATENCY BENCHMARKS ---")
print(json.dumps(stego_results, indent=2))

sym_results = benchmark.run_symmetric_benchmark()
print("\n--- SYMMETRIC AES BENCHMARKS ---")
print(json.dumps(sym_results, indent=2))
