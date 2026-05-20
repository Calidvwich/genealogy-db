启动环境：conda activate genealogy
运行网页程序：uvicorn main:app --reload
生成数据: python generate_data.py
将数据导出 (备份): pg_dump -U postgres -d genealogy_db -f D:/backup/genealogy_backup.sql
将数据导入 (恢复): psql -U postgres -d genealogy_db -f D:/backup/genealogy_backup.sql

