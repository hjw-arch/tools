#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <getopt.h>
#include <time.h>
#include "log.h"

#define ADDR_WIDTH		32

#if ADDR_WIDTH == 32
	typedef uint32_t addr_t;
#elif ADDR_WIDTH == 64
	typedef uint64_t addr_t;
#else
	#error "Address width must be 32 or 64!"
#endif


#define LOG2(n)		({	\
	int num = (n);	\
	int result = -1;	\
	while(num) {	\
		num >>= 1;	\
		result++;	\
	}	\
	result;	\
})

#define BIT_MASK(bits)			((1ull << (bits)) - 1)
#define GET_BITS(a, hi, lo)		(((a) & BIT_MASK((hi) + 1)) >> (lo))
#define GET_OFFSET(addr)		GET_BITS(addr, config.bits_for_offset - 1, 0)
#define GET_INDEX(addr)			GET_BITS(addr, config.bits_for_offset + config.bits_for_index - 1, config.bits_for_offset)
#define GET_TAG(addr)			GET_BITS(addr, ADDR_WIDTH - 1, config.bits_for_offset + config.bits_for_index)


static uint64_t total_access_times = 0;	// 总访问次数
static uint64_t total_hit_times = 0;	// 命中次数

static char *trace_file = NULL;

typedef enum {
	POLICY_PLRU,              ///< 伪最近最少使用 (Pseudo-Least Recently Used) 替换策略。
	POLICY_FIFO,              ///< 先进先出 (First-In, First-Out) 替换策略。
    POLICY_RANDOM             ///< 随机替换策略。
} replacement_policy_t;

typedef struct {
	int total_size;				// cache总大小
	int block_size;				// cache块大小, 单位：字节
	int block_num;				// cache块数量
	int associativity;			// 相联度
	replacement_policy_t policy;	// 替换策略

	int set_num;
	int bits_for_offset;
	int bits_for_index;
	int bits_for_tag;
} cache_config_t;

typedef struct cache_line {
	uint32_t valid;
	uint64_t tag;		// 使用64位，防止是64位地址
} cache_line_t;

typedef struct cache_set {
	cache_line_t *cache_line;
	uint64_t plru_bits;		// 树结构位，用于寻找替死鬼块，对于N路组相联，需要N-1位表示其树形结构
	uint64_t fifo_pointer;	// 指向替死鬼块
} cache_set_t;

static cache_config_t config;
static cache_set_t *cache;

// 检查是否为2的次幂
uint32_t is_pow_2(uint32_t n) {
	return ((n > 0) && ((n & (n - 1)) == 0));
}

void display_usage(char *prog_name) {
	fprintf(stderr, "用法: %s -s <cache总大小> -b <块大小> -a <相联度> -p <替换策略> -t <追踪文件名>\n", prog_name);
    fprintf(stderr, "  参数说明:\n");
    fprintf(stderr, "    -s <大小>: Cache总大小 (单位: 字节, 必须是2的幂).\n");
    fprintf(stderr, "    -b <大小>: Cache块大小 (单位: 字节, 必须是2的幂).\n");
    fprintf(stderr, "    -a <路数>: 相联度 (多少路组相联, 必须是2的幂).\n");
    fprintf(stderr, "               值为 1 表示直接映射 (Direct Mapped).\n");
    fprintf(stderr, "               若 块数量 == 相联度, 则为全相联 (Fully Associative).\n");
    fprintf(stderr, "    -p <策略>: 替换策略。可选值: 'FIFO', 'PLRU', 'RANDOM'.\n");
    fprintf(stderr, "    -t <文件>: 包含内存访问地址序列的追踪文件的路径。\n");
    fprintf(stderr, "               文件每行一个十六进制地址值。\n");
    fprintf(stderr, "    -h        : 显示此帮助信息并退出。\n");
    fprintf(stderr, "  示例:\n");
    fprintf(stderr, "    %s -s 4 -n 64 -a 4 -p PLRU -t /path/to/your/trace.bin\n", prog_name);
}

// 检查cache配置参数是否合适，不支持非2的次幂的参数配置
// 如果cache的组数和相联度是2的次幂，说明cache的总块数一定是2的次幂
void check_config(char *prog_name) {
	if (config.associativity == 0 || config.total_size == 0 || config.block_size == 0) {
		display_usage(prog_name);
		Assert(0, "Missing initialization parameter(s).");
	}

	if (!is_pow_2(config.total_size)) {
		Assert(0, "Cache szie must be power of 2 and cache size can not be zero.");
	}

	if (!is_pow_2(config.block_size)) {
		Assert(0, "Block size must be power of 2 and block size can not be zero.");
	}

	if (!is_pow_2(config.associativity)) {
		Assert(0, "Associativity must be power of 2 and associativity can not be zero.");
	}

	if (config.associativity > config.block_num) {
		Assert(0, "Associativity must equal or less than block number.");
	}

	if (config.associativity > 64) {
		Assert(0, "Associativity must less than 64.");
	}
}

