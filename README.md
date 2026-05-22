本仓库用于存储本学期现代数据库课程的族谱管理项目。

不要修改 resources 文件夹及里面的 defaultpic.jpg。

运行前请先确认：
1. 已安装并启动 PostgreSQL。
2. 已安装 PostgreSQL 客户端工具，确保 `psql` 和 `pg_dump` 可以直接在命令行中使用。
3. 数据库连接地址与代码中的默认配置一致，或自行修改为你的本地连接信息。

建议按以下顺序执行：

1. 创建环境：`conda create --name genealogy python=3.12.13 -y`
2. 启动环境：`conda activate genealogy`
3. 安装相关包：`pip install -r requirements.txt`
4. 先执行 `init_db.sql` 初始化表结构，再导入数据。
5. 生成数据：`python generate_data.py`
6. 第一次导入数据：`python load_db.py`
7. 运行网页程序：`uvicorn main:app --reload`

补充说明：
- 如果需要重新导出整个数据库，可执行 `python export_db.py`，会在项目根目录生成 `genealogy_db_bck`。
- `generate_data.py` 会生成成员数据文件 `members_load.csv`，`load_db.py` 会把它导入数据库并补充婚姻关系。
- 如果你只想导入已有数据，至少要先完成建库和建表，再运行导入脚本。





