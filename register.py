from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 数据库配置 (请确保与 main.py 一致)
DB_URL = "postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 【关键】定义 router 对象，供 main.py 导入
router = APIRouter()

@router.get("/page", response_class=HTMLResponse)
async def register_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>武大族谱系统 - 注册</title>
        <style>
            body { font-family: 'PingFang SC', sans-serif; background: #0f172a; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .card { background: white; padding: 40px; border-radius: 12px; width: 320px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
            input { width: 100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 15px; box-sizing: border-box; outline: none; }
            input:focus { border-color: #2563eb; }
            .btn { width: 100%; background: #10b981; color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: bold; }
            .msg { text-align: center; font-size: 13px; min-height: 20px; margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="text-align:center; color:#2563eb;">创建账号</h2>
            <div id="msg" class="msg"></div>
            <input type="text" id="uid" placeholder="用户名 / 账号">
            <input type="password" id="pwd" placeholder="设置密码">
            <input type="text" id="uname" placeholder="真实姓名">
            <button class="btn" onclick="submitRegister()">立即注册</button>
            <p style="text-align:center; font-size:12px; color:#64748b; margin-top:15px;">
                已有账号？<a href="/" style="color:#2563eb; text-decoration:none;">返回登录</a>
            </p>
        </div>
        <script>
            async function submitRegister() {
                const uid = document.getElementById('uid').value;
                const pwd = document.getElementById('pwd').value;
                const uname = document.getElementById('uname').value;
                const msgBox = document.getElementById('msg');

                // 1. 检查未填写内容
                if (!uid || !pwd) {
                    msgBox.style.color = "#ef4444";
                    msgBox.innerText = "有未填写的内容";
                    return;
                }

                const formData = new FormData();
                formData.append('user_id', uid);
                formData.append('username', uname);
                formData.append('password', pwd);

                try {
                    const res = await fetch('/register/do', { method: 'POST', body: formData });
                    const data = await res.json();
                    
                    if (res.ok) {
                        msgBox.style.color = "#10b981";
                        msgBox.innerText = "账号注册成功，即将跳转至登陆页面";
                        setTimeout(() => { window.location.href = "/"; }, 2000);
                    } else {
                        msgBox.style.color = "#ef4444";
                        // 2. 处理用户名重复提示
                        if (data.detail === "ALREADY_EXISTS") {
                            msgBox.innerText = "注册失败，用户名重复";
                        } else {
                            msgBox.innerText = data.detail || "注册失败";
                        }
                    }
                } catch (e) {
                    msgBox.innerText = "服务器连接异常";
                }
            }
        </script>
    </body>
    </html>
    """

# register.py 核心修改点
@router.post("/do")
async def do_register(
    user_id: str = Form(...), 
    password: str = Form(...), 
    username: str = Form("")
):
    db = SessionLocal()
    try:
        # 截断处理（虽然你的 1234567890 没超标，但加上可以防止脏数据报错）
        safe_password = password[:72] 

        # 重点检查：这里必须是对明文 safe_password 进行 hash
        # 确保没有在循环里调用它，或者误传了别的变量
        hashed_pwd = pwd_context.hash(safe_password)

        # 插入数据库
        db.execute(
            text("INSERT INTO users (user_id, username, password_hash) VALUES (:u, :n, :p)"),
            {"u": user_id, "n": username, "p": hashed_pwd}
        )
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        # 这里会打印出导致 72 bytes 报错的真实原因
        print(f"DEBUG: 报错详情 -> {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()