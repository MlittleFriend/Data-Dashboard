import pandas as pd
import sqlite3

def import_excel_to_db():
    # 1. 读入 Excel 文件（这里已经改成你的文件名 26630.xlsx）
    # 💡 注意：请确保你的 Excel 里面有两列，比如“日期”和“数值”，或者类似的结构
    df = pd.read_excel("26630.xlsx")
    
    # 打印前几行数据，让我们在终端能看到读取是否成功
    print("成功读取到 Excel 数据，前几行为：")
    print(df.head())
    
    # 2. 连接到 SQLite 数据库（文件不存在会自动创建）
    conn = sqlite3.connect("my_data.db")
    
    # 3. 将数据写入名为 'sales_records' 的表中
    df.to_sql("sales_records", conn, if_exists="replace", index=False)
    
    # 4. 关闭连接
    conn.close()
    print("\n🎉 奇迹发生！Excel 数据已成功同步到本地数据库 (my_data.db)！")

if __name__ == "__main__":
    import_excel_to_db()