import pandas as pd
import os

# 文件路径
input_file = 'csv_tsn/output_100.csv'  # 原始CSV文件路径
output_file = 'csv_tsn_modify/output_100.csv'  # 处理后的CSV文件路径

# 处理每一列的函数
def process_column(col):
    # 找出正数值
    positive_vals = col[col > 0]
    if positive_vals.empty:
        return pd.Series([-1.0] * len(col))
    # 找出最小的正数值
    min_val = positive_vals.min()
    # 仅保留最小正数值，其他改为-1.0
    processed_col = col.apply(lambda x: x if x == min_val else -1.0)
    return processed_col

# 主函数
def process_csv_file():
    try:
        # 1. 读取原始CSV文件
        if not os.path.exists(input_file):
            return f"错误：找不到文件 '{input_file}'"
            
        df = pd.read_csv(input_file, header=None)
        
        # 2. 处理数据
        processed_df = df.apply(process_column, axis=0)
        
        # 3. 输出到新文件
        processed_df.to_csv(output_file, index=False, header=False)
        
        # 4. 检查新文件每行元素数是否相等
        with open(output_file, 'r') as f:
            lines = f.readlines()
        
        # 统计每行的元素数量
        line_lengths = [len(line.strip().split(',')) for line in lines]
        
        # 检查是否所有行的元素数量都相等
        if len(set(line_lengths)) == 1:
            return f"处理成功！文件已保存到 {output_file}。所有行元素数量相等，每行 {line_lengths[0]} 个元素。"
        else:
            return f"警告：文件已保存，但行元素数不相等。行长度分布: {line_lengths}"
    
    except Exception as e:
        return f"处理过程中出错: {str(e)}"

# 执行处理函数
result = process_csv_file()
print(result)
