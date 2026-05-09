from fastapi import FastAPI, HTTPException, Depends, Cookie, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import Optional
import base64, os
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
                    <div style="font-weight:bold; color:var(--primary); font-size: 1.2rem;">武大族谱系统 - 管理后台</div>
                    <div style="color: #64748b; font-size: 13px;">计算机学院 弘毅班 | 已登录</div>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <button id="btn-collab-current" onclick="openCurrentClanCollab()" style="display:none; background:#7c3aed; color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px; padding:4px 10px;">👥 管理协作者</button>
                        <button onclick="toggleClanView()" style="background:var(--primary); color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px; padding:4px 10px;">📚 我的族谱</button>
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
                                    </div>
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
                                    <button onclick="toggleClanView()" style="background:none; border:none; cursor:pointer; color:#94a3b8; font-size:18px; padding:0;">✕</button>
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
                    <div id="editMsg" style="font-size:13px; min-height:18px; color:var(--danger);"></div>
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

            <script>
                let myChart, pieChart;
                let DEFAULT_PIC = '';  // 启动时从 /api/default_pic 加载
                // 当前选中成员的 clan_id（用于权限检查和授权管理）
                let currentClanId = null;
                // 当前用户对 currentClanId 的权限
                let currentPerm = {{ can_edit: false, is_owner: false }};

                window.onload = async () => {{
                    try {{
                        const res = await fetch('/auth/me');
                        if (res.ok) {{ initCharts(); }}
                        else {{
                            document.getElementById('adminContent').style.display = 'none';
                            document.getElementById('loginOverlay').style.display = 'flex';
                        }}
                    }} catch(e) {{
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
                    if (!name) return;
                    const res = await fetch(`/members/search?name=${{encodeURIComponent(name)}}`);
                    const data = await res.json();

                    if (!data.length) {{
                        document.getElementById('search-results').innerHTML =
                            '<p style="color:#94a3b8;font-size:13px;text-align:center;margin-top:16px;">无结果</p>';
                        return;
                    }}

                    // ── 关键优化：一次请求批量获取所有涉及族谱的权限 ──
                    const uniqueClans = [...new Set(data.map(m => m.clan_id))];
                    const permMap = {{}};
                    const batchRes = await fetch(`/api/permissions/batch?clan_ids=${{uniqueClans.join(',')}}`);
                    const batchData = await batchRes.json();
                    uniqueClans.forEach(cid => {{ permMap[cid] = batchData[String(cid)] || {{}}; }});

                    // 一次性渲染，按权限直接插入按钮
                    let html = '';
                    data.forEach(m => {{
                        const perm = permMap[m.clan_id] || {{}};
                        let actionHtml = '';
                        if (perm.is_owner) {{
                            actionHtml = `
                                <span class="badge badge-owner">创建者</span>
                                <button class="btn-sm" onclick="openEditModal(${{m.id}})">编辑</button>
                                <button class="btn-danger" onclick="openDeleteModal(${{m.id}}, this)">删除</button>
                                <button class="btn-sm" style="background:#7c3aed" onclick="openCollabModal(${{m.clan_id}})">授权</button>`;
                        }} else if (perm.can_edit) {{
                            actionHtml = `
                                <span class="badge badge-collab">协作者</span>
                                <button class="btn-sm" onclick="openEditModal(${{m.id}})">编辑</button>
                                <button class="btn-danger" onclick="openDeleteModal(${{m.id}}, this)">删除</button>`;
                        }} else {{
                            actionHtml = `<span class="badge badge-readonly">只读</span>`;
                        }}
                        html += `
                        <div class="member-item">
                            <div class="member-item-left" onclick="loadTree(${{m.id}}, ${{m.clan_id}})">
                                <strong>${{m.name}}</strong>
                                <small style="margin-left:8px; color:#94a3b8;">第${{m.gen}}代</small>
                            </div>
                            <div style="display:flex;gap:4px;align-items:center;">
                                ${{actionHtml}}
                            </div>
                        </div>`;
                    }});
                    document.getElementById('search-results').innerHTML = html;
                }}

                // 点击成员名字加载族谱树，同时记录 clanId
                async function loadTree(id, clanId) {{
                    currentClanId = clanId;
                    const res = await fetch(`/members/${{id}}/ancestors`);
                    const list = await res.json();
                    const treeData = buildHierarchy(list, id);
                    myChart.setOption({{
                        series: [{{ type: 'tree', data: [treeData], label: {{ position: 'right' }} }}]
                    }});
                    // 同步更新当前权限
                    const pRes = await fetch(`/permissions/check/${{clanId}}`);
                    currentPerm = await pRes.json();

                    // 创建者才显示导航栏「管理协作者」按钮
                    const collabBtn = document.getElementById('btn-collab-current');
                    collabBtn.style.display = currentPerm.is_owner ? 'inline-block' : 'none';

                    // 数据概览切换为当前族谱统计
                    updateDashboard(clanId);
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
                    const memberId  = document.getElementById('edit_member_id').value;
                    const birthVal  = document.getElementById('edit_birth').value;
                    const deathVal  = document.getElementById('edit_death').value;
                    const msgEl     = document.getElementById('editMsg');
                    if (birthVal && deathVal && parseInt(birthVal) >= parseInt(deathVal)) {{
                        msgEl.style.color = 'var(--danger)';
                        msgEl.innerText = '出生年份必须早于去世年份';
                        return;
                    }}
                    msgEl.innerText = '';
                    const formData = new FormData();
                    formData.append('name', document.getElementById('edit_name').value);
                    formData.append('gender', document.getElementById('edit_gender').value);
                    formData.append('birth_year', birthVal);
                    formData.append('death_year', deathVal);
                    formData.append('bio', document.getElementById('edit_bio').value);
                    const res = await fetch(`/members/${{memberId}}/update`, {{ method: 'POST', body: formData }});
                    const data = await res.json();
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

                    const res = await fetch(url);
                    const data = await res.json();

                    msgEl.style.color = data.found ? 'var(--success)' : 'var(--danger)';
                    msgEl.innerText = data.message;

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

                // ── 工具 ─────────────────────────────────────────
                function openModal(id) {{ document.getElementById(id).classList.add('active'); }}
                function closeModal(id) {{ document.getElementById(id).classList.remove('active'); }}

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
@app.get("/api/permissions/batch")
def batch_check_permissions(clan_ids: str, request: Request):
    """
    批量查询多个族谱的权限，clan_ids 为逗号分隔的 id 字符串。
    返回 {clan_id: {can_edit, is_owner}, ...}
    """
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


@app.get("/api/default_pic")
def get_default_pic():
    return {"url": DEFAULT_PIC_DATA_URI}


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
def search_members(name: str):
    db = SessionLocal()
    try:
        results = db.execute(
            text("""
                SELECT member_id, clan_id, name, generation_num FROM members
                WHERE name LIKE :n
                ORDER BY
                    CASE WHEN name = :exact THEN 0 ELSE 1 END,
                    length(name),
                    member_id
                LIMIT 20
            """),
            {"n": f"%{name}%", "exact": name}
        ).all()
        return [{"id": r[0], "clan_id": r[1], "name": r[2], "gen": r[3]} for r in results]
    finally:
        db.close()


# ---------------------------------------------------------
# 成员详情（编辑表单回填用）
# ---------------------------------------------------------
@app.get("/members/{member_id}/detail")
def get_member_detail(member_id: int):
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT member_id, clan_id, name, gender, birth_year, death_year, bio, id_pic FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")
        return dict(row._mapping)
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
    bio: str = Form("")
):
    current_user = request.cookies.get("session_user")
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT clan_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")

        # ── 权限检查 ──
        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限，请联系族谱创建者授权")

        # ── 出生/死亡年份校验 ──
        if birth_year and death_year:
            try:
                if int(birth_year) >= int(death_year):
                    raise HTTPException(status_code=400, detail="出生年份必须早于去世年份")
            except ValueError:
                pass

        db.execute(
            text("""
                UPDATE members SET
                    name = :name,
                    gender = :gender,
                    birth_year = NULLIF(:birth, '')::INT,
                    death_year = NULLIF(:death, '')::INT,
                    bio = :bio
                WHERE member_id = :mid
            """),
            {
                "name": name, "gender": gender,
                "birth": birth_year, "death": death_year,
                "bio": bio, "mid": member_id
            }
        )
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
    id_b: int = None
):
    db = SessionLocal()
    try:
        # 若前端已精确指定 member_id，直接用；否则按姓名查
        if id_a and id_b:
            from search import _label_path, _bfs_relationship
            path = _bfs_relationship(db, id_a, id_b)
            if path:
                labeled = _label_path(db, path)
                return {
                    "found": True,
                    "message": f"存在亲缘关系，相距 {len(path)-1} 代",
                    "path": labeled,
                    "candidates_a": [],
                    "candidates_b": [],
                }
            else:
                return {
                    "found": False,
                    "message": "两人之间未发现亲缘关系（或超出可查范围）",
                    "path": [], "candidates_a": [], "candidates_b": [],
                }
        return find_relationship(db, name_a, name_b)
    finally:
        db.close()


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
            text("SELECT clan_id FROM members WHERE member_id = :mid"),
            {"mid": member_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="成员不存在")

        # ── 权限检查 ──
        if not check_edit_permission(db, row[0], current_user):
            raise HTTPException(status_code=403, detail="无编辑权限，请联系族谱创建者授权")

        db.execute(text("DELETE FROM members WHERE member_id = :mid"), {"mid": member_id})
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