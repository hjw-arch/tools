import subprocess
import re
import itertools
import concurrent.futures
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class CacheConfig:
    block_size: int
    associativity: int
    policy: str
    hit_rate: float = None

def run_cachesim(config: CacheConfig, cache_size: int, trace_file: str) -> Tuple[CacheConfig, float]:
    """运行单个cachesim实例并提取命中率"""
    cmd = f"./cachesim -s {cache_size} -b {config.block_size} -a {config.associativity} -p {config.policy} -t {trace_file}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        output = result.stdout
        # 查找命中率行
        match = re.search(r'命中率:\s*([\d.]+)%', output)
        if match:
            hit_rate = float(match.group(1))
            config.hit_rate = hit_rate
            return config, hit_rate
        else:
            return config, None
    except (subprocess.SubprocessError, ValueError):
        return config, None

def main():
    # 固定参数
    cache_size = 64
    trace_file = "/path/to/your/TRACE.bin"
    
    # 可变参数组合
    block_sizes = [4, 8, 16, 32, 64]
    associativities = [1, 2, 4, 8]
    policies = ["PLRU", "FIFO", "RANDOM"]
    
    # 生成所有参数组合
    configs: List[CacheConfig] = [
        CacheConfig(block_size=b, associativity=a, policy=p)
        for b, a, p in itertools.product(block_sizes, associativities, policies)
    ]
    
    # 并行运行所有组合
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_config = {
            executor.submit(run_cachesim, config, cache_size, trace_file): config 
            for config in configs
        }
        for future in concurrent.futures.as_completed(future_to_config):
            config = future_to_config[future]
            try:
                config, hit_rate = future.result()
                if hit_rate is not None:
                    results.append((config, hit_rate))
            except Exception as e:
                print(f"Config {config} failed with error: {e}")
    
    if not results:
        print("No valid results obtained.")
        return
    
    # 找到最佳命中率
    best_config, best_hit_rate = max(results, key=lambda x: x[1])
    
    # 输出结果
    print(f"Total configurations tested: {len(results)}")
    print("\nBest configuration:")
    print(f"Block Size: {best_config.block_size}")
    print(f"Associativity: {best_config.associativity}")
    print(f"Replacement Policy: {best_config.policy}")
    print(f"Hit Rate: {best_hit_rate:.4f}%")
    
    # 输出所有结果（按命中率排序）
    print("\nAll results (sorted by hit rate):")
    for config, hit_rate in sorted(results, key=lambda x: x[1], reverse=True):
        print(f"Block Size: {config.block_size}, Assoc: {config.associativity}, Policy: {config.policy}, Hit Rate: {hit_rate:.4f}%")

if __name__ == "__main__":
    main()
