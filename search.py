"""
search.py — 亲缘关系查询模块（内存图加速版）

核心优化：把某一族谱的完整父子关系一次性加载进内存邻接表，
再在内存中做 BFS，避免逐步查询数据库导致的严重性能问题。

对外接口：
    find_relationship(db, name_a, name_b) -> dict
"""

from sqlalchemy import text
from collections import deque


# ── 双向数据库 BFS (消除全表内存加载) ────────────────────────────
def _bfs_in_db(db, id_a: int, id_b: int, max_depth: int = 15) -> list[int] | None:
    """直接使用数据库查询做双向 BFS，避免将几十万数据的全族谱加载进内存。"""
    if id_a == id_b:
        return [id_a]

    # visited 记录 {节点: (父节点, 深度)}
    visited_a = {id_a: (None, 0)}
    visited_b = {id_b: (None, 0)}

    frontier_a = {id_a}
    frontier_b = {id_b}

    intersect_node = None

    for depth in range(max_depth):
        if not frontier_a and not frontier_b:
            break

        # ================== 扩展 A 侧 ==================
        if frontier_a:
            next_frontier_a = set()
            # 批量获取 A 侧前沿节点的所有邻居 (父母、子女)
            if frontier_a:
                query_ids = tuple(frontier_a)
                # 寻找他们的父母 (father_id, mother_id)
                rows = db.execute(
                    text(f"SELECT member_id, father_id, mother_id FROM members WHERE member_id IN :q_ids"),
                    {"q_ids": query_ids}
                ).fetchall()
                
                # 寻找他们的子女 (作为 father 或 mother 被引用)
                children_rows = db.execute(
                    text(f"SELECT member_id, father_id, mother_id FROM members WHERE father_id IN :q_ids OR mother_id IN :q_ids"),
                    {"q_ids": query_ids}
                ).fetchall()
                
                # 收集邻居关系
                # 对于查询父母的行，邻居是 father_id, mother_id
                for r in rows:
                    m_id, f_id, mo_id = r
                    for par in (f_id, mo_id):
                        if par is not None:
                            if par not in visited_a:
                                visited_a[par] = (m_id, depth + 1)
                                if par in visited_b:
                                    intersect_node = par
                                    break
                                next_frontier_a.add(par)
                    if intersect_node is not None: break
                
                if intersect_node is None:
                    # 对于查询子女的行，邻居是该子节点本身，它的连接点是对应的父亲或母亲
                    for r in children_rows:
                        c_id, f_id, mo_id = r
                        # 判断是通过哪一方连接的
                        for p_id in (f_id, mo_id):
                            if p_id in frontier_a:
                                if c_id not in visited_a:
                                    visited_a[c_id] = (p_id, depth + 1)
                                    if c_id in visited_b:
                                        intersect_node = c_id
                                        break
                                    next_frontier_a.add(c_id)
                        if intersect_node is not None: break

            frontier_a = next_frontier_a
            if intersect_node is not None:
                break

        # ================== 扩展 B 侧 ==================
        if frontier_b:
            next_frontier_b = set()
            if frontier_b:
                query_ids = tuple(frontier_b)
                rows = db.execute(
                    text(f"SELECT member_id, father_id, mother_id FROM members WHERE member_id IN :q_ids"),
                    {"q_ids": query_ids}
                ).fetchall()
                children_rows = db.execute(
                    text(f"SELECT member_id, father_id, mother_id FROM members WHERE father_id IN :q_ids OR mother_id IN :q_ids"),
                    {"q_ids": query_ids}
                ).fetchall()
                
                for r in rows:
                    m_id, f_id, mo_id = r
                    for par in (f_id, mo_id):
                        if par is not None:
                            if par not in visited_b:
                                visited_b[par] = (m_id, depth + 1)
                                if par in visited_a:
                                    intersect_node = par
                                    break
                                next_frontier_b.add(par)
                    if intersect_node is not None: break
                
                if intersect_node is None:
                    for r in children_rows:
                        c_id, f_id, mo_id = r
                        for p_id in (f_id, mo_id):
                            if p_id in frontier_b:
                                if c_id not in visited_b:
                                    visited_b[c_id] = (p_id, depth + 1)
                                    if c_id in visited_a:
                                        intersect_node = c_id
                                        break
                                    next_frontier_b.add(c_id)
                        if intersect_node is not None: break

            frontier_b = next_frontier_b
            if intersect_node is not None:
                break

    if intersect_node is None:
        return None

    # 重建路径
    path_a = []
    node = intersect_node
    while node is not None:
        path_a.append(node)
        node = visited_a[node][0]
    path_a = list(reversed(path_a))

    path_b = []
    node = visited_b[intersect_node][0]
    while node is not None:
        path_b.append(node)
        node = visited_b[node][0]

    return path_a + path_b


