import psycopg2
conn=psycopg2.connect('postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db')
cur=conn.cursor()
cur.execute('TRUNCATE TABLE members CASCADE;')
curr=cur.copy_expert('COPY members(member_id, clan_id, name, gender, birth_year, death_year, father_id, mother_id, generation_num, bio) FROM STDIN WITH CSV', open('members_load.csv', 'r', encoding='utf-8'))

# 依据已有子女记录，批量反推并创建婚姻关系
cur.execute('''
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
	)
''')

conn.commit()
print('Done!')
