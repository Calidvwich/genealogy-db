from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

router = APIRouter()
DB_URL = "postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


# ── 工具函数 ──────────────────────────────────────────────

def get_current_user(request: Request) -> str | None:
    """从 Cookie 中取出当前登录用户的 user_id（字符串）"""
    return request.cookies.get("session_user")


def check_edit_permission(db, clan_id: int, user_id: str) -> bool:
    """
    判断 user_id 是否有权修改 clan_id 这个族谱。
    满足以下任一条件即可：
      1. 是该族谱的创建者（genealogies.creator_id -> users.id）
      2. 在 collaborations 表中存在对应记录
    """
    row = db.execute(
        text("""
            SELECT 1
            FROM genealogies g
            JOIN users u ON u.id = g.creator_id
            WHERE g.clan_id = :cid AND u.user_id = :uid
        """),
        {"cid": clan_id, "uid": user_id}
    ).fetchone()

    if row:
        return True  # 是创建者

    row2 = db.execute(
        text("""
            SELECT 1
            FROM collaborations c
            JOIN users u ON u.id = c.user_id
            WHERE c.clan_id = :cid AND u.user_id = :uid
        """),
        {"cid": clan_id, "uid": user_id}
    ).fetchone()

    return row2 is not None  # 是被授权的协作者


# ── API 端点 ──────────────────────────────────────────────

@router.get("/check/{clan_id}")
def check_permission(clan_id: int, request: Request):
    """
    前端调用此接口判断当前用户对某族谱是否有编辑权。
    返回：{ "can_edit": true/false, "is_owner": true/false }
    """
    current_user = get_current_user(request)
    if not current_user:
        return {"can_edit": False, "is_owner": False}

    db = SessionLocal()
    try:
        # 判断是否是创建者
        owner_row = db.execute(
            text("""
                SELECT 1 FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """),
            {"cid": clan_id, "uid": current_user}
        ).fetchone()
        is_owner = owner_row is not None

        can_edit = is_owner or check_edit_permission(db, clan_id, current_user)
        return {"can_edit": can_edit, "is_owner": is_owner}
    finally:
        db.close()


@router.get("/collaborators/{clan_id}")
def list_collaborators(clan_id: int, request: Request):
    """
    创建者查看某族谱的协作者列表。
    只有创建者本人才能查看。
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        # 验证请求者是创建者
        owner_row = db.execute(
            text("""
                SELECT 1 FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """),
            {"cid": clan_id, "uid": current_user}
        ).fetchone()

        if not owner_row:
            raise HTTPException(status_code=403, detail="只有创建者才能查看协作者列表")

        rows = db.execute(
            text("""
                SELECT u.user_id, u.username
                FROM collaborations c
                JOIN users u ON u.id = c.user_id
                WHERE c.clan_id = :cid
            """),
            {"cid": clan_id}
        ).all()

        return [{"user_id": r[0], "username": r[1]} for r in rows]
    finally:
        db.close()


@router.post("/grant")
def grant_permission(
    request: Request,
    clan_id: int = Form(...),
    target_user_id: str = Form(...)
):
    """
    创建者授权某用户编辑自己的族谱。
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        # 验证请求者是创建者
        owner_row = db.execute(
            text("""
                SELECT g.clan_id FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """),
            {"cid": clan_id, "uid": current_user}
        ).fetchone()

        if not owner_row:
            raise HTTPException(status_code=403, detail="无权操作：你不是该族谱的创建者")

        # 查找被授权用户的 id
        target = db.execute(
            text("SELECT id FROM users WHERE user_id = :uid"),
            {"uid": target_user_id}
        ).fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="目标用户不存在")

        target_id = target[0]

        # 防止重复插入
        exists = db.execute(
            text("SELECT 1 FROM collaborations WHERE clan_id = :cid AND user_id = :uid"),
            {"cid": clan_id, "uid": target_id}
        ).fetchone()

        if exists:
            return JSONResponse(status_code=200, content={"message": "该用户已有编辑权限"})

        db.execute(
            text("INSERT INTO collaborations (clan_id, user_id) VALUES (:cid, :uid)"),
            {"cid": clan_id, "uid": target_id}
        )
        db.commit()
        return {"message": f"已成功授权 {target_user_id} 编辑此族谱"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/revoke")
def revoke_permission(
    request: Request,
    clan_id: int = Form(...),
    target_user_id: str = Form(...)
):
    """
    创建者撤销某用户的编辑权限。
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        # 验证请求者是创建者
        owner_row = db.execute(
            text("""
                SELECT 1 FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """),
            {"cid": clan_id, "uid": current_user}
        ).fetchone()

        if not owner_row:
            raise HTTPException(status_code=403, detail="无权操作：你不是该族谱的创建者")

        target = db.execute(
            text("SELECT id FROM users WHERE user_id = :uid"),
            {"uid": target_user_id}
        ).fetchone()

        if not target:
            raise HTTPException(status_code=404, detail="目标用户不存在")

        db.execute(
            text("DELETE FROM collaborations WHERE clan_id = :cid AND user_id = :uid"),
            {"cid": clan_id, "uid": target[0]}
        )
        db.commit()
        return {"message": f"已撤销 {target_user_id} 的编辑权限"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()