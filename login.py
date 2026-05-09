from fastapi import APIRouter, Form, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 配置加密方式
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 定义路由
router = APIRouter()
DB_URL = "postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

@router.post("/login")
async def login(response: Response, user_id: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        # 1. 从数据库获取该用户的哈希密码
        user = db.execute(
            text("SELECT password_hash FROM users WHERE user_id = :uid"), 
            {"uid": user_id}
        ).fetchone()

        # 2. 用户不存在检查
        if not user:
            return JSONResponse(status_code=401, content={"message": "用户名或密码错误"})

        # 3. 【核心修改】使用 verify 函数进行安全比对
        # 注意：这里也要对输入密码进行 [:72] 截断，确保与注册时逻辑一致
        input_password = password[:72]
        db_hash = user[0]

        if not pwd_context.verify(input_password, db_hash):
            return JSONResponse(status_code=401, content={"message": "用户名或密码错误"})

        # 4. 验证通过，设置 Cookie
        res = JSONResponse(content={"message": "登录成功"})
        res.set_cookie(key="session_user", value=user_id, httponly=True, path="/")
        return res
    except Exception as e:
        print(f"Login Error: {e}")
        return JSONResponse(status_code=500, content={"message": "服务器内部错误"})
    finally:
        db.close()

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_user")
    return response


@router.get("/me")
async def me(request: Request):
    """前端用来检查 httponly cookie 是否存在（即是否已登录）"""
    user_id = request.cookies.get("session_user")
    if user_id:
        return JSONResponse(status_code=200, content={"user_id": user_id})
    return JSONResponse(status_code=401, content={"message": "未登录"})