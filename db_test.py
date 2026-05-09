import psycopg2

try:
    conn = psycopg2.connect(
        dbname="genealogy_db",
        user="postgres",
        password="Xjz20041119",  
        host="localhost",
        port="5432"
    )
    print("数据库连接成功！")
    conn.close()
except Exception as e:
    # 如果报错，尝试用 GBK 解码错误信息
    try:
        error_msg = str(e).encode('utf-8').decode('gbk')
        print(f"连接失败 (GBK解码): {error_msg}")
    except:
        print(f"连接失败 (原始信息): {e}")