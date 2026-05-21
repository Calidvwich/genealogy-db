from fastapi import FastAPI, HTTPException, Depends, Cookie, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import Optional
import base64, os, time, tracemalloc
from login import router as auth_router
from register import router as register_router
from permissions import router as perm_router, check_edit_permission
from search import find_relationship

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
app.include_router(register_router, prefix="/register")
app.include_router(perm_router, prefix="/permissions")

# 启动时读取默认头像，转为 data URI
def _load_default_pic() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "resources", "defaultpic.jpg")
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
    except FileNotFoundError:
        return ""

DEFAULT_PIC_DATA_URI = _load_default_pic()

DB_URL = "postgresql://postgres:Xjz20041119@127.0.0.1:5432/genealogy_db"
engine = create_engine(DB_URL, connect_args={'options': '-c client_encoding=utf8'})
SessionLocal = sessionmaker(bind=engine)


# ---------------------------------------------------------
# 首页
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session_user = request.cookies.get("session_user")
    login_display = "flex"
    admin_display = "none"
    if session_user:
        login_display = "none"
        admin_display = "flex"

    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>族谱系统</title>
            <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
            <style>
                :root {{ --primary: #2563eb; --bg: #f1f5f9; --danger: #ef4444; --success: #10b981; }}
                body {{ font-family: 'PingFang SC', sans-serif; margin: 0; background: var(--bg); height: 100vh; overflow: hidden; }}

                #loginOverlay {{
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: #0f172a; display: {login_display}; align-items: center; justify-content: center;
                    z-index: 10000;
                }}
                .login-card {{ background: white; padding: 40px; border-radius: 12px; width: 320px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }}

                #adminContent {{ display: {admin_display}; height: 100vh; flex-direction: column; }}

                .navbar {{ background: white; padding: 0 24px; height: 60px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
                .mode-switch {{ display: flex; align-items: center; gap: 6px; font-size: 13px; color: #475569; margin-right: 15px; border: 1px solid #e2e8f0; padding: 4px 10px; border-radius: 20px; background: #f8fafc; cursor: pointer; user-select: none; }}
                .mode-switch input {{ margin: 0; width: auto; cursor: pointer; }}
                .main-container {{ flex: 1; display: flex; padding: 15px; gap: 15px; overflow: hidden; box-sizing: border-box; }}
                .card {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); box-sizing: border-box; }}
                .side-panel {{ width: 360px; display: flex; flex-direction: column; gap: 15px; height: 100%; overflow: hidden; }}
                .viz-panel {{ flex: 1; background: white; border-radius: 12px; height: 100%; position: relative; }}
                input, select {{ width: 100%; padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; outline: none; margin-bottom: 10px; box-sizing: border-box; font-size: 13px; }}
                .btn-add {{ width: 100%; background: var(--success); color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: bold; }}
                .btn-primary {{ background: var(--primary); color: white; border: none; padding: 0 15px; border-radius: 6px; cursor: pointer; height: 38px; }}
                .btn-danger {{ background: var(--danger); color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
                .btn-sm {{ background: var(--primary); color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
                .pwd-container {{ position: relative; width: 100%; }}
                .eye-btn {{ position: absolute; right: 10px; top: 12px; cursor: pointer; opacity: 0.6; }}
                .search-results {{ flex: 1; overflow-y: auto; margin-top: 10px; }}
                .member-item {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid #f1f5f9; margin-bottom: 6px; border-radius: 8px; transition: 0.2s; }}
                .member-item:hover {{ background: #f8fbff; border-color: var(--primary); }}
                .member-item-left {{ cursor: pointer; flex: 1; }}

                /* 模态框通用样式 */
                .modal-overlay {{
                    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,0.5); z-index: 9000; align-items: center; justify-content: center;
                }}
                .modal-overlay.active {{ display: flex; }}
                .modal-box {{
                    background: white; border-radius: 12px; padding: 28px; width: 420px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.2); max-height: 80vh; overflow-y: auto;
                }}
                .modal-box h3 {{ margin: 0 0 18px 0; color: #1e293b; }}
                .modal-footer {{ display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end; }}
                .btn-cancel {{ background: #e2e8f0; color: #475569; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }}
                label {{ font-size: 12px; color: #64748b; margin-bottom: 3px; display: block; }}

                /* 授权管理面板 */
                .collab-item {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: #f8fafc; border-radius: 6px; margin-bottom: 6px; font-size: 13px; }}

                /* 权限标签 */
                .badge {{ font-size: 11px; padding: 2px 7px; border-radius: 10px; font-weight: 500; }}
                .badge-owner {{ background: #fef3c7; color: #92400e; }}
                .badge-collab {{ background: #dbeafe; color: #1e40af; }}
                .badge-readonly {{ background: #f1f5f9; color: #94a3b8; }}
                .clan-item {{ padding:10px 12px; border:1px solid #f1f5f9; margin-bottom:6px; border-radius:8px; }}
                .clan-item-header {{ display:flex; justify-content:space-between; align-items:center; }}
                .clan-item-title {{ font-weight:600; font-size:13px; color:#1e293b; }}
                .clan-item-sub {{ font-size:11px; color:#94a3b8; margin-top:2px; }}
                .clan-collab-panel {{ display:none; margin-top:8px; padding-top:8px; border-top:1px solid #f1f5f9; }}
                .clan-collab-panel.open {{ display:block; }}
                .collab-row {{ display:flex; justify-content:space-between; align-items:center; padding:4px 0; font-size:12px; color:#475569; }}
                .grant-row {{ display:flex; gap:6px; margin-top:8px; }}
                .grant-row input {{ margin:0; padding:6px 8px; font-size:12px; height:32px; }}
                .grant-row button {{ white-space:nowrap; height:32px; padding:0 10px; font-size:12px; }}
                /* 婚姻记录 */
                .marriage-item {{ display:flex; justify-content:space-between; align-items:center; padding:8px 10px; background:#fefce8; border:1px solid #fde68a; border-radius:6px; margin-bottom:6px; font-size:12px; }}
                .marriage-item .spouse-name {{ font-weight:600; color:#92400e; }}
                /* 查询结果表格 */
                .query-result-table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
                .query-result-table th {{ background:#2563eb; color:white; padding:6px 8px; text-align:left; font-weight:600; }}
                .query-result-table td {{ padding:5px 8px; border-bottom:1px solid #f1f5f9; color:#475569; }}
                .query-result-table tr:nth-child(even) td {{ background:#f8fafc; }}
            </style>
        </head>
        <body>
            <!-- 登录遮罩 -->
            <div id="loginOverlay">
                <div class="login-card">
                    <h2 style="text-align:center; color:var(--primary); margin-bottom:20px">系统登录</h2>
                    <input type="text" id="login_uid" placeholder="账号">
                    <div class="pwd-container">
                        <input type="password" id="login_pwd" placeholder="密码">
                        <span class="eye-btn" onclick="togglePassword()">👁️</span>
                        <p style="text-align:center; font-size:12px; color:#64748b; margin-top:15px;">
                            没有帐户？<a href="/register/page" style="color:var(--primary); text-decoration:none;">点击注册</a>
                        </p>
                    </div>
                    <div id="loginMsg" style="text-align:center; font-size:13px; min-height:20px; margin: 10px 0;"></div>
                    <button class="btn-add" onclick="handleLogin()">进入系统</button>
                </div>
            </div>

            <!-- 主界面 -->
            <div id="adminContent">
                <div class="navbar">
                    <div style="font-weight:bold; color:var(--primary); font-size: 1.2rem;">族谱管理系统</div>
                        <div style="color: #64748b; font-size: 13px;">{session_user or '访客'} | 已登录</div>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <label class="mode-switch" title="开启后显示SQL执行性能指标">
                            <input type="checkbox" id="perfModeToggle">
                            <span>性能模式</span>
                        </label>
                        <button id="btn-collab-current" onclick="openCurrentClanCollab()" style="display:none; background:#7c3aed; color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px; padding:4px 10px;">👥 管理协作者</button>
                        <button onclick="toggleClanView()" style="background:var(--primary); color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px; padding:4px 10px;">📚 我的族谱</button>
                        <button onclick="openQueryModal()" style="background:#0891b2; color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px; padding:4px 10px;">📊 统计查询</button>
                        <button onclick="logout()" style="background:none; border:1px solid #ccc; border-radius:4px; cursor:pointer; font-size:12px; padding:2px 8px">退出</button>
                    </div>
                </div>
                <div class="main-container">
                    <div class="side-panel">
                        <div class="card">
                            <h4 style="margin:0 0 10px 0">数据概览</h4>
                            <div id="chart-clan-label" style="font-size:11px; color:#94a3b8; margin-bottom:4px; text-align:center;">全库统计</div>
                            <div id="stats-chart" style="height:130px"></div>
                        </div>
                        <div class="card" style="flex:1; display:flex; flex-direction:column; overflow:hidden;">
                            <!-- 搜索视图（默认显示） -->
                            <div id="search-view" style="display:flex; flex-direction:column; flex:1; overflow:hidden;">
                                <!-- Tab 切换 -->
                                <div style="display:flex; gap:4px; margin-bottom:10px;">
                                    <button id="tab-search" onclick="switchTab('search')"
                                        style="flex:1; padding:6px; border:none; border-radius:6px; cursor:pointer; font-size:12px; background:var(--primary); color:white; font-weight:600;">
                                        成员查询
                                    </button>
                                    <button id="tab-relation" onclick="switchTab('relation')"
                                        style="flex:1; padding:6px; border:none; border-radius:6px; cursor:pointer; font-size:12px; background:#e2e8f0; color:#475569;">
                                        查询关系
                                    </button>
                                </div>

                                <!-- 成员查询面板 -->
                                <div id="panel-search" style="display:flex; flex-direction:column; flex:1; overflow:hidden;">
                                    <div style="display:flex; gap:8px">
                                        <input type="text" id="nameInput" placeholder="输入姓名查询..." style="margin:0">
                                        <button class="btn-primary" onclick="search()">查询</button>
                                        <button class="btn-primary" style="background:var(--success);" onclick="openModal('addMemberModal')">添加</button>
                                    </div>
                                    <div id="search-msg" style="font-size:12px; min-height:18px; color:#475569; margin-top:6px;"></div>
                                    <div class="search-results" id="search-results"></div>
                                </div>

                                <!-- 查询关系面板 -->
                                <div id="panel-relation" style="display:none; flex-direction:column; flex:1; overflow:hidden;">
                                    <input type="text" id="relNameA" placeholder="成员 A 姓名" style="margin-bottom:6px;">
                                    <input type="text" id="relNameB" placeholder="成员 B 姓名" style="margin-bottom:8px;">
                                    <button class="btn-primary" onclick="queryRelation()" style="width:100%; height:36px; margin-bottom:8px;">查询亲缘关系</button>
                                    <div id="relation-msg" style="font-size:12px; min-height:18px; color:#475569; margin-bottom:6px;"></div>
                                    <div id="relation-result" style="overflow-y:auto; flex:1;"></div>
                                </div>
                            </div>
                            <!-- 族谱列表视图（默认隐藏） -->
                            <div id="clan-view" style="display:none; flex-direction:column; flex:1; overflow:hidden;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                    <span style="font-size:13px; font-weight:600; color:#1e293b;">我创建/协作的族谱</span>
                                    <div>
                                        <button onclick="openModal('addGenealogyModal')" style="background:var(--success); color:white; border:none; border-radius:4px; padding:2px 6px; font-size:12px; cursor:pointer;">新建</button>
                                        <button onclick="toggleClanView()" style="background:none; border:none; cursor:pointer; color:#94a3b8; font-size:18px; padding:0; margin-left:4px;">✕</button>
                                    </div>
                                </div>
                                <div id="clan-list" style="overflow-y:auto; flex:1;"></div>
                            </div>
                        </div>
                    </div>
                    <div class="viz-panel">
                        <div id="chart-container" style="width:100%; height:100%"></div>
                    </div>
                </div>
            </div>

            <!-- ① 编辑成员模态框 -->
            <div class="modal-overlay" id="editModal">
                <div class="modal-box">
                    <h3>✏️ 编辑成员信息</h3>
                    <input type="hidden" id="edit_member_id">

                    <!-- 照片区域 -->
                    <div style="display:flex; align-items:center; gap:14px; margin-bottom:14px; padding:12px; background:#f8fafc; border-radius:8px;">
                        <img id="edit_pic_preview" src="" data-default="1"
                             style="width:72px; height:72px; border-radius:8px; object-fit:cover; border:2px solid #e2e8f0; flex-shrink:0; background:#f1f5f9;"
                             onerror="this.src=''; this.style.background='#f1f5f9';">
                        <div>
                            <div style="font-size:12px; color:#64748b; margin-bottom:6px;">成员照片</div>
                            <input type="file" id="edit_pic_input" accept=".jpg,.jpeg,.png" style="display:none;" onchange="previewAndUploadPic()">
                            <button type="button" class="btn-sm" onclick="document.getElementById('edit_pic_input').click()">📷 修改照片</button>
                            <div id="pic_upload_msg" style="font-size:11px; margin-top:4px; min-height:14px; color:#94a3b8;"></div>
                        </div>
                    </div>

                    <label>姓名</label>
                    <input type="text" id="edit_name" placeholder="成员姓名">
                    <label>性别</label>
                    <select id="edit_gender">
                        <option value="M">男</option>
                        <option value="F">女</option>
                    </select>
                    <label>出生年份</label>
                    <input type="number" id="edit_birth" placeholder="如 1980">
                    <label>去世年份（未去世留空）</label>
                    <input type="number" id="edit_death" placeholder="如 2050">
                    <label>简介</label>
                    <input type="text" id="edit_bio" placeholder="简短描述">

                    <!-- 亲属关系（有编辑权限时显示） -->
                    <div id="parent-section" style="display:none; margin-top:10px; padding-top:10px; border-top:1px solid #f1f5f9;">
                        <div style="font-size:13px; font-weight:600; color:#1e293b; margin-bottom:8px;">👪 亲属关系</div>
                        <div style="font-size:11px; color:#94a3b8; margin-bottom:8px;">必须是同族谱成员姓名且唯一，留空表示清除该关系</div>
                        <label>父亲姓名</label>
                        <input type="text" id="edit_father" placeholder="可留空">
                        <label>母亲姓名</label>
                        <input type="text" id="edit_mother" placeholder="可留空">
                    </div>

                    <div id="editMsg" style="font-size:13px; min-height:18px; color:var(--danger); margin-top:6px;"></div>

                    <!-- 婚姻管理（有编辑权限时显示） -->
                    <div id="marriage-section" style="display:none; margin-top:14px; padding-top:12px; border-top:1px solid #f1f5f9;">
                        <div style="font-size:13px; font-weight:600; color:#1e293b; margin-bottom:8px;">💍 婚姻记录</div>
                        <div id="marriage-list"></div>
                        <div style="font-size:12px; color:#64748b; margin:8px 0 4px;">登记新婚姻：</div>
                        <div style="display:flex; gap:6px; margin-bottom:4px;">
                            <input type="text" id="marriage-spouse-name" placeholder="配偶姓名" style="margin:0; height:32px; font-size:12px; flex:1;">
                            <input type="number" id="marriage-marry-year" placeholder="结婚年份" style="margin:0; width:100px; height:32px; font-size:12px; flex-shrink:0;">
                        </div>
                        <button class="btn-primary" onclick="addMarriage()" style="width:100%; height:32px; font-size:12px; margin-bottom:4px;">＋ 登记婚姻</button>
                        <div id="marriage-msg" style="font-size:12px; min-height:14px;"></div>
                    </div>

                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('editModal')">取消</button>
                        <button class="btn-primary" onclick="submitEdit()">保存修改</button>
                    </div>
                </div>
            </div>

            <!-- ② 删除成员确认框 -->
            <div class="modal-overlay" id="deleteModal">
                <div class="modal-box">
                    <h3>🗑️ 确认删除</h3>
                    <p style="color:#475569; font-size:14px;">确定要删除成员 <strong id="delete_member_name"></strong> 吗？此操作不可撤销。</p>
                    <input type="hidden" id="delete_member_id">
                    <div id="deleteMsg" style="font-size:13px; min-height:18px; color:var(--danger);"></div>
                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('deleteModal')">取消</button>
                        <button class="btn-danger" onclick="submitDelete()">确认删除</button>
                    </div>
                </div>
            </div>

            <!-- ③ 授权管理模态框（仅创建者可见） -->
            <div class="modal-overlay" id="collabModal">
                <div class="modal-box">
                    <h3>👥 协作者管理</h3>
                    <p style="font-size:13px; color:#64748b; margin-top:0;">授权其他用户编辑此族谱（clan_id: <span id="collab_clan_id_label"></span>）</p>
                    <label>授权用户账号</label>
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="grant_user_input" placeholder="输入对方账号" style="margin:0">
                        <button class="btn-primary" onclick="grantAccess()" style="white-space:nowrap;">授权</button>
                    </div>
                    <div id="grantMsg" style="font-size:13px; min-height:18px; margin: 8px 0; color:var(--success);"></div>
                    <div id="collabList" style="margin-top:12px;"></div>
                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('collabModal')">关闭</button>
                    </div>
                </div>
            </div>

            <!-- ⑤ 统计查询模态框 -->
            <div class="modal-overlay" id="queryModal">
                <div class="modal-box" style="width:600px; max-width:95vw;">
                    <h3>📊 统计查询</h3>
                    <!-- 查询类型 Tab -->
                    <div style="display:flex; gap:4px; margin-bottom:14px; flex-wrap:wrap;">
                        <button id="qt-spouse"    onclick="switchQueryTab('spouse')"    class="btn-primary" style="font-size:11px; padding:4px 8px;">配偶/子女</button>
                        <button id="qt-ancestors" onclick="switchQueryTab('ancestors')" style="font-size:11px; padding:4px 8px; border:1px solid #e2e8f0; border-radius:4px; background:#f8fafc;">历代祖先</button>
                        <button id="qt-longevity" onclick="switchQueryTab('longevity')" style="font-size:11px; padding:4px 8px; border:1px solid #e2e8f0; border-radius:4px; background:#f8fafc;">最长寿一代</button>
                        <button id="qt-singles"   onclick="switchQueryTab('singles')"   style="font-size:11px; padding:4px 8px; border:1px solid #e2e8f0; border-radius:4px; background:#f8fafc;">50+单身男性</button>
                        <button id="qt-early"     onclick="switchQueryTab('early')"     style="font-size:11px; padding:4px 8px; border:1px solid #e2e8f0; border-radius:4px; background:#f8fafc;">早于均值出生</button>
                        <button id="qt-descendants" onclick="switchQueryTab('descendants')" style="font-size:11px; padding:4px 8px; border:1px solid #e2e8f0; border-radius:4px; background:#f8fafc;">四代曾孙</button>
                    </div>

                    <!-- 配偶/子女 -->
                    <div id="qp-spouse" style="display:block;">
                        <input type="text" id="q-spouse-name" placeholder="输入成员姓名" style="margin-bottom:6px;">
                        <button class="btn-primary" onclick="runQuery('spouse')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-spouse"></div>
                    </div>
                    <!-- 历代祖先 -->
                    <div id="qp-ancestors" style="display:none;">
                        <input type="text" id="q-ancestors-name" placeholder="输入成员姓名" style="margin-bottom:6px;">
                        <button class="btn-primary" onclick="runQuery('ancestors')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-ancestors"></div>
                    </div>
                    <!-- 最长寿一代 -->
                    <div id="qp-longevity" style="display:none;">
                        <select id="q-longevity-clan" style="margin-bottom:6px;">
                            <option value="">选择族谱...</option>
                        </select>
                        <button class="btn-primary" onclick="runQuery('longevity')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-longevity"></div>
                    </div>
                    <!-- 50+单身男性 -->
                    <div id="qp-singles" style="display:none;">
                        <select id="q-singles-clan" style="margin-bottom:6px;">
                            <option value="">全部族谱</option>
                        </select>
                        <button class="btn-primary" onclick="runQuery('singles')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-singles"></div>
                    </div>
                    <!-- 早于均值出生 -->
                    <div id="qp-early" style="display:none;">
                        <select id="q-early-clan" style="margin-bottom:6px;">
                            <option value="">全部族谱</option>
                        </select>
                        <button class="btn-primary" onclick="runQuery('early')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-early" style="max-height:300px; overflow-y:auto;"></div>
                    </div>
                    <!-- 四代曾孙 -->
                    <div id="qp-descendants" style="display:none;">
                        <input type="text" id="q-descendants-name" placeholder="输入曾祖/曾祖母的成员姓名" style="margin-bottom:6px;">
                        <button class="btn-primary" onclick="runQuery('descendants')" style="width:100%; height:34px; font-size:13px; margin-bottom:8px;">查询</button>
                        <div id="qr-descendants" style="max-height:300px; overflow-y:auto;"></div>
                    </div>

                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('queryModal')">关闭</button>
                    </div>
                </div>
            </div>

            <!-- ⑥ 新建族谱模态框 -->
            <div class="modal-overlay" id="addGenealogyModal">
                <div class="modal-box">
                    <h3>📚 新建族谱</h3>
                    <label>族谱标题</label>
                    <input type="text" id="add_gen_title" placeholder="如：李氏家谱">
                    <label>家族姓氏</label>
                    <input type="text" id="add_gen_surname" placeholder="如：李">
                    <div id="addGenMsg" style="font-size:13px; min-height:18px; color:var(--danger);"></div>
                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('addGenealogyModal')">取消</button>
                        <button class="btn-primary" onclick="submitAddGenealogy()">确认创建</button>
                    </div>
                </div>
            </div>

            <!-- ⑦ 添加成员模态框 -->
            <div class="modal-overlay" id="addMemberModal">
                <div class="modal-box" style="max-height:85vh; overflow-y:auto;">
                    <h3>👤 添加族谱成员</h3>
                    <label>选择族谱</label>
                    <select id="add_member_clan">
                        <option value="">加载中...</option>
                    </select>
                    <label>姓名</label>
                    <input type="text" id="add_member_name" placeholder="成员姓名">
                    <label>性别</label>
                    <select id="add_member_gender">
                        <option value="M">男</option>
                        <option value="F">女</option>
                    </select>
                    <label>出生年份</label>
                    <input type="number" id="add_member_birth" placeholder="如 1980">
                    <label>去世年份（未去世留空）</label>
                    <input type="number" id="add_member_death" placeholder="如 2050">
                    <label>简介</label>
                    <input type="text" id="add_member_bio" placeholder="简短描述">
                    <div style="border-top:1px solid #f1f5f9; margin:10px 0; padding-top:10px;">
                        <span style="font-size:12px; font-weight:600; color:#1e293b;">亲属关系 (选填，必须是同族谱名字且唯一)</span>
                        <label>父亲姓名</label>
                        <input type="text" id="add_member_father" placeholder="可留空">
                        <label>母亲姓名</label>
                        <input type="text" id="add_member_mother" placeholder="可留空">
                    </div>

                    <div id="addMemberMsg" style="font-size:13px; min-height:18px; color:var(--danger);"></div>
                    <div class="modal-footer">
                        <button class="btn-cancel" onclick="closeModal('addMemberModal')">取消</button>
                        <button class="btn-primary" onclick="submitAddMember()">确认添加</button>
                    </div>
                </div>
            </div>

            <script>
                let myChart, pieChart;
                let DEFAULT_PIC = '';  // 启动时从 /api/default_pic 加载
                // 当前选中成员的 clan_id（用于权限检查和授权管理）
                let currentClanId = null;
                // 当前用户对 currentClanId 的权限
                let currentPerm = {{ can_edit: false, is_owner: false }};

                window.onload = () => {{
                    const hasCookie = document.cookie.includes("session_user=");
                    if (hasCookie) {{
                        initCharts();
                    }} else {{
                        document.getElementById('adminContent').style.display = 'none';
                        document.getElementById('loginOverlay').style.display = 'flex';
                    }}
                }};

                function showAdmin() {{
                    document.getElementById('loginOverlay').style.display = 'none';
                    document.getElementById('adminContent').style.display = 'flex';
                    initCharts();
                }}

                async function initCharts() {{
                    // 预加载默认头像 data URI
                    try {{
                        const r = await fetch('/api/default_pic');
                        const d = await r.json();
                        DEFAULT_PIC = d.url || '';
                    }} catch(e) {{}}
                    setTimeout(() => {{
                        if (!myChart) myChart = echarts.init(document.getElementById('chart-container'));
                        if (!pieChart) pieChart = echarts.init(document.getElementById('stats-chart'));
                        updateDashboard();
                        loadClanList();
                    }}, 100);
                }}

                async function handleLogin() {{
                    const uid = document.getElementById('login_uid').value;
                    const pwd = document.getElementById('login_pwd').value;
                    const msg = document.getElementById('loginMsg');
                    const formData = new FormData();
                    formData.append('user_id', uid);
                    formData.append('password', pwd);
                    try {{
                        msg.innerText = "验证中...";
                        const res = await fetch('/auth/login', {{ method: 'POST', body: formData }});
                        if (res.ok) {{
                            msg.style.color = "var(--success)"; msg.innerText = "登录成功";
                            setTimeout(showAdmin, 500);
                        }} else {{
                            msg.style.color = "var(--danger)"; msg.innerText = "账号或密码错误";
                        }}
                    }} catch (e) {{ msg.innerText = "服务器连接异常"; }}
                }}

                async function logout() {{
                    await fetch('/auth/logout', {{ method: 'GET' }});
                    window.location.href = '/';
                }}

                async function updateDashboard(clanId) {{
                    const url = clanId ? `/api/dashboard?clan_id=${{clanId}}` : '/api/dashboard';
                    const res = await fetch(url);
                    const data = await res.json();

                    const M = data.gender_ratio.M || 0;
                    const F = data.gender_ratio.F || 0;
                    const total = M + F;
                    const pM = total > 0 ? (M / total * 100).toFixed(2) : '0.00';
                    const pF = total > 0 ? (F / total * 100).toFixed(2) : '0.00';

                    // 更新标签
                    const labelEl = document.getElementById('chart-clan-label');
                    if (labelEl) {{
                        labelEl.innerText = clanId
                            ? `族谱 ${{clanId}} · 共 ${{total}} 人`
                            : `全库统计 · 共 ${{total}} 人`;
                    }}

                    pieChart.setOption({{
                        tooltip: {{
                            trigger: 'item',
                            formatter: p => `${{p.name}}<br>${{p.value}} 人 (${{p.percent.toFixed(2)}}%)`
                        }},
                        legend: {{ show: false }},
                        series: [{{
                            type: 'pie',
                            radius: ['38%', '65%'],
                            label: {{
                                show: true,
                                fontSize: 11,
                                formatter: p => `${{p.name}}\n${{p.value}}人\n${{p.percent.toFixed(2)}}%`
                            }},
                            data: [
                                {{ value: M, name: '男', itemStyle: {{ color: '#2563eb' }} }},
                                {{ value: F, name: '女', itemStyle: {{ color: '#10b981' }} }}
                            ]
                        }}]
                    }});
                }}

                async function search() {{
                    const name = document.getElementById('nameInput').value.trim();
                    const msgEl = document.getElementById('search-msg');
                    const resultsEl = document.getElementById('search-results');
                    
                    if (!name) {{
                        msgEl.style.color = 'var(--danger)';
                        msgEl.innerText = '请输入要查询的姓名';
                        resultsEl.innerHTML = '';
                        return;
                    }}
                    
                    msgEl.style.color = '#94a3b8';
                    msgEl.innerText = '查询中请稍后...';
                    resultsEl.innerHTML = '';

                    try {{
                        const isPerf = document.getElementById('perfModeToggle').checked;
                        const res = await fetch(`/members/search?name=${{encodeURIComponent(name)}}&perf_mode=${{isPerf ? 'true' : 'false'}}`);
                        const data = await res.json();
                        
                        if (data && data.length > 0) {{
                            msgEl.style.color = 'var(--success)';
                            msgEl.innerText = '查询成功';
                            if (data[0].perf_log) {{
                                msgEl.innerText = `查询成功 | ${{data[0].perf_log}}`;
                            }}
                            let html = '';
                            data.forEach(m => {{
                                html += `
                                <div class="member-item">
                                    <div class="member-item-left" onclick="loadTree(${{m.id}}, ${{m.clan_id}})">
                                        <strong>${{m.name}}</strong>
                                        <small style="margin-left:8px; color:#94a3b8;">第${{m.gen}}代</small>
                                    </div>
                                    <div style="display:flex;gap:4px;align-items:center;" id="actions-${{m.id}}">
                                        <!-- 按钮由 loadPermBadge 填充 -->
                                    </div>
                                </div>`;
                            }});
                            resultsEl.innerHTML = html;
                            // 异步加载每个成员的权限标签/按钮
                            data.forEach(m => loadPermBadge(m.id, m.clan_id));
                        }} else {{
                            msgEl.style.color = 'var(--danger)';
                            msgEl.innerText = '查询失败，未检索到对象';
                        }}
                    }} catch (e) {{
                        msgEl.style.color = 'var(--danger)';
                        msgEl.innerText = '查询失败，网络或服务器异常';
                    }}
                }}

                // 为搜索结果中的每条成员加载权限状态
                async function loadPermBadge(memberId, clanId) {{
                    const res = await fetch(`/permissions/check/${{clanId}}`);
                    const perm = await res.json();
                    const el = document.getElementById(`actions-${{memberId}}`);
                    if (!el) return;
                    if (perm.is_owner) {{
                        el.innerHTML = `
                            <span class="badge badge-owner">创建者</span>
                            <button class="btn-sm" onclick="openEditModal(${{memberId}})">编辑</button>
                            <button class="btn-danger" onclick="openDeleteModal(${{memberId}}, this)">删除</button>
                            <button class="btn-sm" style="background:#7c3aed" onclick="openCollabModal(${{clanId}})">授权</button>`;
                    }} else if (perm.can_edit) {{
                        el.innerHTML = `
                            <span class="badge badge-collab">协作者</span>
                            <button class="btn-sm" onclick="openEditModal(${{memberId}})">编辑</button>
                            <button class="btn-danger" onclick="openDeleteModal(${{memberId}}, this)">删除</button>`;
                    }} else {{
                        el.innerHTML = `<span class="badge badge-readonly">只读</span>`;
                    }}
                }}

                // 点击成员名字加载族谱树，同时记录 clanId
                async function loadTree(id, clanId) {{
                    try {{
                        currentClanId = clanId;
                        const res = await fetch(`/members/${{id}}/ancestors`);
                        if (!res.ok) {{
                            console.error('loadTree: /members/{id}/ancestors 返回错误', res.status);
                            return;
                        }}
                        const list = await res.json();
                        const treeData = buildHierarchy(list, id);

                        if (!treeData) {{
                            // 清空图表并给出提示（数据可能不全）
                            myChart.setOption({{ series: [] }});
                            console.warn('loadTree: 无法构建树数据，可能缺少成员或父母信息', id, list);
                        }} else {{
                            if (!myChart) myChart = echarts.init(document.getElementById('chart-container'));
                            myChart.setOption({{
                                series: [{{ type: 'tree', data: [treeData], label: {{ position: 'right' }} }}]
                            }});
                            // 确保图表在容器尺寸变化后能正确渲染
                            setTimeout(() => {{ try {{ myChart.resize(); }} catch(e) {{}} }}, 50);
                        }}

                        // 同步更新当前权限
                        const pRes = await fetch(`/permissions/check/${{clanId}}`);
                        if (pRes.ok) currentPerm = await pRes.json();

                        // 创建者才显示导航栏「管理协作者」按钮
                        const collabBtn = document.getElementById('btn-collab-current');
                        if (collabBtn) collabBtn.style.display = currentPerm.is_owner ? 'inline-block' : 'none';

                        // 数据概览切换为当前族谱统计
                        updateDashboard(clanId);
                    }} catch (e) {{
                        console.error('loadTree 错误', e);
                    }}
                }}

                function buildHierarchy(list, id) {{
                    const m = list.find(x => x.member_id == id);
                    if (!m) return null;
                    return {{
                        name: m.name,
                        children: [
                            m.father_id ? buildHierarchy(list, m.father_id) : null,
                            m.mother_id ? buildHierarchy(list, m.mother_id) : null
                        ].filter(x => x)
                    }};
                }}

                // ── 编辑成员 ───────────────────────────────────────
                async function openEditModal(memberId) {{
                    // 先拉一次成员详情填入表单
                    const res = await fetch(`/members/${{memberId}}/detail`);
                    if (!res.ok) {{ alert('获取成员信息失败'); return; }}
                    const m = await res.json();
                    document.getElementById('edit_member_id').value = memberId;
                    document.getElementById('edit_name').value = m.name || '';
                    document.getElementById('edit_gender').value = m.gender || 'M';
                    document.getElementById('edit_birth').value = m.birth_year || '';
                    document.getElementById('edit_death').value = m.death_year || '';
                    document.getElementById('edit_bio').value = m.bio || '';
                    document.getElementById('editMsg').innerText = '';
                    document.getElementById('pic_upload_msg').innerText = '';
                    // 设置照片预览（id_pic 是 data URI；无照片用默认图）
                    const preview = document.getElementById('edit_pic_preview');
                    preview.src = m.id_pic || DEFAULT_PIC;
                    preview.style.background = 'none';
                    // 清空文件输入，避免残留
                    document.getElementById('edit_pic_input').value = '';
                    // 亲属关系区域：有权限则显示并回填
                    const parentSec = document.getElementById('parent-section');
                    if (currentPerm && currentPerm.can_edit) {{
                        parentSec.style.display = 'block';
                        document.getElementById('edit_father').value = m.father_name || '';
                        document.getElementById('edit_mother').value = m.mother_name || '';
                    }} else {{
                        parentSec.style.display = 'none';
                    }}
                    // 婚姻区域：有权限则显示
                    const marriageSec = document.getElementById('marriage-section');
                    if (currentPerm && currentPerm.can_edit) {{
                        marriageSec.style.display = 'block';
                        document.getElementById('marriage-spouse-name').value = '';
                        document.getElementById('marriage-marry-year').value = '';
                        document.getElementById('marriage-msg').innerText = '';
                        loadMarriageList(memberId);
                    }} else {{
                        marriageSec.style.display = 'none';
                    }}
                    openModal('editModal');
                }}

                // 用户选图后立即上传，预览同步更新
                async function previewAndUploadPic() {{
                    const input = document.getElementById('edit_pic_input');
                    const memberId = document.getElementById('edit_member_id').value;
                    const msgEl = document.getElementById('pic_upload_msg');
                    const preview = document.getElementById('edit_pic_preview');

                    if (!input.files || !input.files[0]) return;
                    const file = input.files[0];

                    // 本地预览（即时响应）
                    const localUrl = URL.createObjectURL(file);
                    preview.src = localUrl;

                    // 上传到服务器
                    msgEl.style.color = '#94a3b8';
                    msgEl.innerText = '上传中...';
                    const formData = new FormData();
                    formData.append('file', file);
                    try {{
                        const res = await fetch(`/members/${{memberId}}/upload_pic`, {{ method: 'POST', body: formData }});
                        const data = await res.json();
                        if (res.ok) {{
                            msgEl.style.color = 'var(--success)';
                            msgEl.innerText = '照片已更新';
                            preview.src = data.url;  // 换成服务器 URL
                        }} else {{
                            msgEl.style.color = 'var(--danger)';
                            msgEl.innerText = data.detail || '上传失败';
                            preview.src = preview.dataset.original || DEFAULT_PIC;
                        }}
                    }} catch(e) {{
                        msgEl.style.color = 'var(--danger)';
                        msgEl.innerText = '网络错误';
                    }}
                }}

                async function submitEdit() {{
                    const memberId = document.getElementById('edit_member_id').value;
                    const formData = new FormData();
                    formData.append('name', document.getElementById('edit_name').value);
                    formData.append('gender', document.getElementById('edit_gender').value);
                    formData.append('birth_year', document.getElementById('edit_birth').value);
                    formData.append('death_year', document.getElementById('edit_death').value);
                    formData.append('bio', document.getElementById('edit_bio').value);
                    // 父母字段（有权限时才存在于 DOM）
                    const fatherEl = document.getElementById('edit_father');
                    const motherEl = document.getElementById('edit_mother');
                    if (fatherEl) formData.append('father_name', fatherEl.value);
                    if (motherEl) formData.append('mother_name', motherEl.value);
                    const res = await fetch(`/members/${{memberId}}/update`, {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    if (res.status === 401) {{
                        alert('登录已过期或未登录，请重新登录');
                        logout();
                        return;
                    }}
                    if (res.ok) {{
                        closeModal('editModal');
                        search(); // 刷新搜索结果
                    }} else {{
                        document.getElementById('editMsg').innerText = data.detail || '修改失败';
                    }}
                }}

                // ── 删除成员 ───────────────────────────────────────
                function openDeleteModal(memberId, btn) {{
                    const nameEl = btn.closest('.member-item').querySelector('strong');
                    document.getElementById('delete_member_id').value = memberId;
                    document.getElementById('delete_member_name').innerText = nameEl ? nameEl.innerText : memberId;
                    document.getElementById('deleteMsg').innerText = '';
                    openModal('deleteModal');
                }}

                async function submitDelete() {{
                    const memberId = document.getElementById('delete_member_id').value;
                    const res = await fetch(`/members/${{memberId}}/delete`, {{ method: 'DELETE' }});
                    const data = await res.json();
                    if (res.ok) {{
                        closeModal('deleteModal');
                        search();
                    }} else {{
                        document.getElementById('deleteMsg').innerText = data.detail || '删除失败';
                    }}
                }}

                // ── 授权管理 ───────────────────────────────────────
                async function openCollabModal(clanId) {{
                    currentClanId = clanId;
                    document.getElementById('collab_clan_id_label').innerText = clanId;
                    document.getElementById('grant_user_input').value = '';
                    document.getElementById('grantMsg').innerText = '';
                    await refreshCollabList(clanId);
                    openModal('collabModal');
                }}

                async function refreshCollabList(clanId) {{
                    const res = await fetch(`/permissions/collaborators/${{clanId}}`);
                    if (!res.ok) {{ document.getElementById('collabList').innerHTML = '<p style="color:var(--danger);font-size:13px;">无法加载协作者列表</p>'; return; }}
                    const list = await res.json();
                    if (list.length === 0) {{
                        document.getElementById('collabList').innerHTML = '<p style="font-size:13px; color:#94a3b8;">暂无协作者</p>';
                        return;
                    }}
                    let html = '<p style="font-size:12px;color:#64748b;margin-bottom:8px;">当前协作者：</p>';
                    list.forEach(u => {{
                        html += `<div class="collab-item">
                            <span>${{u.username || u.user_id}} <small style="color:#94a3b8;">(${{u.user_id}})</small></span>
                            <button class="btn-danger" onclick="revokeAccess('${{u.user_id}}')">撤销</button>
                        </div>`;
                    }});
                    document.getElementById('collabList').innerHTML = html;
                }}

                async function grantAccess() {{
                    const targetUid = document.getElementById('grant_user_input').value.trim();
                    if (!targetUid) return;
                    const formData = new FormData();
                    formData.append('clan_id', currentClanId);
                    formData.append('target_user_id', targetUid);
                    const res = await fetch('/permissions/grant', {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    const msgEl = document.getElementById('grantMsg');
                    msgEl.style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message || data.detail;
                    if (res.ok) {{
                        document.getElementById('grant_user_input').value = '';
                        await refreshCollabList(currentClanId);
                    }}
                }}

                async function revokeAccess(targetUid) {{
                    const formData = new FormData();
                    formData.append('clan_id', currentClanId);
                    formData.append('target_user_id', targetUid);
                    const res = await fetch('/permissions/revoke', {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    const msgEl = document.getElementById('grantMsg');
                    msgEl.style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message || data.detail;
                    if (res.ok) await refreshCollabList(currentClanId);
                }}

                // ── 族谱列表视图 ────────────────────────────────
                let clanViewOpen = false;

                function toggleClanView() {{
                    clanViewOpen = !clanViewOpen;
                    document.getElementById('search-view').style.display = clanViewOpen ? 'none' : 'flex';
                    document.getElementById('clan-view').style.display = clanViewOpen ? 'flex' : 'none';
                    if (clanViewOpen) loadClanList();
                }}

                async function loadClanList() {{
                    const res = await fetch('/api/genealogies');
                    if (!res.ok) return;
                    const clans = await res.json();
                    const el = document.getElementById('clan-list');
                    if (!clans.length) {{
                        el.innerHTML = '<p style="font-size:12px;color:#94a3b8;text-align:center;margin-top:20px;">暂无可管理的族谱</p>';
                        return;
                    }}
                    el.innerHTML = clans.map(c => {{
                        const badge = c.is_owner
                            ? `<span class="badge badge-owner">创建者</span>`
                            : `<span class="badge badge-collab">协作者</span>`;
                        const manageBtn = c.is_owner
                            ? `<button class="btn-sm" style="background:#7c3aed;flex-shrink:0;" onclick="toggleClanCollab(${{c.clan_id}})">授权管理</button>`
                            : '';
                        return `
                        <div class="clan-item" id="clan-item-${{c.clan_id}}">
                            <div class="clan-item-header">
                                <div>
                                    <div class="clan-item-title">${{c.title}} ${{badge}}</div>
                                    <div class="clan-item-sub">${{c.surname ? '姓氏：' + c.surname + '　' : ''}}ID: ${{c.clan_id}}</div>
                                </div>
                                ${{manageBtn}}
                            </div>
                            <div class="clan-collab-panel" id="collab-panel-${{c.clan_id}}">
                                <div id="collab-body-${{c.clan_id}}"></div>
                                <div class="grant-row">
                                    <input type="text" id="grant-input-${{c.clan_id}}" placeholder="输入账号授权">
                                    <button class="btn-primary" onclick="inlineGrant(${{c.clan_id}})">授权</button>
                                </div>
                                <div id="grant-msg-${{c.clan_id}}" style="font-size:12px;min-height:16px;margin-top:4px;"></div>
                            </div>
                        </div>`;
                    }}).join('');
                }}

                async function toggleClanCollab(clanId) {{
                    const panel = document.getElementById(`collab-panel-${{clanId}}`);
                    const isOpen = panel.classList.contains('open');
                    if (isOpen) {{
                        panel.classList.remove('open');
                    }} else {{
                        panel.classList.add('open');
                        await refreshInlineCollabList(clanId);
                    }}
                }}

                async function refreshInlineCollabList(clanId) {{
                    const res = await fetch(`/permissions/collaborators/${{clanId}}`);
                    const bodyEl = document.getElementById(`collab-body-${{clanId}}`);
                    if (!res.ok) {{ bodyEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">加载失败</p>'; return; }}
                    const list = await res.json();
                    if (!list.length) {{
                        bodyEl.innerHTML = '<p style="font-size:12px;color:#94a3b8;margin:4px 0;">暂无协作者</p>';
                        return;
                    }}
                    bodyEl.innerHTML = list.map(u => `
                        <div class="collab-row">
                            <span>${{u.username || u.user_id}} <small style="color:#94a3b8;">(${{u.user_id}})</small></span>
                            <button class="btn-danger" onclick="inlineRevoke(${{clanId}}, '${{u.user_id}}')">移除</button>
                        </div>`).join('');
                }}

                async function inlineGrant(clanId) {{
                    const input = document.getElementById(`grant-input-${{clanId}}`);
                    const msgEl = document.getElementById(`grant-msg-${{clanId}}`);
                    const targetUid = input.value.trim();
                    if (!targetUid) return;
                    const formData = new FormData();
                    formData.append('clan_id', clanId);
                    formData.append('target_user_id', targetUid);
                    const res = await fetch('/permissions/grant', {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    msgEl.style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message || data.detail;
                    if (res.ok) {{ input.value = ''; await refreshInlineCollabList(clanId); }}
                }}

                async function inlineRevoke(clanId, targetUid) {{
                    const msgEl = document.getElementById(`grant-msg-${{clanId}}`);
                    const formData = new FormData();
                    formData.append('clan_id', clanId);
                    formData.append('target_user_id', targetUid);
                    const res = await fetch('/permissions/revoke', {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    msgEl.style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message || data.detail;
                    if (res.ok) await refreshInlineCollabList(clanId);
                }}

                // 导航栏「管理协作者」按钮——显示当前浏览族谱的协作者
                function openCurrentClanCollab() {{
                    if (!currentClanId) return;
                    openCollabModal(currentClanId);
                }}

                // ── Tab 切换 ──────────────────────────────────
                function switchTab(tab) {{
                    const isSearch = tab === 'search';
                    document.getElementById('panel-search').style.display   = isSearch ? 'flex' : 'none';
                    document.getElementById('panel-relation').style.display = isSearch ? 'none' : 'flex';
                    document.getElementById('tab-search').style.background   = isSearch ? 'var(--primary)' : '#e2e8f0';
                    document.getElementById('tab-search').style.color        = isSearch ? 'white' : '#475569';
                    document.getElementById('tab-relation').style.background = isSearch ? '#e2e8f0' : 'var(--primary)';
                    document.getElementById('tab-relation').style.color      = isSearch ? '#475569' : 'white';
                }}

                // ── 查询亲缘关系 ──────────────────────────────
                async function queryRelation(idA, idB) {{
                    const nameA = document.getElementById('relNameA').value.trim();
                    const nameB = document.getElementById('relNameB').value.trim();
                    const msgEl = document.getElementById('relation-msg');
                    const resEl = document.getElementById('relation-result');

                    if (!nameA || !nameB) {{
                        msgEl.style.color = 'var(--danger)';
                        msgEl.innerText = '请输入两个成员的姓名';
                        return;
                    }}

                    msgEl.style.color = '#94a3b8';
                    msgEl.innerText = '查询中...';
                    resEl.innerHTML = '';

                    let url = `/api/relationship?name_a=${{encodeURIComponent(nameA)}}&name_b=${{encodeURIComponent(nameB)}}`;
                    if (idA) url += `&id_a=${{idA}}`;
                    if (idB) url += `&id_b=${{idB}}`;
                    
                    const isPerf = document.getElementById('perfModeToggle').checked;
                    url += '&perf_mode=' + (isPerf ? 'true' : 'false');

                    const res = await fetch(url);
                    const data = await res.json();

                    msgEl.style.color = data.found ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.perf_log ? `${{data.message}} | ${{data.perf_log}}` : data.message;

                    let candidateHtml = '';
                    if (data.candidates_a && data.candidates_a.length > 1) {{
                        candidateHtml += `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">A 存在多个同名成员，请选择：</div>`;
                        data.candidates_a.forEach(c => {{
                            candidateHtml += `<div class="member-item" style="padding:6px 10px;"
                                onclick="document.getElementById('relNameA').value='${{c.name}}'; queryRelation(${{c.member_id}}, ${{idB||'undefined'}})">
                                ${{c.name}} <small style="color:#94a3b8;">第${{c.gen}}代 族谱${{c.clan_id}}</small></div>`;
                        }});
                    }}
                    if (data.candidates_b && data.candidates_b.length > 1) {{
                        candidateHtml += `<div style="font-size:11px;color:#64748b;margin:6px 0 4px;">B 存在多个同名成员，请选择：</div>`;
                        data.candidates_b.forEach(c => {{
                            candidateHtml += `<div class="member-item" style="padding:6px 10px;"
                                onclick="document.getElementById('relNameB').value='${{c.name}}'; queryRelation(${{idA||'undefined'}}, ${{c.member_id}})">
                                ${{c.name}} <small style="color:#94a3b8;">第${{c.gen}}代 族谱${{c.clan_id}}</small></div>`;
                        }});
                    }}

                    let pathHtml = '';
                    if (data.found && data.path && data.path.length) {{
                        pathHtml = '<div style="margin-top:8px;">';
                        data.path.forEach((node, i) => {{
                            if (i > 0) pathHtml += '<div style="text-align:center;color:#cbd5e1;font-size:14px;margin:2px 0;">↓</div>';
                            const isEndpoint = i === 0 || i === data.path.length - 1;
                            pathHtml += `<div style="display:flex;justify-content:space-between;align-items:center;
                                padding:7px 10px;border-radius:6px;font-size:12px;
                                background:${{isEndpoint ? '#eff6ff' : '#f8fafc'}};
                                border:1px solid ${{isEndpoint ? '#bfdbfe' : '#f1f5f9'}};">
                                <strong>${{node.name}}</strong>
                                <span style="color:#64748b;">${{node.relation}}</span>
                            </div>`;
                        }});
                        pathHtml += '</div>';
                    }}

                    resEl.innerHTML = candidateHtml + pathHtml;
                }}

                // ── 婚姻管理 ──────────────────────────────────────
                async function loadMarriageList(memberId) {{
                    const res = await fetch(`/members/${{memberId}}/marriages`);
                    const listEl = document.getElementById('marriage-list');
                    if (!res.ok) {{ listEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">加载失败</p>'; return; }}
                    const marriages = await res.json();
                    if (!marriages.length) {{
                        listEl.innerHTML = '<p style="font-size:12px;color:#94a3b8;margin:4px 0;">暂无婚姻记录</p>';
                        return;
                    }}
                    listEl.innerHTML = marriages.map(m => {{
                        const years = m.marry_year
                            ? (m.divorce_year ? `${{m.marry_year}}—${{m.divorce_year}}年` : `${{m.marry_year}}年至今`)
                            : (m.divorce_year ? `至${{m.divorce_year}}年` : '年份不详');
                        const divorceBtn = m.divorce_year ? '' :
                            `<button class="btn-sm" style="background:#f59e0b;margin-right:4px;"
                                onclick="divorceMarriage(${{m.marriage_id}})">离婚</button>`;
                        return `<div class="marriage-item">
                            <div>
                                <span class="spouse-name">${{m.spouse_name}}</span>
                                <span style="color:#78350f;font-size:11px;margin-left:8px;">${{years}}</span>
                            </div>
                            <div>${{divorceBtn}}<button class="btn-danger" onclick="deleteMarriage(${{m.marriage_id}})">删除</button></div>
                        </div>`;
                    }}).join('');
                }}

                async function addMarriage() {{
                    const memberId   = document.getElementById('edit_member_id').value;
                    const spouseName = document.getElementById('marriage-spouse-name').value.trim();
                    const marryYear  = document.getElementById('marriage-marry-year').value.trim();
                    const msgEl = document.getElementById('marriage-msg');
                    if (!spouseName) {{ msgEl.style.color='var(--danger)'; msgEl.innerText='请输入配偶姓名'; return; }}
                    const fd = new FormData();
                    fd.append('member_id', memberId);
                    fd.append('spouse_name', spouseName);
                    if (marryYear) fd.append('marry_year', marryYear);
                    const res = await fetch('/api/marriages', {{ method:'POST', body:fd }});
                    const data = await res.json();
                    msgEl.style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message || data.detail;
                    if (res.ok) {{
                        document.getElementById('marriage-spouse-name').value = '';
                        document.getElementById('marriage-marry-year').value = '';
                        loadMarriageList(memberId);
                    }}
                }}

                async function divorceMarriage(marriageId) {{
                    const memberId = document.getElementById('edit_member_id').value;
                    const year = prompt('请输入离婚年份（留空跳过）：');
                    if (year === null) return;
                    const fd = new FormData();
                    fd.append('marriage_id', marriageId);
                    if (year.trim()) fd.append('divorce_year', year.trim());
                    const res = await fetch('/api/marriages/divorce', {{ method:'POST', body:fd }});
                    const data = await res.json();
                    document.getElementById('marriage-msg').style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    document.getElementById('marriage-msg').innerText = data.message || data.detail;
                    if (res.ok) loadMarriageList(memberId);
                }}

                async function deleteMarriage(marriageId) {{
                    if (!confirm('确认删除此婚姻记录？')) return;
                    const memberId = document.getElementById('edit_member_id').value;
                    const res = await fetch(`/api/marriages/${{marriageId}}`, {{ method:'DELETE' }});
                    const data = await res.json();
                    document.getElementById('marriage-msg').style.color = res.ok ? 'var(--success)' : 'var(--danger)';
                    document.getElementById('marriage-msg').innerText = data.message || data.detail;
                    if (res.ok) loadMarriageList(memberId);
                }}

                // ── 统计查询面板 ───────────────────────────────────
                let _clanOptions = null;

                async function openQueryModal() {{
                    openModal('queryModal');
                    // 加载族谱列表到下拉框
                    if (!_clanOptions) {{
                        const res = await fetch('/api/genealogies_all');
                        const clans = await res.json();
                        _clanOptions = clans;
                        ['longevity','singles','early'].forEach(t => {{
                            const sel = document.getElementById(`q-${{t}}-clan`);
                            const base = t === 'longevity' ? '<option value="">选择族谱...</option>' : '<option value="">全部族谱</option>';
                            sel.innerHTML = base + clans.map(cl => `<option value="${{cl.clan_id}}">${{cl.title}}</option>`).join('');
                        }});
                    }}
                    switchQueryTab('spouse');
                }}

                function switchQueryTab(tab) {{
                    ['spouse','ancestors','longevity','singles','early','descendants'].forEach(t => {{
                        document.getElementById(`qp-${{t}}`).style.display = t === tab ? 'block' : 'none';
                        const btn = document.getElementById(`qt-${{t}}`);
                        if (t === tab) {{
                            btn.style.background = 'var(--primary)'; btn.style.color = 'white'; btn.style.border = 'none';
                        }} else {{
                            btn.style.background = '#f8fafc'; btn.style.color = '#475569'; btn.style.border = '1px solid #e2e8f0';
                        }}
                    }});
                }}

                function _table(headers, rows, emptyMsg) {{
                    if (!rows.length) return `<p style="color:#94a3b8;font-size:12px;text-align:center;padding:12px;">${{emptyMsg}}</p>`;
                    return `<table class="query-result-table">
                        <thead><tr>${{headers.map(h=>`<th>${{h}}</th>`).join('')}}</tr></thead>
                        <tbody>${{rows.map(r=>`<tr>${{r.map(cell=>`<td>${{cell??'—'}}</td>`).join('')}}</tr>`).join('')}}</tbody>
                    </table>`;
                }}

                async function runQuery(type) {{
                    const resultEl = document.getElementById(`qr-${{type}}`);
                    resultEl.innerHTML = '<p style="color:#94a3b8;font-size:12px;">查询中...</p>';
                    let url = '', res, data;

                    if (type === 'spouse') {{
                        const name = document.getElementById('q-spouse-name').value.trim();
                        if (!name) {{ resultEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">请输入姓名</p>'; return; }}
                        res = await fetch(`/api/query/spouse_children?name=${{encodeURIComponent(name)}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        let html = '';
                        html += '<div style="font-weight:600;font-size:12px;color:#1e293b;margin-bottom:6px;">配偶</div>';
                        html += _table(['姓名','性别','出生年','结婚年','离婚年'],
                            data.spouses.map(s=>[s.name, s.gender==='M'?'男':'女', s.birth_year, s.marry_year, s.divorce_year]),
                            '暂无配偶记录');
                        html += '<div style="font-weight:600;font-size:12px;color:#1e293b;margin:10px 0 6px;">子女</div>';
                        html += _table(['姓名','性别','出生年','代数'],
                            data.children.map(ch=>[ch.name, ch.gender==='M'?'男':'女', ch.birth_year, ch.generation_num]),
                            '暂无子女记录');
                        resultEl.innerHTML = html;

                    }} else if (type === 'ancestors') {{
                        const name = document.getElementById('q-ancestors-name').value.trim();
                        if (!name) {{ resultEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">请输入姓名</p>'; return; }}
                        res = await fetch(`/api/query/ancestors?name=${{encodeURIComponent(name)}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        resultEl.innerHTML = _table(
                            ['姓名','性别','出生年','去世年','代数','距离（代）'],
                            data.map(r=>[r.name, r.gender==='M'?'男':'女', r.birth_year, r.death_year, r.generation_num, r.depth]),
                            '无祖先数据（可能是始祖）');

                    }} else if (type === 'longevity') {{
                        const clanId = document.getElementById('q-longevity-clan').value;
                        if (!clanId) {{ resultEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">请选择族谱</p>'; return; }}
                        res = await fetch(`/api/query/longevity?clan_id=${{clanId}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        resultEl.innerHTML = _table(
                            ['代数','平均寿命(年)','成员数'],
                            data.map(r=>[r.generation_num, r.avg_lifespan, r.count]),
                            '暂无数据');

                    }} else if (type === 'singles') {{
                        const clanId = document.getElementById('q-singles-clan').value;
                        res = await fetch(`/api/query/singles${{clanId ? '?clan_id='+clanId : ''}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        resultEl.innerHTML = _table(
                            ['姓名','出生年','估算年龄','族谱'],
                            data.map(r=>[r.name, r.birth_year, r.estimated_age, r.clan_title]),
                            '无符合条件成员');

                    }} else if (type === 'early') {{
                        const clanId = document.getElementById('q-early-clan').value;
                        res = await fetch(`/api/query/early_birth${{clanId ? '?clan_id='+clanId : ''}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        resultEl.innerHTML = _table(
                            ['姓名','族谱','代数','出生年','本代均值','早于均值(年)'],
                            data.map(r=>[r.name, r.clan_id, r.generation_num, r.birth_year, r.generation_avg, r.years_earlier]),
                            '无符合条件成员');
                    }} else if (type === 'descendants') {{
                        const name = document.getElementById('q-descendants-name').value.trim();
                        if (!name) {{ resultEl.innerHTML = '<p style="color:var(--danger);font-size:12px;">请输入姓名</p>'; return; }}
                        res = await fetch(`/api/query/great_grandchildren?name=${{encodeURIComponent(name)}}`);
                        data = await res.json();
                        if (!res.ok) {{ resultEl.innerHTML = `<p style="color:var(--danger);font-size:12px;">${{data.detail}}</p>`; return; }}
                        resultEl.innerHTML = _table(
                            ['姓名','性别','代数','出生年'],
                            data.map(r=>[r.name, r.gender==='M'?'男':'女', r.generation_num, r.birth_year]),
                            '无第四代（曾孙辈）记录');
                    }}
                }}

                // ── 工具 ─────────────────────────────────────────
                function openModal(id) {{ 
                    document.getElementById(id).classList.add('active'); 
                    if(id === 'addMemberModal') {{
                         // 加载可以编辑的族谱到下拉框
                         loadAddMemberClanOptions();
                    }}
                }}
                function closeModal(id) {{ document.getElementById(id).classList.remove('active'); }}

                async function loadAddMemberClanOptions() {{
                    const res = await fetch('/api/genealogies');
                    const clans = await res.json();
                    const sel = document.getElementById('add_member_clan');
                    sel.innerHTML = clans.map(c => `<option value="${{c.clan_id}}">${{c.title}}</option>`).join('');
                }}

                async function submitAddGenealogy() {{
                    const title = document.getElementById('add_gen_title').value.trim();
                    const surname = document.getElementById('add_gen_surname').value.trim();
                    const msgEl = document.getElementById('addGenMsg');
                    if (!title) {{ msgEl.innerText = "请输入族谱标题"; return; }}
                    
                    const fd = new FormData();
                    fd.append('title', title);
                    fd.append('surname', surname);

                    try {{
                        const res = await fetch('/api/genealogies', {{ method: 'POST', body: fd }});
                        const data = await res.json();
                        if (res.ok) {{
                            closeModal('addGenealogyModal');
                            document.getElementById('add_gen_title').value = '';
                            document.getElementById('add_gen_surname').value = '';
                            if (clanViewOpen) loadClanList();
                        }} else {{
                            msgEl.innerText = data.detail || '创建失败';
                        }}
                    }} catch (e) {{ msgEl.innerText = "网络错误"; }}
                }}

                async function submitAddMember() {{
                    const clan_id = document.getElementById('add_member_clan').value;
                    const name = document.getElementById('add_member_name').value.trim();
                    const msgEl = document.getElementById('addMemberMsg');
                    if (!clan_id) {{ msgEl.innerText = "请选择族谱"; return; }}
                    if (!name) {{ msgEl.innerText = "请输入成员姓名"; return; }}

                    const fd = new FormData();
                    fd.append('clan_id', clan_id);
                    fd.append('name', name);
                    fd.append('gender', document.getElementById('add_member_gender').value);
                    fd.append('birth_year', document.getElementById('add_member_birth').value);
                    fd.append('death_year', document.getElementById('add_member_death').value);
                    fd.append('bio', document.getElementById('add_member_bio').value);
                    fd.append('father_name', document.getElementById('add_member_father').value.trim());
                    fd.append('mother_name', document.getElementById('add_member_mother').value.trim());

                    try {{
                        const res = await fetch('/members/add', {{ method: 'POST', body: fd }});
                        const data = await res.json();
                        if (res.ok) {{
                            closeModal('addMemberModal');
                            document.getElementById('add_member_name').value = '';
                            document.getElementById('add_member_birth').value = '';
                            document.getElementById('add_member_death').value = '';
                            document.getElementById('add_member_bio').value = '';
                            document.getElementById('add_member_father').value = '';
                            document.getElementById('add_member_mother').value = '';
                            search();
                        }} else {{
                            msgEl.innerText = data.detail || '添加失败';
                        }}
                    }} catch (e) {{ msgEl.innerText = "网络错误"; }}
                }}

                function togglePassword() {{
                    const p = document.getElementById('login_pwd');
                    p.type = p.type === 'password' ? 'text' : 'password';
                }}
            </script>
        </body>
    </html>
    """


# ---------------------------------------------------------
# 仪表盘
# ---------------------------------------------------------
@app.get("/api/default_pic")
def get_default_pic():
    return {"url": DEFAULT_PIC_DATA_URI}


@app.get("/api/permissions/batch")
def batch_check_permissions(clan_ids: str, request: Request):
    current_user = request.cookies.get("session_user")
    if not current_user:
        return {}
    try:
        ids = [int(x) for x in clan_ids.split(",") if x.strip().isdigit()]
    except ValueError:
        return {}
    db = SessionLocal()
    try:
        result = {}
        for cid in ids:
            owner_row = db.execute(text("""
                SELECT 1 FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """), {"cid": cid, "uid": current_user}).fetchone()
            is_owner = owner_row is not None
            can_edit = is_owner or check_edit_permission(db, cid, current_user)
            result[str(cid)] = {"can_edit": can_edit, "is_owner": is_owner}
        return result
    finally:
        db.close()


@app.get("/api/dashboard")
def get_dashboard_stats(clan_id: int = None):
    db = SessionLocal()
    try:
        if clan_id is not None:
            total = db.execute(
                text("SELECT COUNT(*) FROM members WHERE clan_id = :cid"),
                {"cid": clan_id}
            ).scalar()
            gender_stats = db.execute(
                text("SELECT gender, COUNT(*) FROM members WHERE clan_id = :cid GROUP BY gender"),
                {"cid": clan_id}
            ).all()
        else:
            total = db.execute(text("SELECT COUNT(*) FROM members")).scalar()
            gender_stats = db.execute(text("SELECT gender, COUNT(*) FROM members GROUP BY gender")).all()
        return {"total_members": total, "gender_ratio": {row[0]: row[1] for row in gender_stats}}
    finally:
        db.close()


# ---------------------------------------------------------
# 族谱列表（仅返回当前用户创建或被授权的族谱）
# ---------------------------------------------------------
@app.get("/api/genealogies")
def get_genealogies(request: Request):
    current_user = request.cookies.get("session_user")
    if not current_user:
        return []
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT clan_id, title, surname FROM genealogies ORDER BY clan_id")).all()
        result = []
        for r in rows:
            owner_row = db.execute(text("""
                SELECT 1 FROM genealogies g
                JOIN users u ON u.id = g.creator_id
                WHERE g.clan_id = :cid AND u.user_id = :uid
            """), {"cid": r[0], "uid": current_user}).fetchone()
            is_owner = owner_row is not None
            can_edit = is_owner or check_edit_permission(db, r[0], current_user)
            if can_edit:
                result.append({"clan_id": r[0], "title": r[1], "surname": r[2], "is_owner": is_owner})
        return result
    finally:
        db.close()


# ---------------------------------------------------------
# 成员查询（新增 clan_id 返回，供前端权限检查用）
# ---------------------------------------------------------
@app.get("/members/search")
def search_members(name: str, perf_mode: str = "true"):
    db = SessionLocal()
    tracemalloc.start()
    m0, _ = tracemalloc.get_traced_memory()
    start_time = time.perf_counter()
    try:
        if perf_mode.lower() == "false":
            db.execute(text("SET enable_indexscan = off;"))
            db.execute(text("SET enable_bitmapscan = off;"))

        results = db.execute(
            text("""
                SELECT member_id, clan_id, name, generation_num FROM members
                WHERE name LIKE :n
                ORDER BY
                    CASE WHEN name = :exact THEN 0 ELSE 1 END,
                    length(name),
                    member_id
                LIMIT 50
            """),
            {"n": f"%{name}%", "exact": name}
        ).all()
        data = [{"id": r[0], "clan_id": r[1], "name": r[2], "gen": r[3]} for r in results]
    finally:
        if perf_mode.lower() == "false":
            db.execute(text("SET enable_indexscan = on;"))
            db.execute(text("SET enable_bitmapscan = on;"))
        end_time = time.perf_counter()
        m1, _ = tracemalloc.get_traced_memory()
        db.close()
        
    time_ms = (end_time - start_time) * 1000
    mem_kb = max(0, (m1 - m0) / 1024)
    if data:
        data[0]["perf_log"] = f"耗时: {time_ms:.2f}ms | 内存: {mem_kb:.2f}KB"
        
    return data


# ---------------------------------------------------------
# 成员详情（编辑表单回填用）
# ---------------------------------------------------------
@app.get("/members/{member_id}/detail")
def get_member_detail(member_id: int):
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT member_id, clan_id, name, gender, birth_year, death_year, bio, id_pic, father_id, mother_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")
        res = dict(row._mapping)
        if not res.get("id_pic"):
            res["id_pic"] = DEFAULT_PIC_DATA_URI
        # 查父母姓名，供前端回填
        if res.get("father_id"):
            f = db.execute(text("SELECT name FROM members WHERE member_id = :mid"), {"mid": res["father_id"]}).fetchone()
            res["father_name"] = f[0] if f else ""
        else:
            res["father_name"] = ""
        if res.get("mother_id"):
            m = db.execute(text("SELECT name FROM members WHERE member_id = :mid"), {"mid": res["mother_id"]}).fetchone()
            res["mother_name"] = m[0] if m else ""
        else:
            res["mother_name"] = ""
        return res
    finally:
        db.close()


# ---------------------------------------------------------
# 成员祖先树
# ---------------------------------------------------------
@app.get("/members/{member_id}/ancestors")
def get_ancestors(member_id: int):
    db = SessionLocal()
    try:
        sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT member_id, name, father_id, mother_id FROM members WHERE member_id = :mid
                UNION ALL
                SELECT m.member_id, m.name, m.father_id, m.mother_id FROM members m
                JOIN ancestors a ON m.member_id = a.father_id OR m.member_id = a.mother_id
            ) SELECT DISTINCT * FROM ancestors
        """)
        return [dict(r._mapping) for r in db.execute(sql, {"mid": member_id}).all()]
    finally:
        db.close()


# ---------------------------------------------------------
# 修改成员（需要编辑权限）
# ---------------------------------------------------------
@app.post("/members/{member_id}/update")
def update_member(
    member_id: int,
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    birth_year: str = Form(""),
    death_year: str = Form(""),
    bio: str = Form(""),
    father_name: str = Form(""),
    mother_name: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    if birth_year and death_year:
        try:
            if int(birth_year) >= int(death_year):
                raise HTTPException(status_code=400, detail="出生年份必须早于死亡年份")
        except ValueError:
            pass

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id, father_id, mother_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")

        clan_id = row[0]

        # ── 权限检查 ──
        if not check_edit_permission(db, clan_id, current_user):
            raise HTTPException(status_code=403, detail="无编辑权限，请联系族谱创建者授权")

        # ── 解析父母 ID（含性别校验，支持姓名或 member_id 数字）──
        def resolve_parent(raw: str, role: str, required_gender: str) -> int:
            val = raw.strip()
            if val.isdigit():
                pid = int(val)
                if pid == member_id:
                    raise HTTPException(status_code=400, detail=f"不能将自己设为{role}")
                row_p = db.execute(
                    text("SELECT member_id, clan_id, gender FROM members WHERE member_id = :pid"),
                    {"pid": pid}
                ).fetchone()
                if not row_p:
                    raise HTTPException(status_code=404, detail=f"找不到 member_id={pid} 的成员")
                if row_p[1] != clan_id:
                    raise HTTPException(status_code=400, detail=f"member_id={pid} 不属于当前族谱(clan_id={clan_id})")
                if row_p[2] and row_p[2] != required_gender:
                    gender_label = "男" if required_gender == "M" else "女"
                    raise HTTPException(status_code=400, detail=f"{role}性别必须为{gender_label}，该成员性别不符")
                return pid
            candidates = db.execute(
                text("SELECT member_id, gender FROM members WHERE name = :n AND clan_id = :cid AND member_id != :mid"),
                {"n": val, "cid": clan_id, "mid": member_id}
            ).fetchall()
            if not candidates:
                anywhere = db.execute(
                    text("SELECT clan_id FROM members WHERE name = :n LIMIT 5"),
                    {"n": val}
                ).fetchall()
                hint = f"；该名字存在于族谱 {[r[0] for r in anywhere]}，但不在当前族谱(clan_id={clan_id})" if anywhere else ""
                raise HTTPException(status_code=404, detail=f"同族谱中找不到{role} [{val}]{hint}")
            if len(candidates) > 1:
                raise HTTPException(status_code=400, detail=f"{role}姓名 [{val}] 对应多个成员，请直接输入 member_id 数字")
            pid, gender = candidates[0]
            if gender and gender != required_gender:
                gender_label = "男" if required_gender == "M" else "女"
                raise HTTPException(status_code=400, detail=f"{role}性别必须为{gender_label}，[{val}] 的性别不符")
            return pid

        new_father_id = None
        new_mother_id = None

        if father_name and father_name.strip():
            new_father_id = resolve_parent(father_name, "父亲", "M")

        if mother_name and mother_name.strip():
            new_mother_id = resolve_parent(mother_name, "母亲", "F")

        # ── 出生年份校验（使用新父母 ID，若未传则沿用旧值）──
        effective_father_id = new_father_id if father_name.strip() else row[1]
        effective_mother_id = new_mother_id if mother_name.strip() else row[2]

        by = int(birth_year) if birth_year and birth_year.strip() else None
        if by is not None:
            if effective_father_id:
                f_birth = db.execute(text("SELECT birth_year FROM members WHERE member_id = :fid"), {"fid": effective_father_id}).fetchone()
                if f_birth and f_birth[0] is not None and by <= f_birth[0]:
                    raise HTTPException(status_code=400, detail="成员的出生年份不能早于或等于父亲的出生年份")
            if effective_mother_id:
                m_birth = db.execute(text("SELECT birth_year FROM members WHERE member_id = :fid"), {"fid": effective_mother_id}).fetchone()
                if m_birth and m_birth[0] is not None and by <= m_birth[0]:
                    raise HTTPException(status_code=400, detail="成员的出生年份不能早于或等于母亲的出生年份")
            children_births = db.execute(
                text("SELECT birth_year FROM members WHERE (father_id = :mid OR mother_id = :mid) AND birth_year IS NOT NULL"),
                {"mid": member_id}
            ).fetchall()
            for cb in children_births:
                if by >= cb[0]:
                    raise HTTPException(status_code=400, detail="成员的出生年份不能晚于或等于子女的出生年份")

        # ── 构建 UPDATE，父母字段仅在有传值时更新 ──
        set_clauses = [
            "name = :name",
            "gender = :gender",
            "birth_year = NULLIF(:birth, '')::INT",
            "death_year = NULLIF(:death, '')::INT",
            "bio = :bio",
        ]
        params = {
            "name": name, "gender": gender,
            "birth": birth_year, "death": death_year,
            "bio": bio, "mid": member_id
        }

        # 父亲：传了名字就更新（传空字符串表示清空）
        if father_name is not None:
            set_clauses.append("father_id = :father_id")
            params["father_id"] = new_father_id  # None = 清空

        # 母亲同理
        if mother_name is not None:
            set_clauses.append("mother_id = :mother_id")
            params["mother_id"] = new_mother_id

        db.execute(
            text(f"UPDATE members SET {', '.join(set_clauses)} WHERE member_id = :mid"),
            params
        )

        # ── 同步父母婚姻记录 ──────────────────────────────────────
        # 取更新后的实际父母 ID
        final_father_id = new_father_id if father_name is not None else row[1]
        final_mother_id = new_mother_id if mother_name is not None else row[2]
        _ensure_marriage(db, final_father_id, final_mother_id, clan_id)

        # ── 清理旧父母的婚姻记录 ──────────────────────────────────
        old_father_id = row[1]
        old_mother_id = row[2]
        if old_father_id and old_mother_id:
            if old_father_id != final_father_id or old_mother_id != final_mother_id:
                _cleanup_marriage(db, old_father_id, old_mother_id, clan_id)

        db.commit()
        return {"message": "修改成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------
# 查询亲缘关系
# ---------------------------------------------------------
@app.get("/api/relationship")
def get_relationship(
    name_a: str,
    name_b: str,
    id_a: int = None,
    id_b: int = None,
    perf_mode: str = "true"
):
    db = SessionLocal()
    tracemalloc.start()
    m0, _ = tracemalloc.get_traced_memory()
    start_time = time.perf_counter()
    try:
        if perf_mode.lower() == "false":
            db.execute(text("SET enable_indexscan = off;"))
            db.execute(text("SET enable_bitmapscan = off;"))

        res = find_relationship(db, name_a, name_b, id_a, id_b)
    finally:
        if perf_mode.lower() == "false":
            db.execute(text("SET enable_indexscan = on;"))
            db.execute(text("SET enable_bitmapscan = on;"))
        end_time = time.perf_counter()
        m1, _ = tracemalloc.get_traced_memory()
        db.close()
        
    time_ms = (end_time - start_time) * 1000
    mem_kb = max(0, (m1 - m0) / 1024)
    res["time_ms"] = time_ms
    res["mem_kb"] = mem_kb
    res["perf_log"] = f"耗时: {time_ms:.2f}ms | 内存: {mem_kb:.2f}KB"
    return res


# ---------------------------------------------------------
# 删除成员（需要编辑权限）
# ---------------------------------------------------------
@app.delete("/members/{member_id}/delete")
def delete_member(member_id: int, request: Request):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id, father_id, mother_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")

        # ── 权限检查 ──
        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限，请联系族谱创建者授权")

        db.execute(text("DELETE FROM members WHERE member_id = :mid"), {"mid": member_id})
        
        # ── 清理父母的婚姻记录 ──────────────────────────────────
        if row[1] and row[2]:
            _cleanup_marriage(db, row[1], row[2], row[0])

        db.commit()
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# ---------------------------------------------------------
# 上传成员照片（base64 直接存数据库，无本地文件）
# ---------------------------------------------------------
@app.post("/members/{member_id}/upload_pic")
async def upload_member_pic(
    member_id: int,
    request: Request,
    file: UploadFile = File(...)
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    # 校验文件格式
    ext = os.path.splitext(file.filename)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    if ext not in mime_map:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png 格式")

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")

        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限")

        # 读取文件内容，转 base64，拼成 data URI
        raw = await file.read()
        b64 = base64.b64encode(raw).decode("utf-8")
        data_uri = f"data:{mime_map[ext]};base64,{b64}"

        db.execute(
            text("UPDATE members SET id_pic = :pic WHERE member_id = :mid"),
            {"pic": data_uri, "mid": member_id}
        )
        db.commit()
        # 直接把 data URI 返回给前端，前端赋值给 img.src 即可
        return {"message": "上传成功", "url": data_uri}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================
# 父母婚姻关系同步工具函数
# =============================================================

def _ensure_marriage(db, father_id, mother_id, clan_id):
    """
    确保 father_id 和 mother_id 之间存在婚姻记录。
    - 若已有未离婚记录则跳过。
    - 若无则自动创建（marry_year=NULL）。
    仅在两者都不为 None 时执行。
    """
    if not father_id or not mother_id:
        return
    existing = db.execute(text("""
        SELECT 1 FROM marriages
        WHERE ((spouse_a_id = :a AND spouse_b_id = :b)
            OR (spouse_a_id = :b AND spouse_b_id = :a))
          AND divorce_year IS NULL
    """), {"a": father_id, "b": mother_id}).fetchone()
    if not existing:
        db.execute(text("""
            INSERT INTO marriages (spouse_a_id, spouse_b_id, marry_year, clan_id)
            VALUES (:a, :b, NULL, :cid)
        """), {"a": father_id, "b": mother_id, "cid": clan_id})


def _cleanup_marriage(db, father_id, mother_id, clan_id):
    """
    检查 father_id 和 mother_id 之间是否还存在其他共同子女。
    如果不存在，且两人的婚姻记录是自动创建的（marry_year IS NULL 且 divorce_year IS NULL），
    则自动删除该婚姻记录。
    """
    if not father_id or not mother_id:
        return
    has_children = db.execute(text("""
        SELECT 1 FROM members
        WHERE father_id = :fid AND mother_id = :mid
        LIMIT 1
    """), {"fid": father_id, "mid": mother_id}).fetchone()
    
    if not has_children:
        db.execute(text("""
            DELETE FROM marriages
            WHERE ((spouse_a_id = :fid AND spouse_b_id = :mid)
                OR (spouse_a_id = :mid AND spouse_b_id = :fid))
              AND marry_year IS NULL
              AND divorce_year IS NULL
        """), {"fid": father_id, "mid": mother_id})


# =============================================================
# marriages 表相关接口
# =============================================================

@app.get("/members/{member_id}/marriages")
def get_member_marriages(member_id: int, request: Request):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT mg.marriage_id, mg.marry_year, mg.divorce_year,
                CASE WHEN mg.spouse_a_id = :mid THEN mb.name ELSE ma.name END AS spouse_name,
                CASE WHEN mg.spouse_a_id = :mid THEN mg.spouse_b_id ELSE mg.spouse_a_id END AS spouse_id
            FROM marriages mg
            JOIN members ma ON ma.member_id = mg.spouse_a_id
            JOIN members mb ON mb.member_id = mg.spouse_b_id
            WHERE mg.spouse_a_id = :mid OR mg.spouse_b_id = :mid
            ORDER BY mg.marry_year NULLS LAST, mg.marriage_id
        """), {"mid": member_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.post("/api/marriages")
def add_marriage(
    request: Request,
    member_id: int = Form(...),
    spouse_name: str = Form(...),
    marry_year: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    db = SessionLocal()
    try:
        member = db.execute(
            text("SELECT member_id, clan_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="成员不存在")
        if not check_edit_permission(db, member[1], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限")

        spouses = db.execute(
            text("SELECT member_id FROM members WHERE name = :n AND clan_id = :cid"),
            {"n": spouse_name, "cid": member[1]}
        ).fetchall()
        if not spouses:
            raise HTTPException(status_code=404, detail=f"同族谱中找不到成员 [{spouse_name}]")
        if len(spouses) > 1:
            raise HTTPException(status_code=400, detail=f"同名成员有 {len(spouses)} 个，请使用更精确的姓名")

        spouse_id = spouses[0][0]
        if spouse_id == member_id:
            raise HTTPException(status_code=400, detail="不能与自己登记婚姻")

        existing = db.execute(text("""
            SELECT 1 FROM marriages
            WHERE ((spouse_a_id=:a AND spouse_b_id=:b) OR (spouse_a_id=:b AND spouse_b_id=:a))
              AND divorce_year IS NULL
        """), {"a": member_id, "b": spouse_id}).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="两人已有有效婚姻记录")

        # ── 性别推断：一方已知则推断另一方，有矛盾则回退 ──
        gender_rows = db.execute(
            text("SELECT member_id, gender FROM members WHERE member_id IN :ids"),
            {"ids": (member_id, spouse_id)}
        ).fetchall()
        genders = {r[0]: r[1] or None for r in gender_rows}
        g_self   = genders.get(member_id)
        g_spouse = genders.get(spouse_id)

        infer_id     = None
        infer_gender = None
        if g_self and not g_spouse:
            infer_id, infer_gender = spouse_id, ('F' if g_self == 'M' else 'M')
        elif g_spouse and not g_self:
            infer_id, infer_gender = member_id, ('F' if g_spouse == 'M' else 'M')

        if infer_id and infer_gender:
            expected_spouse_gender = 'F' if infer_gender == 'M' else 'M'
            conflict = db.execute(text("""
                SELECT sp.member_id FROM marriages mg
                JOIN members sp ON sp.member_id =
                    CASE WHEN mg.spouse_a_id = :iid THEN mg.spouse_b_id ELSE mg.spouse_a_id END
                WHERE (mg.spouse_a_id = :iid OR mg.spouse_b_id = :iid)
                  AND sp.gender IS NOT NULL AND sp.gender != ''
                  AND sp.gender != :esg
                LIMIT 1
            """), {"iid": infer_id, "esg": expected_spouse_gender}).fetchone()
            if conflict:
                gender_label = "男" if infer_gender == 'M' else "女"
                raise HTTPException(
                    status_code=400,
                    detail=f"性别推断冲突：根据配偶性别推断该成员应为{gender_label}，"
                           f"但其已有婚姻记录中存在矛盾，请先手动确认性别后再登记"
                )
            db.execute(
                text("UPDATE members SET gender = :g WHERE member_id = :mid"),
                {"g": infer_gender, "mid": infer_id}
            )

        my = int(marry_year) if marry_year and marry_year.strip() else None
        db.execute(text("""
            INSERT INTO marriages (spouse_a_id, spouse_b_id, marry_year, clan_id)
            VALUES (:a, :b, :my, :cid)
        """), {"a": member_id, "b": spouse_id, "my": my, "cid": member[1]})
        db.commit()

        infer_msg = ""
        if infer_id and infer_gender:
            label = "男" if infer_gender == "M" else "女"
            name_row = db.execute(
                text("SELECT name FROM members WHERE member_id = :mid"), {"mid": infer_id}
            ).fetchone()
            infer_msg = f"，已自动将 [{name_row[0] if name_row else infer_id}] 的性别确定为{label}"
        return {"message": f"已成功登记与 [{spouse_name}] 的婚姻{infer_msg}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/marriages/divorce")
def set_divorce(
    request: Request,
    marriage_id: int = Form(...),
    divorce_year: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id FROM marriages WHERE marriage_id = :mid"),
            {"mid": marriage_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="婚姻记录不存在")
        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限")
        dy = int(divorce_year) if divorce_year and divorce_year.strip() else None
        db.execute(
            text("UPDATE marriages SET divorce_year = :dy WHERE marriage_id = :mid"),
            {"dy": dy, "mid": marriage_id}
        )
        db.commit()
        return {"message": "已记录离婚"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.delete("/api/marriages/{marriage_id}")
def delete_marriage(marriage_id: int, request: Request):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id FROM marriages WHERE marriage_id = :mid"),
            {"mid": marriage_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="婚姻记录不存在")
        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限")
        db.execute(text("DELETE FROM marriages WHERE marriage_id = :mid"), {"mid": marriage_id})
        db.commit()
        return {"message": "婚姻记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================
# 新增族谱与成员接口
# =============================================================

@app.post("/api/genealogies")
def add_genealogy(
    request: Request,
    title: str = Form(...),
    surname: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        user = db.execute(text("SELECT id FROM users WHERE user_id = :uid"), {"uid": current_user}).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
            
        next_id_row = db.execute(text("SELECT COALESCE(MAX(clan_id), 0) + 1 FROM genealogies")).fetchone()
        new_id = next_id_row[0]

        db.execute(text("""
            INSERT INTO genealogies (clan_id, title, surname, creator_id)
            VALUES (:cid, :t, :s, :uid)
        """), {"cid": new_id, "t": title, "s": surname, "uid": user[0]})
        db.commit()
        return {"message": "新建族谱成功", "clan_id": new_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/members/add")
def add_member(
    request: Request,
    clan_id: int = Form(...),
    name: str = Form(...),
    gender: str = Form(...),
    birth_year: str = Form(""),
    death_year: str = Form(""),
    bio: str = Form(""),
    father_name: str = Form(""),
    mother_name: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    if birth_year and death_year:
        try:
            if int(birth_year) >= int(death_year):
                raise HTTPException(status_code=400, detail="出生年份必须早于死亡年份")
        except ValueError:
            pass

    db = SessionLocal()
    try:
        if not check_edit_permission(db, clan_id, current_user):
            raise HTTPException(status_code=403, detail="无编辑权限")

        father_id = None
        mother_id = None
        generation_num = 1

        father_birth = None
        if father_name and father_name.strip():
            fs_all = db.execute(
                text("SELECT member_id, generation_num, gender, birth_year FROM members WHERE name = :n AND clan_id = :c"),
                {"n": father_name.strip(), "c": clan_id}
            ).fetchall()
            if not fs_all:
                raise HTTPException(status_code=404, detail=f"同族谱中找不到父亲 [{father_name}]")
            # 允许性别未设定（None/空）或明确为男
            valid = [r for r in fs_all if not r[2] or r[2] == 'M']
            if not valid:
                raise HTTPException(status_code=400, detail=f"父亲性别必须为男，[{father_name}] 的性别不符")
            if len(valid) > 1:
                raise HTTPException(status_code=400, detail=f"父亲姓名 [{father_name}] 对应多个成员，请直接输入 member_id 数字")
            father_id = valid[0][0]
            generation_num = max(generation_num, (valid[0][1] or 0) + 1)
            father_birth = valid[0][3]

        mother_birth = None
        if mother_name and mother_name.strip():
            ms_all = db.execute(
                text("SELECT member_id, generation_num, gender, birth_year FROM members WHERE name = :n AND clan_id = :c"),
                {"n": mother_name.strip(), "c": clan_id}
            ).fetchall()
            if not ms_all:
                raise HTTPException(status_code=404, detail=f"同族谱中找不到母亲 [{mother_name}]")
            # 允许性别未设定（None/空）或明确为女
            valid = [r for r in ms_all if not r[2] or r[2] == 'F']
            if not valid:
                raise HTTPException(status_code=400, detail=f"母亲性别必须为女，[{mother_name}] 的性别不符")
            if len(valid) > 1:
                raise HTTPException(status_code=400, detail=f"母亲姓名 [{mother_name}] 对应多个成员，请直接输入 member_id 数字")
            mother_id = valid[0][0]
            generation_num = max(generation_num, (valid[0][1] or 0) + 1)
            mother_birth = valid[0][3]

        by = int(birth_year) if birth_year.strip() else None
        
        if by is not None:
            if father_birth is not None and by <= father_birth:
                raise HTTPException(status_code=400, detail="子女的出生年份不能早于或等于父亲的出生年份")
            if mother_birth is not None and by <= mother_birth:
                raise HTTPException(status_code=400, detail="子女的出生年份不能早于或等于母亲的出生年份")

        dy = int(death_year) if death_year.strip() else None

        next_id_row = db.execute(text("SELECT COALESCE(MAX(member_id), 0) + 1 FROM members")).fetchone()
        new_id = next_id_row[0]

        db.execute(text("""
            INSERT INTO members (member_id, clan_id, name, gender, birth_year, death_year, bio, father_id, mother_id, generation_num)
            VALUES (:mid, :cid, :n, :g, :by, :dy, :bio, :fid, :mid_parent, :gen)
        """), {
            "mid": new_id, "cid": clan_id, "n": name, "g": gender, "by": by, "dy": dy, "bio": bio, "fid": father_id, "mid_parent": mother_id, "gen": generation_num
        })

        # ── 同步父母婚姻记录 ──────────────────────────────────────
        _ensure_marriage(db, father_id, mother_id, clan_id)

        db.commit()
        return {"message": "添加成员成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



# =============================================================
# 统计查询接口
# =============================================================

@app.get("/api/genealogies_all")
def get_all_genealogies():
    """返回全部族谱（供查询面板下拉框使用，不过滤权限）"""
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT clan_id, title FROM genealogies ORDER BY clan_id")).fetchall()
        return [{"clan_id": r[0], "title": r[1]} for r in rows]
    finally:
        db.close()


@app.get("/api/query/spouse_children")
def query_spouse_children(name: str):
    """查询某成员的所有配偶（通过共同子女推导）和子女"""
    db = SessionLocal()
    try:
        members = db.execute(
            text("SELECT member_id, clan_id FROM members WHERE name = :n"),
            {"n": name}
        ).fetchall()
        if not members:
            raise HTTPException(status_code=404, detail=f"找不到成员 [{name}]")

        all_spouses, all_children = [], []
        for member_id, clan_id in members:
            # 配偶（通过共同出现的儿女的父母字段推导）
            spouses = db.execute(text("""
                WITH target AS (
                    SELECT CAST(:mid AS BIGINT) AS mid
                ),
                children_of_target AS (
                    SELECT member_id, father_id, mother_id
                    FROM members
                    WHERE father_id = (SELECT mid FROM target)
                       OR mother_id = (SELECT mid FROM target)
                )
                SELECT DISTINCT
                    s.member_id,
                    s.name AS spouse_name,
                    s.gender,
                    s.birth_year
                FROM children_of_target c
                JOIN members s ON s.member_id = CASE
                    WHEN c.father_id = (SELECT mid FROM target) THEN c.mother_id
                    ELSE c.father_id
                END
                ORDER BY s.member_id
            """), {"mid": member_id}).fetchall()
            all_spouses.extend([{"name": r[1], "gender": r[2], "birth_year": r[3]} for r in spouses])

            # 子女
            children = db.execute(text("""
                SELECT name, gender, birth_year, generation_num
                FROM members WHERE father_id = :mid OR mother_id = :mid
                ORDER BY birth_year NULLS LAST
            """), {"mid": member_id}).fetchall()
            all_children.extend([dict(r._mapping) for r in children])

        return {"spouses": all_spouses, "children": all_children}
    finally:
        db.close()


@app.get("/api/query/ancestors")
def query_ancestors(name: str):
    """查询某成员的所有历代祖先（递归 CTE）"""
    db = SessionLocal()
    try:
        target = db.execute(
            text("SELECT member_id FROM members WHERE name = :n LIMIT 1"),
            {"n": name}
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"找不到成员 [{name}]")

        rows = db.execute(text("""
            WITH RECURSIVE ancestors AS (
                SELECT member_id, name, gender, birth_year, death_year,
                       father_id, mother_id, generation_num, 0 AS depth
                FROM members WHERE member_id = :mid
                UNION ALL
                SELECT m.member_id, m.name, m.gender, m.birth_year, m.death_year,
                       m.father_id, m.mother_id, m.generation_num, a.depth + 1
                FROM members m
                JOIN ancestors a ON m.member_id = a.father_id OR m.member_id = a.mother_id
            )
            SELECT DISTINCT member_id, name, gender, birth_year, death_year,
                            generation_num, depth
            FROM ancestors WHERE depth > 0
            ORDER BY depth, member_id
        """), {"mid": target[0]}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.get("/api/query/longevity")
def query_longevity(clan_id: int):
    """统计某族谱中各代平均寿命，按平均寿命降序排列"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT generation_num,
                   ROUND(AVG(death_year - birth_year)::NUMERIC, 2) AS avg_lifespan,
                   COUNT(*) AS count
            FROM members
            WHERE clan_id = :cid
              AND birth_year IS NOT NULL
              AND death_year IS NOT NULL
            GROUP BY generation_num
            ORDER BY avg_lifespan DESC NULLS LAST
        """), {"cid": clan_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.get("/api/query/singles")
def query_singles(clan_id: int = None):
    """查询年龄超过 50 岁的男性单身成员（无子女明确指向配偶记录）"""
    db = SessionLocal()
    try:
        clan_filter = "AND m.clan_id = :cid" if clan_id else ""
        params = {"cid": clan_id} if clan_id else {}
        rows = db.execute(text(f"""
            SELECT m.member_id, m.name, m.birth_year,
                   COALESCE(m.death_year, EXTRACT(YEAR FROM CURRENT_DATE)::INT) - m.birth_year AS estimated_age,
                   g.title AS clan_title
            FROM members m
            JOIN genealogies g ON g.clan_id = m.clan_id
            WHERE m.gender = 'M'
              AND m.birth_year IS NOT NULL
              AND COALESCE(m.death_year, EXTRACT(YEAR FROM CURRENT_DATE)::INT) - m.birth_year > 50
              {clan_filter}
              AND NOT EXISTS (
                  SELECT 1 FROM members c
                  WHERE c.father_id = m.member_id
                    AND c.mother_id IS NOT NULL
              )
              AND NOT EXISTS (
                  SELECT 1 FROM members c
                  WHERE c.mother_id = m.member_id
                    AND c.father_id IS NOT NULL
              )
            ORDER BY estimated_age DESC
            LIMIT 50
        """), params).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.get("/api/query/early_birth")
def query_early_birth(clan_id: int = None):
    """找出出生年份早于本代平均出生年份的所有成员"""
    db = SessionLocal()
    try:
        clan_filter = "AND clan_id = :cid" if clan_id else ""
        params = {"cid": clan_id} if clan_id else {}
        rows = db.execute(text(f"""
            WITH gen_avg AS (
                SELECT clan_id, generation_num, AVG(birth_year) AS avg_birth
                FROM members
                WHERE birth_year IS NOT NULL
                {clan_filter}
                GROUP BY clan_id, generation_num
            )
            SELECT m.member_id, m.clan_id, m.name, m.gender,
                   m.birth_year, m.generation_num,
                   ROUND(g.avg_birth::NUMERIC, 2) AS generation_avg,
                   ROUND((g.avg_birth - m.birth_year)::NUMERIC, 2) AS years_earlier
            FROM members m
            JOIN gen_avg g ON g.clan_id = m.clan_id AND g.generation_num = m.generation_num
            WHERE m.birth_year IS NOT NULL AND m.birth_year < g.avg_birth
            ORDER BY m.clan_id, m.generation_num, m.birth_year
        """), params).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        db.close()


@app.get("/api/query/great_grandchildren")
def query_great_grandchildren(name: str):
    """查询某个曾祖父的所有曾孙 (四代查询)"""
    db = SessionLocal()
    try:
        # 先根据名字找到匹配的 member_id
        m = db.execute(text("SELECT member_id FROM members WHERE name = :n LIMIT 1"), {"n": name}).fetchone()
        if not m:
            raise HTTPException(status_code=404, detail=f"找不到成员: {name}")
        member_id = m[0]

        rows = db.execute(text("""
            WITH RECURSIVE descendants AS (
                -- 第1代：作为起点
                SELECT member_id, 1 AS depth
                FROM members
                WHERE member_id = :mid
                
                UNION ALL
                
                -- 递归查询下一代
                SELECT m.member_id, d.depth + 1
                FROM members m
                JOIN descendants d ON m.father_id = d.member_id OR m.mother_id = d.member_id
                WHERE d.depth < 4
            )
            SELECT m.member_id, m.name, m.gender, m.generation_num, m.birth_year
            FROM descendants d
            JOIN members m ON d.member_id = m.member_id
            WHERE d.depth = 4
        """), {"mid": member_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()