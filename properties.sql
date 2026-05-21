SELECT
    c.table_name AS table_name,
    c.column_name AS column_name,
    c.data_type AS data_type,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE kcu.table_schema = c.table_schema
              AND kcu.table_name = c.table_name
              AND kcu.column_name = c.column_name
              AND tc.constraint_type = 'PRIMARY KEY'
        ) THEN 'PK'
        WHEN EXISTS (
            SELECT 1
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE kcu.table_schema = c.table_schema
              AND kcu.table_name = c.table_name
              AND kcu.column_name = c.column_name
              AND tc.constraint_type = 'FOREIGN KEY'
        ) THEN 'FK'
        WHEN EXISTS (
            SELECT 1
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE kcu.table_schema = c.table_schema
              AND kcu.table_name = c.table_name
              AND kcu.column_name = c.column_name
              AND tc.constraint_type = 'UNIQUE'
        ) THEN 'UNIQUE'
        ELSE ''
    END AS constraint_type
FROM information_schema.columns c
JOIN information_schema.tables t
  ON c.table_name = t.table_name
 AND c.table_schema = t.table_schema
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name, c.ordinal_position;