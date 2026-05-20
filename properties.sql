SELECT 
    t.table_name AS "表名",
    c.column_name AS "属性（字段名）",
    c.data_type AS "数据类型",
    CASE 
        WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'PRIMARY KEY' THEN '⭐ 主键 (PK)'
        WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'FOREIGN KEY' THEN '🔗 外键 (FK)'
        WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'UNIQUE' THEN '💎 唯一约束 (Unique)'
        ELSE ''
    END AS "约束类型", -- 👈 这里已经修复
    CASE 
        WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'FOREIGN KEY' THEN 
            (SELECT ccu.table_name || '.' || ccu.column_name 
             FROM information_schema.constraint_column_usage ccu 
             WHERE ccu.constraint_name = tc.constraint_name LIMIT 1)
        ELSE ''
    END AS "关联的目标表/字段"
FROM information_schema.tables t
JOIN information_schema.columns c ON t.table_name = c.table_name
LEFT JOIN information_schema.key_column_usage kcu 
    ON t.table_name = kcu.table_name AND c.column_name = kcu.column_name
LEFT JOIN information_schema.table_constraints tc 
    ON kcu.table_name = tc.table_name AND kcu.constraint_name = tc.constraint_name
WHERE t.table_schema = 'public' 
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name, c.ordinal_position;