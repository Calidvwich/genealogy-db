-- 批量补全现有成员数据中的婚姻关系
-- 前提：members 表里已经有 father_id / mother_id
-- 作用：从孩子记录反推出一条婚姻记录，避免重复插入

INSERT INTO marriages (clan_id, spouse_a_id, spouse_b_id, marry_year, divorce_year)
SELECT DISTINCT
    x.clan_id,
    LEAST(x.father_id, x.mother_id) AS spouse_a_id,
    GREATEST(x.father_id, x.mother_id) AS spouse_b_id,
    NULL::INT AS marry_year,
    NULL::INT AS divorce_year
FROM (
    SELECT clan_id, father_id, mother_id
    FROM members
    WHERE father_id IS NOT NULL
      AND mother_id IS NOT NULL
) AS x
WHERE x.father_id <> x.mother_id
  AND NOT EXISTS (
      SELECT 1
      FROM marriages mg
      WHERE mg.clan_id = x.clan_id
        AND ((mg.spouse_a_id = LEAST(x.father_id, x.mother_id)
              AND mg.spouse_b_id = GREATEST(x.father_id, x.mother_id))
          OR (mg.spouse_a_id = GREATEST(x.father_id, x.mother_id)
              AND mg.spouse_b_id = LEAST(x.father_id, x.mother_id)))
  );

-- 验证：查询某成员的婚姻与子女仍然依赖 marriages / father_id / mother_id
-- 示例：把 :mid 替换成具体 member_id
-- SELECT * FROM marriages WHERE spouse_a_id = :mid OR spouse_b_id = :mid;
-- SELECT * FROM members WHERE father_id = :mid OR mother_id = :mid;
