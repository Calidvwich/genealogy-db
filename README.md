创建环境：conda create --name genealogy python=3.12.13 -y

启动环境：conda activate genealogy

安装相关包：pip install -r requirements.txt

运行网页程序：uvicorn main:app --reload

生成数据: python generate_data.py

第一次导入数据： python load.py

将数据导出 (备份):\copy (SELECT * FROM genealogies WHERE clan_id = 11) TO 'C:\Users\Lenovo\Desktop\genealogy\clan_11_meta.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

\copy (SELECT * FROM members WHERE clan_id = 11) TO 'C:\Users\Lenovo\Desktop\genealogy\clan_11_members.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

\copy (SELECT * FROM collaborations WHERE clan_id = 11) TO 'C:\Users\Lenovo\Desktop\genealogy\clan_11_collabs.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

\copy (SELECT * FROM marriages WHERE clan_id = 11) TO 'C:/Users/Lenovo/Desktop/genealogy/clan_11_marriages.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

将数据导入 (恢复):  
-- 0. 如果目标库已有 clan_id=11 的数据，先清除（注意顺序，子表先删）
DELETE FROM marriages     WHERE clan_id = 11;
DELETE FROM collaborations WHERE clan_id = 11;
DELETE FROM members       WHERE clan_id = 11;
DELETE FROM genealogies   WHERE clan_id = 11;

-- 1. 先导入 genealogies
\copy genealogies FROM 'C:/Users/Lenovo/Desktop/genealogy/clan_11_meta.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

-- 2. 再导入 members
\copy members FROM 'C:/Users/Lenovo/Desktop/genealogy/clan_11_members.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

-- 3. 导入 collaborations
\copy collaborations FROM 'C:/Users/Lenovo/Desktop/genealogy/clan_11_collabs.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

-- 4. 最后导入 marriages
\copy marriages FROM 'C:/Users/Lenovo/Desktop/genealogy/clan_11_marriages.csv' WITH (FORMAT CSV, HEADER, ENCODING 'UTF8');

修复序列：
SELECT setval('members_member_id_seq',   (SELECT MAX(member_id) FROM members));
SELECT setval('genealogies_clan_id_seq', (SELECT MAX(clan_id)   FROM genealogies));
SELECT setval('members_member_id_seq',   (SELECT MAX(member_id) FROM members));
SELECT setval('genealogies_clan_id_seq', (SELECT MAX(clan_id)   FROM genealogies));
SELECT creator_id FROM genealogies WHERE clan_id = 11;
SELECT DISTINCT user_id FROM collaborations WHERE clan_id = 11;

