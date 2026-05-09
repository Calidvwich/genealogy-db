import pandas as pd
import random
import time

def generate_genealogy_data():
    members = []

    clans = [
        {"id": 1, "size": 55000, "gens": 30},
        *[{"id": i, "size": 5000, "gens": 15} for i in range(2, 11)]
    ]

    global_member_id = 1

    for clan in clans:
        clan_id = clan["id"]
        total_gen = clan["gens"]
        avg_per_gen = clan["size"] // total_gen

        generation_pools = {g: {"M": [], "F": []} for g in range(1, total_gen + 1)}

        # 第一代（始祖）
        for _ in range(max(2, avg_per_gen // 10)):
            gender = random.choice(['M', 'F'])
            members.append([global_member_id, clan_id,
                            f"祖_{clan_id}_{global_member_id}",
                            gender, None, None, 1, "始祖"])
            generation_pools[1][gender].append(global_member_id)
            global_member_id += 1

        # 逐代生成后代
        for g in range(2, total_gen + 1):
            current_gen_size = int(avg_per_gen * random.uniform(0.8, 1.2))
            prev_males   = generation_pools[g-1]["M"]
            prev_females = generation_pools[g-1]["F"]

            if not prev_males or not prev_females:
                break

            # ── 关键改动：先给每对父母分配至少一个孩子，再随机分配剩余名额 ──
            # 随机配对（允许一夫多妻/一妻多夫只是随机选，符合模拟场景）
            couple_count = min(len(prev_males), len(prev_females))
            couples = [(random.choice(prev_males), random.choice(prev_females))
                       for _ in range(couple_count)]

            # 每对夫妻子女数：泊松分布(λ=2.5)，至少 1 个，最多 8 个
            children_per_couple = [max(1, min(8, int(random.gauss(2.5, 1.2))))
                                   for _ in couples]

            # 按比例缩放到目标代人数
            total_assigned = sum(children_per_couple)
            if total_assigned == 0:
                continue
            scale = current_gen_size / total_assigned
            children_per_couple = [max(1, round(n * scale)) for n in children_per_couple]

            for (f_id, m_id), n_children in zip(couples, children_per_couple):
                for _ in range(n_children):
                    gender = random.choice(['M', 'F'])
                    birth  = 1000 + (g - 1) * 30 + random.randint(-5, 5)
                    death  = birth + random.randint(40, 90)
                    members.append([global_member_id, clan_id,
                                    f"名_{clan_id}_{global_member_id}",
                                    gender, f_id, m_id, g, f"第{g}代成员"])
                    generation_pools[g][gender].append(global_member_id)
                    global_member_id += 1

    print("数据生成完毕，正在转换格式...")
    return members


if __name__ == "__main__":
    start = time.time()
    all_members = generate_genealogy_data()

    df = pd.DataFrame(all_members,
                      columns=['member_id', 'clan_id', 'name', 'gender',
                               'father_id', 'mother_id', 'generation_num', 'bio'])
    df['father_id']  = df['father_id'].astype('Int64')
    df['mother_id']  = df['mother_id'].astype('Int64')
    df['member_id']  = df['member_id'].astype('Int64')

    df.to_csv("members_load.csv", index=False, header=False)
    print(f"成功生成 {len(df)} 条成员数据，耗时: {time.time() - start:.2f} 秒")