// 解析命令行的命令
void parse_arguments(int argc, char **argv) {
	int opt;
	while ((opt = getopt(argc, argv, "s:b:a:p:t:h")) != -1) {
		switch (opt) {
			case 's':
				config.total_size = atoi(optarg);
				break;
			case 'b':
				config.block_size = atoi(optarg);
				break;
			case 'a':
				config.associativity = atoi(optarg);
				break;
			case 'p':
				if (strcmp(optarg, "FIFO") == 0) {
					config.policy = POLICY_FIFO;
				} else if (strcmp(optarg, "PLRU") == 0) {
					config.policy = POLICY_PLRU;
				} else if (strcmp(optarg, "RANDOM") == 0) {
					config.policy = POLICY_RANDOM;
				} else {
					Assert(0, "Invalid replacement policy.");
				}
				break;
			case 't':
				trace_file = optarg;
				break;
			case 'h':
				display_usage(argv[0]);
				exit(0);
 			default:
				display_usage(argv[0]);
				Assert(0, "Unknown argument(s)!");
				break;
		}
	}
}


void init_cache(char *prog_name) {
	config.block_num = config.total_size / config.block_size;
	config.set_num = config.block_num / config.associativity;		// 组数量

	config.bits_for_offset = LOG2(config.block_size);
	config.bits_for_index = LOG2(config.set_num);
	config.bits_for_tag = ADDR_WIDTH - config.bits_for_offset - config.bits_for_index;

	cache = (cache_set_t *)malloc(config.set_num * sizeof(cache_set_t));
	Assert(cache, "Fail to alloc memory for cache.");

	// 分配内存
	for (uint32_t i = 0; i < config.set_num; i++) {
		cache[i].cache_line = (cache_line_t *)calloc(config.associativity, sizeof(cache_line_t));

		if (!cache[i].cache_line) {
			perror("Fail to alloc memory for cache line.");

			for (uint32_t j = 0; j < i; j++) {
				free(cache[j].cache_line);
				cache[j].cache_line = NULL;		// 避免悬挂指针，安全考虑
			}

			free(cache);
			cache = NULL;
			exit(-1);
		}

		cache[i].fifo_pointer = 0;
		cache[i].plru_bits = 0;
	}

	// 如果采用随机替换算法，初始化一个随机种子
	// 随机种子使用当前时间
	if (config.policy == POLICY_RANDOM) {
		srand(time(NULL));
	}

	check_config(prog_name);

	// 打印配置信息
    printf("--- Cache 配置初始化完成 ---\n");
    printf("总大小:         %d 字节\n", config.total_size);
    printf("块大小:         %d 字节\n", config.block_size);
	printf("总行数:         %d\n", config.block_num);
    printf("相联度:         %d 路\n", config.associativity);
	printf("总组数:         %d\n", config.set_num);
    printf("替换策略:       %s\n", config.policy == POLICY_FIFO ? "FIFO" :
                                     (config.policy == POLICY_PLRU ? "PLRU" : "Random"));
    printf("块内偏移位数:   %d\n", config.bits_for_offset);
    printf("组索引位数:     %d\n", config.bits_for_index);
    printf("标签位数:       %d\n", config.bits_for_tag);
    printf("---------------------------\n");
}

// 根据hit_way将沿途的bit都设置为远离hit way
void update_plru_victim_way(cache_set_t *current_cache_set, uint32_t hit_way) {
	if (config.associativity == 1) {	// 直接映射，无需更新状态
		return;
	}

	uint32_t tree_level = LOG2(config.associativity);

	uint32_t current_node_index = 0;		// 记录当前节点的索引

	for (uint32_t i = 0; i < tree_level; i++) {
		uint32_t shift = tree_level - 1 - i;
		uint32_t direction = (hit_way >> shift) & 1;	// 获取hit_way最高位

		if (direction) {
			current_cache_set->plru_bits &= ~(1ULL << current_node_index);
		} else {
			current_cache_set->plru_bits |= (1ULL << current_node_index);
		}

		current_node_index = current_node_index * 2 + 1 + direction;		// 更新当前节点的索引
	}
}

