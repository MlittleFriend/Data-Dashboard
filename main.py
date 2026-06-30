from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI()

# 允许跨域请求（防止浏览器拦截你的本地网页请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/sales")
def get_sales_data():
    # 1. 连接刚刚生成的 my_data.db 数据库
    conn = sqlite3.connect("my_data.db")
    cursor = conn.cursor()
    
    # 2. 从表中查询数据
    # 💡 这里的表名 'sales_records' 必须和 upload_data.py 里的保持一致
    cursor.execute("SELECT * FROM sales_records")
    rows = cursor.fetchall()
    
    # 3. 获取表格的列名（比如：日期, 数值 等）
    columns = [description[0] for description in cursor.description]
    conn.close()
    
    # 4. 把数据组装成前端最喜欢的 JSON 格式
    result = []
    for row in rows:
        result.append(dict(zip(columns, row)))
        
    return result

if __name__ == "__main__":
    import uvicorn
    # 启动后端服务，运行在本地 8000 端口
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)