import pandas as pd

def xlsx_to_csv(input_file, output_file):
    """
    将 xlsx 文件转换为 csv 文件，并将空白单元格填充为 -1。
    
    参数:
        input_file (str): 输入的 xlsx 文件路径。
        output_file (str): 输出的 csv 文件路径。
    """
    try:
        # 读取 xlsx 文件
        df = pd.read_excel(input_file, header=None)  # 不使用表头，确保所有数据被读取
        df = df.iloc[1:, 1:]
        # 填充空白单元格为 -1
        df.fillna(-1, inplace=True)
        
        # 保存为 csv 文件
        df.to_csv(output_file, index=False, header=False)
        print(f"成功将 {input_file} 转换为 {output_file}")
    
    except Exception as e:
        print(f"发生错误: {e}")

# 示例调用
input_xlsx = "/home/sail01/875/frr/dynamic_frr/TSN-1/tsn_low_orbit_matrix4.xlsx"  # 输入的 xlsx 文件路径
output_csv = "tsn_csv/output_4.csv"    # 输出的 csv 文件路径

xlsx_to_csv(input_xlsx, output_csv)