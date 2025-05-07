import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import platform
import pprint

# matplotlib 可能的后端问题警告抑制 (如果需要)
# import warnings
# warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

class PerformanceAnalyzer:
    """
    分析处理器性能数据，包括指令分布、周期数、CPI、IFU和LSU性能，
    并提供一个方法同时输出分析结果和生成五个特定可视化图表。
    增加阿姆达尔定律计算潜在加速比的功能。
    修改输出，显示各类型指令的数量占比和周期占比，并附带绝对值。
    """
    def __init__(self, data):
        if not isinstance(data, dict):
            raise ValueError("输入数据必须是字典类型")
        self.data = data
        self._set_chinese_font()

    def _set_chinese_font(self):
        os_type = platform.system()
        font_name = None
        possible_fonts = []

        if os_type == "Windows":
            possible_fonts = ['SimHei', 'Microsoft YaHei', 'DengXian']
        elif os_type == "Darwin": # macOS
            possible_fonts = ['PingFang HK', 'PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
        else: # Linux
            possible_fonts = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Source Han Sans SC', 'Droid Sans Fallback']

        available_fonts = {f.name for f in fm.fontManager.ttflist}

        for font in possible_fonts:
            if font in available_fonts:
                font_name = font
                break

        if font_name:
            plt.rcParams['font.sans-serif'] = [font_name]
            plt.rcParams['axes.unicode_minus'] = False
            print(f"信息：已设置中文字体为 '{font_name}'。") # 增加提示
        else:
            print("警告：未找到合适的中文字体，图表中的中文可能无法正常显示。")

    def analyze_mode(self, mode):
        # --- 数据检查与提取 ---
        if mode not in self.data.get('type', {}) or \
           mode not in self.data.get('ifu', {}) or \
           mode not in self.data.get('lsu', {}):
            print(f"错误：数据中模式 '{mode}' 的 'type', 'ifu', 或 'lsu' 信息不完整。")
            return None
        type_data = self.data['type'][mode]
        ifu_data = self.data['ifu'][mode]
        lsu_data = self.data['lsu'][mode]
        if not type_data:
            print(f"警告：模式 '{mode}' 的 'type' 数据为空。")
            return None

        # --- 计算 ---
        total_instructions_mode = sum(v.get('instructions', 0) for v in type_data.values())
        total_cycles_mode = sum(v.get('cycles', 0) for v in type_data.values())

        instruction_distribution_pct = {} # 指令数量占比 %
        instruction_distribution_abs = {}    # 指令数量 (绝对值) <--- 新增
        cycle_distribution_abs = {}   # 指令周期数 (绝对值)
        cycle_distribution_pct = {}   # 指令周期数占比 %
        cpi_per_type = {}             # 每类指令的CPI
        instruction_types = list(type_data.keys()) # 指令类型列表

        # 处理指令数为0或周期数为0的情况
        valid_instruction_calc = total_instructions_mode > 0
        valid_cycle_calc = total_cycles_mode > 0

        for instr_type, values in type_data.items():
            instructions = values.get('instructions', 0)
            cycles = values.get('cycles', 0)

            instruction_distribution_abs[instr_type] = instructions # <--- 记录绝对指令数

            cycle_distribution_abs[instr_type] = cycles # 记录绝对周期数

            if valid_instruction_calc:
                instruction_distribution_pct[instr_type] = (instructions / total_instructions_mode) * 100
            else:
                 instruction_distribution_pct[instr_type] = 0

            if valid_cycle_calc:
                cycle_distribution_pct[instr_type] = (cycles / total_cycles_mode) * 100
            else:
                 cycle_distribution_pct[instr_type] = 0

            if instructions > 0:
                cpi_per_type[instr_type] = cycles / instructions
            else:
                 cpi_per_type[instr_type] = 0

        # IFU/LSU 计算保持不变
        ifu_fetch_quantity = ifu_data.get('fetch_quantity', 0)
        ifu_fetch_cycles = ifu_data.get('fetch_cycles', 0)
        ifu_avg_fetch_cycles = ifu_fetch_cycles / ifu_fetch_quantity if ifu_fetch_quantity > 0 else 0

        lsu_load_quantity = lsu_data.get('load', {}).get('quantity', 0)
        lsu_load_cycles = lsu_data.get('load', {}).get('cycles', 0)
        lsu_avg_load_cycles = lsu_load_cycles / lsu_load_quantity if lsu_load_quantity > 0 else 0

        lsu_store_quantity = lsu_data.get('store', {}).get('quantity', 0)
        lsu_store_cycles = lsu_data.get('store', {}).get('cycles', 0)
        lsu_avg_store_cycles = lsu_store_cycles / lsu_store_quantity if lsu_store_quantity > 0 else 0

        return {
            'instruction_types': instruction_types,
            'total_instructions': total_instructions_mode,
            'total_cycles': total_cycles_mode,
            'instruction_distribution_pct': instruction_distribution_pct, # % (数量)
            'instruction_distribution_abs': instruction_distribution_abs,       # absolute instructions <--- 新增返回
            'cycle_distribution_abs': cycle_distribution_abs,    # absolute cycles
            'cycle_distribution_pct': cycle_distribution_pct,    # % (周期)
            'cpi_per_type': cpi_per_type,                        # CPI
            'ifu_avg_fetch_cycles': ifu_avg_fetch_cycles,        # cycles/fetch
            'lsu_avg_load_cycles': lsu_avg_load_cycles,          # cycles/load (LSU specific)
            'lsu_avg_store_cycles': lsu_avg_store_cycles         # cycles/store (LSU specific)
        }

    def _print_analysis_results(self, mode_name, analysis_data):
        # --- 打印逻辑 (修改第1点和第2点) ---
        print(f"\n{'='*10} {mode_name.capitalize()} 模式分析结果 {'='*10}")
        if not analysis_data:
            print("未能生成分析数据."); print("=" * (22 + len(mode_name) + 12)); return

        print(f"模式总指令数: {analysis_data['total_instructions']:,}")
        print(f"模式总周期数: {analysis_data['total_cycles']:,}")

        # --- 修改点 1: 打印指令数量占比及绝对值 ---
        print("\n1. 指令类型数量分布 (%):")
        if not analysis_data.get('instruction_distribution_pct'): print("  无数据。")
        else:
             # 按指令数量百分比降序排序
            sorted_instr_dist = sorted(analysis_data['instruction_distribution_pct'].items(), key=lambda item: item[1], reverse=True)
            abs_instructions_dict = analysis_data.get('instruction_distribution_abs', {}) # 获取绝对数量字典
            for type, pct in sorted_instr_dist:
                abs_instr_count = abs_instructions_dict.get(type, 0) # 获取对应类型的绝对数量
                # 格式化输出，包含百分比和绝对数量
                print(f"  - {type:<10}: {pct:>7.6f}%  ({abs_instr_count:>10,} instructions)")
        # ------------------------------------------

        # --- 修改点 2: 保持周期占比及绝对值的打印 ---
        print("\n2. 各类指令周期数占比 (%):")
        if not analysis_data.get('cycle_distribution_pct'): print("  无数据。")
        else:
            # 按周期百分比降序排序
            sorted_cycle_pct = sorted(analysis_data['cycle_distribution_pct'].items(), key=lambda item: item[1], reverse=True)
            abs_cycles_dict = analysis_data.get('cycle_distribution_abs', {}) # 获取绝对周期字典
            for type, pct in sorted_cycle_pct:
                abs_cycles = abs_cycles_dict.get(type, 0) # 获取对应类型的绝对周期数
                print(f"  - {type:<10}: {pct:>7.6f}%  ({abs_cycles:>10,} cycles)") # 保持原有格式
        # ----------------------------------------

        print("\n3. 各类指令平均执行周期 (CPI):")
        if not analysis_data.get('cpi_per_type'): print("  无数据。")
        else:
            # 按CPI降序排序
            sorted_cpi = sorted(analysis_data['cpi_per_type'].items(), key=lambda item: item[1], reverse=True)
            for type, cpi in sorted_cpi: print(f"  - {type:<10}: {cpi:>7.6f}")

        print("\n4. IFU 平均取指周期:")
        print(f"  {analysis_data.get('ifu_avg_fetch_cycles', 0):.2f} cycles/fetch")

        print("\n5. LSU 平均操作周期 (基于 LSU 统计):")
        print(f"  - Load : {analysis_data.get('lsu_avg_load_cycles', 0):.2f} cycles/load")
        print(f"  - Store: {analysis_data.get('lsu_avg_store_cycles', 0):.2f} cycles/store")
        print("=" * (22 + len(mode_name) + 12))

    # --- _generate_plots, analyze_and_visualize, calculate_amdahl_speedup 保持不变 ---
    def _generate_plots(self, analysis_bootloader, analysis_normal):
        """
        生成并显示 5 个对比图表。
        """
        # --- 安全获取数据和标签 ---
        if not analysis_bootloader or not analysis_normal:
            print("错误：缺少一个或两个模式的分析数据，无法生成所有图表。")
            return

        # 统一指令类型标签，处理可能的不一致
        bl_types = set(analysis_bootloader.get('instruction_types', []))
        nr_types = set(analysis_normal.get('instruction_types', []))
        all_labels = sorted(list(bl_types | nr_types))
        if not all_labels:
             print("警告：无法获取有效的指令类型用于绘图。")
             # 即使没有指令类型，IFU/LSU图仍然可以画

        # Helper function to safely get data, defaulting to 0
        def get_data(analysis_dict, key, label_list, subkey=None): # 增加subkey以处理嵌套字典
            data_source = analysis_dict.get(key, {}) if analysis_dict else {}
            if subkey: # 如果需要访问嵌套字典
                 data_source = data_source.get(subkey, {})
            # 确保即使某个label在data_source中不存在，也能返回0
            return [data_source.get(label, 0) for label in label_list]


        # --- 图表 1: 各类指令占比 (%) - 柱状图 ---
        if all_labels: # 仅当有指令类型时绘制
            fig1, ax1 = plt.subplots(figsize=(15, 9))
            x = np.arange(len(all_labels))
            width = 0.35
            # 使用 instruction_distribution (指令数量占比)
            dist_bootloader = get_data(analysis_bootloader, 'instruction_distribution_pct', all_labels)
            dist_normal = get_data(analysis_normal, 'instruction_distribution_pct', all_labels)

            rects1 = ax1.bar(x - width/2, dist_bootloader, width, label='Bootloader')
            rects2 = ax1.bar(x + width/2, dist_normal, width, label='Normal')

            ax1.set_ylabel('指令数量占比 (%)')
            ax1.set_title('图 1: Bootloader vs Normal - 指令类型数量分布')
            ax1.set_xticks(x)
            ax1.set_xticklabels(all_labels, rotation=45, ha="right") # 旋转标签防止重叠
            ax1.legend()
            ax1.bar_label(rects1, padding=3, fmt='%.1f%%')
            ax1.bar_label(rects2, padding=3, fmt='%.1f%%')
            fig1.tight_layout()
            plt.show()
        else:
            print("信息：跳过绘制指令类型数量分布图 (无有效指令类型)。")

        # --- 图表 2: 各类指令运行周期占比 (%) - 饼图 ---
        # 这个图已经显示了周期占比，无需修改逻辑，只需确保数据来源正确
        if all_labels: # 仅当有指令类型时绘制
            fig2, (ax2_bl, ax2_nr) = plt.subplots(1, 2, figsize=(16, 9))

            # Bootloader Pie Chart
            # 使用 cycle_distribution_abs 来计算饼图，matplotlib会自动计算百分比
            cycles_bl_dict = analysis_bootloader.get('cycle_distribution_abs', {})
            total_cycles_bl = analysis_bootloader.get('total_cycles', 0)

            # 过滤掉周期为0或过小的类别，避免饼图混乱
            threshold_pct_bl = 1.0 # 小于1%的合并为'Other'
            labels_bl_filtered = []
            sizes_bl_filtered = []
            other_bl_size = 0
            if total_cycles_bl > 0:
                # 按周期数降序排序，这样饼图扇区大致按大小排列
                sorted_cycles_bl = sorted(cycles_bl_dict.items(), key=lambda item: item[1], reverse=True)
                for label, size in sorted_cycles_bl:
                    if size > 0:
                        percentage = (size / total_cycles_bl) * 100
                        if percentage >= threshold_pct_bl:
                            labels_bl_filtered.append(label)
                            sizes_bl_filtered.append(size)
                        else:
                            other_bl_size += size
                if other_bl_size > 0:
                    labels_bl_filtered.append('Other')
                    sizes_bl_filtered.append(other_bl_size)

            if sizes_bl_filtered: # 确保有数据可画
                # 使用 counterclock=False 让扇区顺时针排列
                ax2_bl.pie(sizes_bl_filtered, labels=labels_bl_filtered, autopct='%1.1f%%', startangle=90, counterclock=False)
                ax2_bl.set_title('Bootloader: 各类指令周期数占比')
            else:
                ax2_bl.text(0.5, 0.5, '无周期数据或所有类别占比过小', horizontalalignment='center', verticalalignment='center')
                ax2_bl.set_title('Bootloader: 各类指令周期数占比')
            ax2_bl.axis('equal')

            # Normal Pie Chart
            cycles_nr_dict = analysis_normal.get('cycle_distribution_abs', {})
            total_cycles_nr = analysis_normal.get('total_cycles', 0)

            threshold_pct_nr = 1.0
            labels_nr_filtered = []
            sizes_nr_filtered = []
            other_nr_size = 0
            if total_cycles_nr > 0:
                 # 按周期数降序排序
                 sorted_cycles_nr = sorted(cycles_nr_dict.items(), key=lambda item: item[1], reverse=True)
                 for label, size in sorted_cycles_nr:
                    if size > 0:
                        percentage = (size / total_cycles_nr) * 100
                        if percentage >= threshold_pct_nr:
                            labels_nr_filtered.append(label)
                            sizes_nr_filtered.append(size)
                        else:
                            other_nr_size += size
                 if other_nr_size > 0:
                    labels_nr_filtered.append('Other')
                    sizes_nr_filtered.append(other_nr_size)

            if sizes_nr_filtered:
                ax2_nr.pie(sizes_nr_filtered, labels=labels_nr_filtered, autopct='%1.1f%%', startangle=90, counterclock=False)
                ax2_nr.set_title('Normal: 各类指令周期数占比')
            else:
                ax2_nr.text(0.5, 0.5, '无周期数据或所有类别占比过小', horizontalalignment='center', verticalalignment='center')
                ax2_nr.set_title('Normal: 各类指令周期数占比')
            ax2_nr.axis('equal')

            fig2.suptitle('图 2: 各类指令运行周期占比 (%)', fontsize=14)
            fig2.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.show()
        else:
             print("信息：跳过绘制周期占比饼图 (无有效指令类型)。")


        # --- 图表 3: 各类指令的 CPI - 柱状图 ---
        if all_labels: # 仅当有指令类型时绘制
            fig3, ax3 = plt.subplots(figsize=(15, 9))
            x = np.arange(len(all_labels))
            width = 0.35
            # 使用 cpi_per_type
            cpi_bootloader = get_data(analysis_bootloader, 'cpi_per_type', all_labels)
            cpi_normal = get_data(analysis_normal, 'cpi_per_type', all_labels)

            rects5 = ax3.bar(x - width/2, cpi_bootloader, width, label='Bootloader')
            rects6 = ax3.bar(x + width/2, cpi_normal, width, label='Normal')

            ax3.set_ylabel('平均执行周期 (CPI)')
            ax3.set_title('图 3: Bootloader vs Normal - 各类指令平均执行周期 (CPI)')
            ax3.set_xticks(x)
            ax3.set_xticklabels(all_labels, rotation=45, ha="right") # 旋转标签
            ax3.legend()
            ax3.bar_label(rects5, padding=3, fmt='%.2f')
            ax3.bar_label(rects6, padding=3, fmt='%.2f')
            fig3.tight_layout()
            plt.show()
        else:
            print("信息：跳过绘制 CPI 对比图 (无有效指令类型)。")


        # --- 图表 4: IFU 平均取指周期 - 柱状图 ---
        fig4, ax4 = plt.subplots(figsize=(6, 5))
        modes = ['Bootloader', 'Normal']
        # 使用 ifu_avg_fetch_cycles
        ifu_avg_cycles = [
            analysis_bootloader.get('ifu_avg_fetch_cycles', 0),
            analysis_normal.get('ifu_avg_fetch_cycles', 0)
        ]

        bars4 = ax4.bar(modes, ifu_avg_cycles, color=['tab:blue', 'tab:orange'], width=0.5)

        ax4.set_ylabel('平均周期数')
        ax4.set_title('图 4: IFU 平均取指周期对比')
        ax4.bar_label(bars4, fmt='%.2f')
        # 自动调整Y轴范围通常足够好
        # ax4.set_ylim(bottom=0)
        fig4.tight_layout()
        plt.show()

        # --- 图表 5: LSU 平均 Load/Store 周期 - 分组柱状图 ---
        fig5, ax5 = plt.subplots(figsize=(8, 6))
        lsu_categories = ['Load 平均周期', 'Store 平均周期']
        x_lsu = np.arange(len(lsu_categories))
        width_lsu = 0.35

        # 使用 lsu_avg_load_cycles 和 lsu_avg_store_cycles
        lsu_bl_values = [
            analysis_bootloader.get('lsu_avg_load_cycles', 0),
            analysis_bootloader.get('lsu_avg_store_cycles', 0)
        ]
        lsu_nr_values = [
            analysis_normal.get('lsu_avg_load_cycles', 0),
            analysis_normal.get('lsu_avg_store_cycles', 0)
        ]

        rects7 = ax5.bar(x_lsu - width_lsu/2, lsu_bl_values, width_lsu, label='Bootloader', color='tab:blue')
        rects8 = ax5.bar(x_lsu + width_lsu/2, lsu_nr_values, width_lsu, label='Normal', color='tab:orange')

        ax5.set_ylabel('平均周期数 (基于LSU统计)')
        ax5.set_title('图 5: LSU 平均 Load/Store 操作周期对比')
        ax5.set_xticks(x_lsu)
        ax5.set_xticklabels(lsu_categories)
        ax5.legend()
        ax5.bar_label(rects7, padding=3, fmt='%.2f')
        ax5.bar_label(rects8, padding=3, fmt='%.2f')
        # ax5.set_ylim(bottom=0)
        fig5.tight_layout()
        plt.show()

    def analyze_and_visualize(self):
        # --- 分析和可视化入口 (保持不变) ---
        print("="*20 + " 开始性能分析 " + "="*20)
        analysis_bl = self.analyze_mode('bootloader')
        analysis_nr = self.analyze_mode('normal')
        self._print_analysis_results('bootloader', analysis_bl)
        self._print_analysis_results('normal', analysis_nr)

        if not analysis_bl or not analysis_nr:
            print("\n错误：由于至少一个模式的分析数据不完整，无法生成所有图表。")
        else:
            print("\n即将生成图表...")
            try:
                self._generate_plots(analysis_bl, analysis_nr)
                print("图表已生成并显示。")
            except Exception as e:
                print(f"\n生成图表时发生错误: {e}")
                import traceback
                traceback.print_exc()

        print("="*20 + " 分析与可视化完成 " + "="*20)


    def calculate_amdahl_speedup(self, mode: str, improvements: dict):
        """
        计算阿姆达尔定律定义的理论加速比，支持同时优化多个组件。

        Args:
            mode (str): 要分析的模式 ('bootloader' 或 'normal')。
            improvements (dict): 一个字典，键是组件（指令类型）名称 (str)，
                                 值是该组件的性能提升倍数 (float or int, > 1)。
                                 例如: {'load': 2.0, 'calculate': 1.5}

        Returns:
            dict: 包含 'total_fraction_enhanced' 和 'overall_speedup' 的字典，
                  如果计算失败则返回 None。
        """
        # 打印分析标题
        print(f"\n--- 阿姆达尔定律分析 ({mode} 模式) ---")

        # 1. 输入验证: improvements 参数
        if not isinstance(improvements, dict):
            print("错误：'improvements' 参数必须是一个字典。")
            return None
        if not improvements:
            print("错误：'improvements' 字典不能为空，至少需要指定一个优化项。")
            return None

        # 2. 获取基础分析数据
        analysis_result = self.analyze_mode(mode)
        if not analysis_result:
            print(f"错误：无法分析模式 '{mode}' 的数据。")
            return None # analyze_mode 内部已打印错误

        type_data = self.data.get('type', {}).get(mode, {})
        total_cycles = analysis_result['total_cycles']

        # 3. 检查总周期数
        if total_cycles == 0:
            print(f"警告：模式 '{mode}' 的总周期数为 0，无法计算加速比。")
            # 返回表示无加速的值
            return {'total_fraction_enhanced': 0.0, 'overall_speedup': 1.0}

        # 4. 验证 improvements 字典中的每一项，并准备计算
        total_fraction_enhanced = 0.0  # 初始化总的可优化部分比例
        sum_of_fraction_over_factor = 0.0 # 初始化 Σ (Fi / Si)
        valid_improvements = {} # 存储验证通过的优化项及其数据

        print("计划优化的组件及提升倍数:")
        for component_name, improvement_factor in improvements.items():
            # a. 检查组件是否存在
            if component_name not in type_data:
                print(f"  - 错误：在模式 '{mode}' 中未找到指令类型 '{component_name}'。跳过此项。")
                continue # 跳过这个无效的组件

            # b. 检查提升因子是否有效
            if not isinstance(improvement_factor, (int, float)) or improvement_factor <= 1:
                print(f"  - 错误：组件 '{component_name}' 的 'improvement_factor' ({improvement_factor}) 必须是大于 1 的数字。跳过此项。")
                continue # 跳过这个无效的因子

            # c. 获取组件周期数并计算比例
            component_cycles = type_data[component_name].get('cycles', 0)
            fraction_enhanced = component_cycles / total_cycles

            # d. 累加总优化比例
            total_fraction_enhanced += fraction_enhanced

            # e. 计算 Fi / Si 项，并累加
            if improvement_factor == float('inf'):
                # 如果提升无限大，该项对新执行时间的贡献为 0
                sum_of_fraction_over_factor += 0.0
                factor_display = "无限" # 用于后面打印
            else:
                sum_of_fraction_over_factor += fraction_enhanced / improvement_factor
                factor_display = f"{improvement_factor:.2f}" # 用于后面打印

            # 打印当前处理的有效优化项
            print(f"  - {component_name:<10}: 提升 {factor_display} 倍 (占总周期 {fraction_enhanced*100:.2f}%)")
            valid_improvements[component_name] = {'factor': improvement_factor, 'fraction': fraction_enhanced}

        # 5. 检查是否有任何有效的优化项被处理
        if not valid_improvements:
             print("错误：没有提供任何有效的优化组件和提升因子。无法计算加速比。")
             return None

        # 6. 计算最终加速比
        # Amdahl's Law for multiple components: Speedup = 1 / [(1 - ΣFi) + Σ(Fi / Si)]
        fraction_unenhanced = 1.0 - total_fraction_enhanced
        denominator = fraction_unenhanced + sum_of_fraction_over_factor

        # 检查分母是否接近于零 (可能发生在 total_fraction_enhanced 接近 1 且所有因子都无穷大时)
        if abs(denominator) < 1e-9: # 使用一个很小的数来判断是否接近零
            overall_speedup = float('inf') # 理论上加速比为无穷大
        else:
            overall_speedup = 1.0 / denominator

        # 7. 打印结果
        print(f"\n总结:")
        print(f"  - 所有优化组件合计占总周期比例 (Total Fraction Enhanced): {total_fraction_enhanced:.4f} ({total_fraction_enhanced*100:.2f}%)")
        print(f"  - 理论整体加速比 (Overall Speedup): {overall_speedup:.4f} 倍")
        print("-----------------------------------------")

        # 8. 返回结果
        return {'total_fraction_enhanced': total_fraction_enhanced, 'overall_speedup': overall_speedup}

# --- 使用示例 (保持不变) ---
data = {
    'total' : { 'instruction_quantity' : 602668, 'cycle_quantity' : 10193257 },
    'type' : {
        'bootloader' : {
            'calculate' : {'instructions' : 25419, 'cycles' : 206978}, 'load' : {'instructions' : 12666, 'cycles' : 3597904},
            'store' : {'instructions' : 12718, 'cycles' : 115170}, 'jmp' : {'instructions' : 12723, 'cycles' : 102754},
            'csr' : {'instructions' : 0, 'cycles' : 0},
        },
        'normal' : {
            'calculate' : {'instructions' : 291169, 'cycles' : 3115072}, 'load' : {'instructions' : 72001, 'cycles' : 1150920},
            'store' : {'instructions' : 46382, 'cycles' : 565058}, 'jmp' : {'instructions' : 129587, 'cycles' : 1339369},
            'csr' : {'instructions' : 2, 'cycles' : 21},
        }
    },
    'ifu' : {
        'bootloader' : {'fetch_quantity' : 63526, 'fetch_cycles' : 260175},
        'normal' : {'fetch_quantity' : 539142, 'fetch_cycles' : 3576876},
    },
    'lsu' : {
        'bootloader' : {'load' : {'quantity' : 12666, 'cycles' : 3508482}, 'store' : {'quantity' : 12718, 'cycles' : 25436}},
        'normal' : {'load' : {'quantity' : 72001, 'cycles' : 462623}, 'store' : {'quantity' : 46382, 'cycles' : 92764}}
    }
}

analyzer = PerformanceAnalyzer(data)

# 执行分析和可视化
analyzer.analyze_and_visualize()


# 执行 Amdahl 分析

improvements = {
    'calculate' : 5,
    'load' : 20,
    'store' : 10,
    'jmp' : 5,
    'csr' : 5
}
analyzer.calculate_amdahl_speedup(mode='bootloader', improvements=improvements)
