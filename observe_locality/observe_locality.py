import matplotlib.pyplot as plt
import numpy as np
import os
import random  # 用于随机选择起始点

# Matplotlib 支持中文的设置
try:
    # 尝试使用常见的无衬线中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
except Exception as e:
    print(f"设置中文字体时可能出现问题: {e}")
    print("如果遇到中文显示问题，请确保已安装支持中文的字体，并正确配置matplotlib。")
    print("常用的中文字体有：SimHei (黑体), WenQuanYi Micro Hei (文泉驿微米黑), Arial Unicode MS等。")


def parse_binary_trace_file(filepath, address_width_bits=32, byte_order='little'):
    """
    解析二进制 TRACE 文件，其中包含连续的内存地址。

    参数:
    filepath (str): 二进制 TRACE 文件的路径。
    address_width_bits (int): 每个地址的位数 (例如 32 或 64)。
    byte_order (str): 地址在文件中的字节序 ('little' 表示小端, 'big' 表示大端)。

    返回:
    list: 解析出的十进制地址列表。如果发生错误，则返回 None。
    """
    addresses = []
    address_width_bytes = address_width_bits // 8

    if address_width_bits not in [32, 64]:
        print(f"错误: 不支持的地址宽度 {address_width_bits}。请选择 32 或 64。")
        return None
    if byte_order not in ['little', 'big']:
        print(f"错误: 不支持的字节序 '{byte_order}'。请选择 'little' 或 'big'。")
        return None

    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(address_width_bytes)
                if not chunk:
                    break
                if len(chunk) < address_width_bytes:
                    print(
                        f"警告: 文件 '{filepath}' 末尾存在不足 {address_width_bytes} 字节的数据块 ({len(chunk)} 字节)，已忽略。")
                    break
                addr = int.from_bytes(chunk, byteorder=byte_order, signed=False)
                addresses.append(addr)
    except FileNotFoundError:
        print(f"错误: 文件 '{filepath}' 未找到。")
        return None
    except Exception as e:
        print(f"读取或解析二进制文件 '{filepath}' 时发生错误: {e}")
        return None
    return addresses


