import time
from sqlalchemy import create_engine, text
# 这个脚本用于测试在 members 表上创建索引前后的查询性能差异，特别是针对模糊搜索和父母关系查询。

DB_URL = 'postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db'
engine = create_engine(DB_URL)

with engine.connect() as conn:
    print('=== DROP INDEXES (SIMULATING BEFORE) ===')
    conn.execute(text('DROP INDEX IF EXISTS idx_members_name_trgm'))
    conn.execute(text('DROP INDEX IF EXISTS idx_members_mother'))
    conn.commit()

    print('\n=== BEFORE INDEXES ===')
    res1 = conn.execute(text("EXPLAIN ANALYZE SELECT member_id FROM members WHERE name LIKE '%明%'")).fetchall()
    print('Fuzzy Search:', [r[0] for r in res1 if 'Execution Time' in r[0]][0])
    
    res2 = conn.execute(text("EXPLAIN ANALYZE SELECT member_id FROM members WHERE father_id IN (100, 101) OR mother_id IN (100, 101)")).fetchall()
    print('Child Search (OR logic):', [r[0] for r in res2 if 'Execution Time' in r[0]][0])

    FOUR_GEN_QUERY = """
    EXPLAIN ANALYZE
    WITH RECURSIVE descendants AS (
        SELECT member_id, 1 as depth
        FROM members
        WHERE member_id = 100
        UNION ALL
        SELECT m.member_id, d.depth + 1
        FROM members m
        JOIN descendants d ON m.father_id = d.member_id OR m.mother_id = d.member_id
        WHERE d.depth < 4
    )
    SELECT member_id FROM descendants WHERE depth = 4;
    """
    res_gen_before = conn.execute(text(FOUR_GEN_QUERY)).fetchall()
    print('4-Gen Descendant Search:', [r[0] for r in res_gen_before if 'Execution Time' in r[0]][0])

    print('\n=== CREATE INDEXES ===')
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    conn.execute(text('CREATE INDEX idx_members_name_trgm ON members USING gin (name gin_trgm_ops)'))
    conn.execute(text('CREATE INDEX idx_members_mother ON members(mother_id)'))
    conn.commit()

    print('\n=== AFTER INDEXES ===')
    res3 = conn.execute(text("EXPLAIN ANALYZE SELECT member_id FROM members WHERE name LIKE '%明%'")).fetchall()
    print('Fuzzy Search:', [r[0] for r in res3 if 'Execution Time' in r[0]][0])
    
    res4 = conn.execute(text("EXPLAIN ANALYZE SELECT member_id FROM members WHERE father_id IN (100, 101) OR mother_id IN (100, 101)")).fetchall()
    print('Child Search (OR logic):', [r[0] for r in res4 if 'Execution Time' in r[0]][0])

    res_gen_after = conn.execute(text(FOUR_GEN_QUERY)).fetchall()
    print('4-Gen Descendant Search:', [r[0] for r in res_gen_after if 'Execution Time' in r[0]][0])
