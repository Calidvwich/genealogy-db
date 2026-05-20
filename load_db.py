import psycopg2
conn=psycopg2.connect('postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db')
cur=conn.cursor()
cur.execute('TRUNCATE TABLE members CASCADE;')
curr=cur.copy_expert('COPY members(member_id, clan_id, name, gender, birth_year, death_year, father_id, mother_id, generation_num, bio) FROM STDIN WITH CSV', open('members_load.csv', 'r', encoding='utf-8'))
conn.commit()
print('Done!')