# ── 路径标注 ─────────────────────────────────────────────
def _label_path(db, path: list[int]) -> list[dict]:
    """批量查询路径成员信息，标注每个节点的亲缘角色。"""
    placeholders = ",".join([f":id{i}" for i in range(len(path))])
    params = {f"id{i}": v for i, v in enumerate(path)}
    rows = db.execute(
        text(f"SELECT member_id, name, gender, father_id, mother_id "
             f"FROM members WHERE member_id IN ({placeholders})"),
        params
    ).fetchall()
    info = {r[0]: {"name": r[1], "gender": r[2], "father_id": r[3], "mother_id": r[4]}
            for r in rows}

    result = []
    for i, mid in enumerate(path):
        m = info.get(mid, {})
        name = m.get("name", str(mid))
        gender = m.get("gender", "M")

        if i == 0:
            relation = "查询人 A"
        elif i == len(path) - 1:
            relation = "查询人 B"
        else:
            prev_info = info.get(path[i - 1], {})
            if mid in (prev_info.get("father_id"), prev_info.get("mother_id")):
                relation = "父亲" if gender == "M" else "母亲"
            else:
                relation = "儿子" if gender == "M" else "女儿"

        result.append({"member_id": mid, "name": name, "relation": relation})
    return result


# ── 对外主接口 ───────────────────────────────────────────
def find_relationship(db, name_a: str, name_b: str,
                      id_a: int = None, id_b: int = None) -> dict:
    """
    查询 name_a 与 name_b 之间的亲缘关系。
    若提供 id_a/id_b 则跳过姓名查找直接计算。
    同族优先，跨族不存在亲缘关系。
    """
    def _lookup(name):
        rows = db.execute(
            text("SELECT member_id, name, clan_id, generation_num "
                 "FROM members WHERE name = :n"),
            {"n": name}
        ).fetchall()
        return [{"member_id": r[0], "name": r[1], "clan_id": r[2], "gen": r[3]}
                for r in rows]

    # 按姓名查候选
    cands_a = _lookup(name_a) if not id_a else []
    cands_b = _lookup(name_b) if not id_b else []

    # 若已指定 id，直接构造单元素候选列表
    if id_a:
        row = db.execute(
            text("SELECT member_id, name, clan_id, generation_num FROM members WHERE member_id = :id"),
            {"id": id_a}
        ).fetchone()
        cands_a = [{"member_id": row[0], "name": row[1], "clan_id": row[2], "gen": row[3]}] if row else []

    if id_b:
        row = db.execute(
            text("SELECT member_id, name, clan_id, generation_num FROM members WHERE member_id = :id"),
            {"id": id_b}
        ).fetchone()
        cands_b = [{"member_id": row[0], "name": row[1], "clan_id": row[2], "gen": row[3]}] if row else []

    if not cands_a:
        return {"found": False, "message": f"找不到成员[{name_a}]", "path": [],
                "candidates_a": [], "candidates_b": cands_b}
    if not cands_b:
        return {"found": False, "message": f"找不到成员[{name_b}]", "path": [],
                "candidates_a": cands_a, "candidates_b": []}

    # 同族配对优先；跨族直接判定无亲缘
    best_path = None
    best_a = best_b = None

    for ca in cands_a:
        for cb in cands_b:
            if ca["member_id"] == cb["member_id"]:
                continue
            if ca["clan_id"] != cb["clan_id"]:
                continue  # 不同族谱必然无亲缘

            path = _bfs_in_db(db, ca["member_id"], cb["member_id"])
            if path and (best_path is None or len(path) < len(best_path)):
                best_path = path
                best_a, best_b = ca, cb

    if best_path is None:
        return {
            "found": False,
            "message": f"[{name_a}]与[{name_b}]之间未发现亲缘关系（或超出可查范围）",
            "path": [],
            "candidates_a": cands_a if len(cands_a) > 1 else [],
            "candidates_b": cands_b if len(cands_b) > 1 else [],
        }

    labeled = _label_path(db, best_path)
    hops = len(best_path) - 1
    return {
        "found": True,
        "message": f"[{name_a}]与[{name_b}]存在亲缘关系，相距 {hops} 代",
        "path": labeled,
        "candidates_a": cands_a if len(cands_a) > 1 else [],
        "candidates_b": cands_b if len(cands_b) > 1 else [],
    }