"""
search.py — 亲缘关系查询模块（内存图加速版）

核心优化：把某一族谱的完整父子关系一次性加载进内存邻接表，
再在内存中做 BFS，避免逐步查询数据库导致的严重性能问题。

对外接口：
    find_relationship(db, name_a, name_b) -> dict
"""

from sqlalchemy import text
from collections import deque


# ── 内存图构建 ───────────────────────────────────────────
def _build_graph(db, clan_id: int) -> dict[int, list[int]]:
    """
    一次性从数据库读取指定族谱所有成员的父子关系，
    构建无向邻接表 {member_id: [neighbor_id, ...]}。
    """
    rows = db.execute(
        text("SELECT member_id, father_id, mother_id FROM members WHERE clan_id = :cid"),
        {"cid": clan_id}
    ).fetchall()

    graph: dict[int, list[int]] = {}
    for member_id, father_id, mother_id in rows:
        if member_id not in graph:
            graph[member_id] = []
        for parent_id in (father_id, mother_id):
            if parent_id is not None:
                graph[member_id].append(parent_id)
                if parent_id not in graph:
                    graph[parent_id] = []
                graph[parent_id].append(member_id)
    return graph


# ── 内存 BFS ─────────────────────────────────────────────
def _bfs_in_graph(graph: dict, id_a: int, id_b: int) -> list[int] | None:
    """在内存邻接表上做 BFS，返回最短路径节点列表，找不到返回 None。"""
    if id_a == id_b:
        return [id_a]
    if id_a not in graph or id_b not in graph:
        return None

    visited = {id_a: None}
    queue = deque([id_a])

    while queue:
        cur = queue.popleft()
        for nb in graph.get(cur, []):
            if nb not in visited:
                visited[nb] = cur
                if nb == id_b:
                    path = []
                    node = id_b
                    while node is not None:
                        path.append(node)
                        node = visited[node]
                    return list(reversed(path))
                queue.append(nb)
    return None


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
    _graph_cache: dict[int, dict] = {}  # clan_id -> graph，避免同族多次查询

    for ca in cands_a:
        for cb in cands_b:
            if ca["member_id"] == cb["member_id"]:
                continue
            if ca["clan_id"] != cb["clan_id"]:
                continue  # 不同族谱必然无亲缘

            cid = ca["clan_id"]
            if cid not in _graph_cache:
                _graph_cache[cid] = _build_graph(db, cid)
            graph = _graph_cache[cid]

            path = _bfs_in_graph(graph, ca["member_id"], cb["member_id"])
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