def plot_memory_access_chunked(addresses, output_image_path="memory_access_pattern.svg",  # 默认输出SVG
                               address_width_bits=32,
                               chunk_plot_threshold=1000000,
                               chunk_size_to_plot=1000000,
                               output_format='svg'  # 新增参数指定输出格式
                               ):
    """
    使用 matplotlib 绘制内存访问模式图，并保存为矢量图 (默认为SVG)。
    如果地址总数超过 chunk_plot_threshold，则随机选取一个长度为 chunk_size_to_plot 的连续片段进行绘制。
    否则，绘制所有地址。

    参数:
    addresses (list): 包含十进制内存地址的列表。
    output_image_path (str): 输出图像的文件名及路径。文件名后缀应与output_format匹配。
    address_width_bits (int): 内存地址的位数，用于格式化Y轴标签。
    chunk_plot_threshold (int): 触发抽取连续片段的地址总数阈值。
    chunk_size_to_plot (int): 要抽取的连续地址片段的大小。
    output_format (str): 输出图像的格式，例如 'svg', 'pdf', 'eps'。
    """
    if not addresses:
        print("没有可供绘制的地址数据。")
        return

    num_total_addresses = len(addresses)
    plot_title_info = ""

    if num_total_addresses > chunk_plot_threshold:
        print(f"地址总数 ({num_total_addresses}) 超过阈值 ({chunk_plot_threshold}).")
        actual_chunk_size = min(chunk_size_to_plot, num_total_addresses)
        print(f"将随机抽取一个包含 {actual_chunk_size} 个连续地址的片段进行绘制。")

        if num_total_addresses <= actual_chunk_size:
            selected_addresses_for_plot = addresses
            access_sequence_numbers = np.arange(num_total_addresses)
            plot_title_info = f"(全部 {num_total_addresses} 条)"
        else:
            max_start_index = num_total_addresses - actual_chunk_size
            start_index = random.randint(0, max_start_index)
            end_index = start_index + actual_chunk_size

            selected_addresses_for_plot = addresses[start_index:end_index]
            access_sequence_numbers = np.arange(len(selected_addresses_for_plot))
            plot_title_info = f"(随机连续片段: 原始索引 {start_index}-{end_index - 1}, 共 {len(selected_addresses_for_plot)} 条)"
            print(f"已选择从原始索引 {start_index} 到 {end_index - 1} 的地址。")
    else:
        print(f"地址总数 ({num_total_addresses}) 未超过阈值 ({chunk_plot_threshold})，将绘制所有地址。")
        selected_addresses_for_plot = addresses
        access_sequence_numbers = np.arange(num_total_addresses)
        plot_title_info = f"(全部 {num_total_addresses} 条)"

    # --- 绘图逻辑 ---
    # plt.style.use('seaborn-v0_8-whitegrid') # 可以尝试不同的样式以获得更好的视觉效果
    plt.figure(figsize=(32, 18))

    # 对于矢量图，点的大小 (s) 和透明度 (alpha) 依然重要
    # edgecolors='none' 可以让点看起来更干净，尤其是在密集区域
    # rasterized=True 可以用于在矢量图中将散点图本身栅格化，如果点非常多(数百万)且导致SVG文件过大或渲染过慢，
    # 这可以显著减小文件大小并提高渲染速度，同时保持坐标轴和标签的矢量特性。
    # 但如果点不是特别多，或者需要完全的矢量点，则可以不设置 rasterized=True。
    # 考虑您的要求是“提高图片质量”，我们先不设置 rasterized=True，除非遇到性能问题。
    plt.scatter(access_sequence_numbers, selected_addresses_for_plot,
                s=1,  # 点的大小
                alpha=0.6,  # 点的透明度
                edgecolors='none'  # 不绘制点的边缘
                # rasterized= (True if len(selected_addresses_for_plot) > 50000 else False) # 条件栅格化
                )

    if "随机连续片段" in plot_title_info:
        plt.xlabel(f"片段内访问序号 (0 至 {len(selected_addresses_for_plot) - 1}) - {plot_title_info}", fontsize=12)
    else:
        plt.xlabel(f"访问序号 {plot_title_info}", fontsize=12)

    plt.ylabel(f"内存地址 ({address_width_bits}-bit, 十六进制)", fontsize=12)
    plt.title(f"内存访问模式可视化 (来自二进制TRACE)", fontsize=14)

    hex_digits = address_width_bits // 4

    def to_hex_formatter(y_value, position):
        return f'{int(y_value):0{hex_digits}X}'

    formatter = plt.FuncFormatter(to_hex_formatter)
    plt.gca().yaxis.set_major_formatter(formatter)

    plt.grid(True, linestyle='--', alpha=0.5)  # 网格线可以细一些，透明度低一些
    plt.tight_layout(pad=1.5)  # 调整布局，给标签留出更多空间

    # 确保输出路径的目录存在
    output_dir = os.path.dirname(output_image_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建目录: {output_dir}")

    try:
        # 保存为指定的矢量图格式
        # dpi参数对矢量图影响不大，但某些后端可能会使用它
        plt.savefig(output_image_path, format=output_format, bbox_inches='tight', dpi=300)
        print(f"矢量图已成功保存到: {output_image_path} (格式: {output_format})")
        plt.show()  # 显示图像
    except Exception as e:
        print(f"保存或显示图像时发生错误: {e}")
    finally:
        plt.close()  # 关闭图像，释放资源


if __name__ == "__main__":
    # --- 用户配置区 ---
    trace_file_path = "/workspaces/tools/observe_locality/ITRACE.bin"
    ADDR_WIDTH_BITS = 32
    BYTE_ORDER = 'little'

    # 输出矢量图格式 ('svg', 'pdf', 'eps')
    VECTOR_IMAGE_FORMAT = 'svg'  # <--- 修改这里选择 'svg', 'pdf', 或 'eps'

    # 更新输出文件名以反映格式
    output_image_filename = f"memory_locality_trace_{ADDR_WIDTH_BITS}bit_chunked.{VECTOR_IMAGE_FORMAT}"

    CHUNK_PLOT_THRESHOLD = 100000
    CHUNK_SIZE_TO_PLOT = 100000

    # --- 主程序逻辑 ---
    print(f"开始处理二进制 TRACE 文件: {trace_file_path}")
    print(f"配置参数: 地址宽度={ADDR_WIDTH_BITS}-bit, 字节序='{BYTE_ORDER}'")
    print(f"绘图逻辑: 若地址总数 > {CHUNK_PLOT_THRESHOLD}, 则随机绘制 {CHUNK_SIZE_TO_PLOT} 条连续地址; 否则绘制全部。")
    print(f"输出格式: {VECTOR_IMAGE_FORMAT}")

    memory_addresses = parse_binary_trace_file(
        filepath=trace_file_path,
        address_width_bits=ADDR_WIDTH_BITS,
        byte_order=BYTE_ORDER
    )

    if memory_addresses:
        print(f"成功解析 {len(memory_addresses)} 个内存地址。")

        plot_memory_access_chunked(
            addresses=memory_addresses,
            output_image_path=output_image_filename,
            address_width_bits=ADDR_WIDTH_BITS,
            chunk_plot_threshold=CHUNK_PLOT_THRESHOLD,
            chunk_size_to_plot=CHUNK_SIZE_TO_PLOT,
            output_format=VECTOR_IMAGE_FORMAT  # 传递格式参数
        )
    else:
        print("未能从文件中解析出地址数据，无法进行绘图。请检查文件和配置。")