// 从根节点找victim_way 沿途的bit都要远离victim way
uint64_t find_and_updata_plru_victim_way(cache_set_t *current_cache_set) {
	if (config.associativity == 1) {	// 直接映射，直接返回0
		return 0;
	}

	uint32_t tree_level = LOG2(config.associativity);	// 树的高度

	uint64_t victim_way = 0;

	uint32_t current_node_index = 0;

	for (uint32_t i = 0; i < tree_level; i++) {
		uint32_t bit = (current_cache_set->plru_bits >> current_node_index) & 1;	// 根据plru_bits找到当前的节点

		if (bit) {
			current_cache_set->plru_bits &= ~(1ULL << current_node_index);
		} else {
			current_cache_set->plru_bits |= (1ULL << current_node_index);
		}

		current_node_index = current_node_index * 2 + 1 + bit;

		victim_way = (victim_way << 1) | bit;	// 计算victim_way，二叉树的特性
	}

	return victim_way;
}

uint64_t find_and_update_fifo_victim_way(cache_set_t *current_cache_set) {
	uint64_t ret = current_cache_set->fifo_pointer;
	current_cache_set->fifo_pointer = (current_cache_set->fifo_pointer + 1) % config.associativity;
	return ret;
}

uint64_t find_random_victim_way() {
	return rand() % config.associativity;
}

void access_cache(addr_t addr) {
	total_access_times++;

	uint64_t index 	= GET_INDEX(addr);
	uint64_t tag	= GET_TAG(addr);

	cache_set_t *current_cache_set = &cache[index];

	int hit_way = -1;

	for (uint32_t i = 0; i < config.associativity; i++) {
		if (tag == current_cache_set->cache_line[i].tag && current_cache_set->cache_line[i].valid) {
			// 命中
			hit_way = i;
			break;
		}
	}

	if (hit_way != -1) {	// cache 命中
		total_hit_times++;

		// 如果是LRU，需要更新其牺牲者状态，FIFO和RANDOM无需处理
		if (config.policy == POLICY_PLRU) {
			update_plru_victim_way(current_cache_set, hit_way);
		}
	} else {	// cache 缺失
		int victim_way = -1;	// 牺牲者编号

		switch (config.policy) {
			case POLICY_PLRU:
				victim_way = find_and_updata_plru_victim_way(current_cache_set);
				break;
			case POLICY_FIFO:
				victim_way = find_and_update_fifo_victim_way(current_cache_set);
				break;
			case POLICY_RANDOM:
				victim_way = find_random_victim_way();
				break;
			default:
				break;
		}

		Assert(victim_way >= 0 && victim_way < config.associativity, "Error victim way.");

		current_cache_set->cache_line[victim_way].tag = tag;
		current_cache_set->cache_line[victim_way].valid = 1;
	}
}



// 读出trace值，以此模拟
void sim_cache() {
	FILE *fp = fopen(trace_file, "rb");
	if (!fp) {
		Assert(0, "Open trace file failed.");
	}

	printf("Begin cache simulation...\n");

	addr_t addr;
	size_t items_read;
	uint64_t access_count = 0;

	while((items_read = fread(&addr, sizeof(addr_t), 1, fp)) == 1) {
		access_cache(addr);
		access_count++;

		if (access_count % 1000000 == 0) {
            printf("已处理 %lu 个地址...\n", access_count);
        }
	}

	if (ferror(fp)) {
		fclose(fp);
		Assert(0, "Error(s) occurred while reading the trace file.");
	}

	printf("追踪文件处理完毕。共处理 %lu 个地址。\n", access_count);
}

// 释放为cache申请的内存
void cleanup_memory() {
	if (cache) {
		for (uint32_t i = 0; i < config.set_num; i++) {
			if (cache[i].cache_line) {
				free(cache[i].cache_line);
				cache[i].cache_line = NULL;
			}
		}
		free(cache);
		cache = NULL;
	}
}

void display_statistics() {
    printf("\n--- 模拟结果统计 ---\n");
    printf("总访问次数: %lu\n", total_access_times);
    printf("命中次数:   %lu\n", total_hit_times);
    printf("缺失次数:   %lu\n", total_access_times - total_hit_times);

    if (total_access_times > 0) { // 避免除以零错误。
        double hit_rate = (double)total_hit_times / total_access_times * 100.0;
        printf("命中率:     %.4f%%\n", hit_rate);   // %.4f 表示打印浮点数并保留4位小数。
    } else {
        printf("命中率:     N/A (无访问记录)\n");
    }
    printf("----------------------\n");
}

int main(int argc, char **argv) {
	parse_arguments(argc, argv);

	init_cache(argv[0]);

	sim_cache();

	cleanup_memory();

	display_statistics();

	return 0;
}
