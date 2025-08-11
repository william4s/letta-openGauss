#!/usr/bin/env python3
"""
Letta RAG系统Web集成安全审计示例
展示如何在Web应用中集成安全审计功能
"""

from flask import Flask, request, session, jsonify, render_template_string
import uuid
import os
import sys
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from audited_rag_system import AuditedQuickRAG
from security_audit import AuditEventType, AuditLevel, get_auditor

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 生产环境中使用随机密钥

# 全局RAG实例存储
rag_instances = {}

# 简单的HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Letta RAG 安全审计系统</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; color: #333; }
        .login-form, .chat-interface { margin: 20px 0; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, button { padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        input[type="text"], input[type="password"] { width: 300px; }
        textarea { width: 100%; height: 100px; resize: vertical; }
        button { background-color: #007bff; color: white; border: none; cursor: pointer; padding: 12px 20px; }
        button:hover { background-color: #0056b3; }
        .chat-history { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; max-height: 400px; overflow-y: auto; }
        .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
        .user-message { background-color: #e3f2fd; text-align: right; }
        .bot-message { background-color: #f1f8e9; }
        .audit-info { background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107; }
        .audit-report { background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .error { color: #dc3545; background-color: #f8d7da; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .success { color: #155724; background-color: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .risk-high { color: #721c24; background-color: #f5c6cb; }
        .risk-medium { color: #856404; background-color: #fff3cd; }
        .risk-low { color: #155724; background-color: #d4edda; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔒 Letta RAG 安全审计系统</h1>
            <p>集成安全审计功能的智能文档问答系统</p>
        </div>
        
        {% if not session.user_id %}
        <!-- 登录界面 -->
        <div class="login-form">
            <h2>用户登录</h2>
            <form method="POST" action="/login">
                <div class="form-group">
                    <label for="user_id">用户ID:</label>
                    <input type="text" id="user_id" name="user_id" required placeholder="请输入用户ID">
                </div>
                <div class="form-group">
                    <label for="password">密码:</label>
                    <input type="password" id="password" name="password" required placeholder="请输入密码">
                </div>
                <button type="submit">登录</button>
            </form>
        </div>
        {% else %}
        <!-- 聊天界面 -->
        <div class="audit-info">
            <strong>🔍 当前会话信息:</strong><br>
            用户: {{ session.user_id }} | 会话: {{ session.session_id[:8] }}... | IP: {{ session.ip_address }}
        </div>
        
        <div class="chat-interface">
            <h2>📚 文档问答</h2>
            
            {% if not session.rag_initialized %}
            <div class="form-group">
                <p>请先初始化RAG系统 (需要jr.pdf文件在当前目录):</p>
                <form method="POST" action="/init_rag">
                    <button type="submit">初始化RAG系统</button>
                </form>
            </div>
            {% else %}
            <div class="success">✅ RAG系统已就绪</div>
            
            <div class="chat-history" id="chatHistory">
                {% for msg in session.get('chat_history', []) %}
                <div class="message {{ 'user-message' if msg.type == 'user' else 'bot-message' }}">
                    <strong>{{ '👤 用户' if msg.type == 'user' else '🤖 助手' }}:</strong><br>
                    {{ msg.content }}
                    {% if msg.risk_score %}
                    <small class="risk-{{ 'high' if msg.risk_score >= 70 else 'medium' if msg.risk_score >= 40 else 'low' }}">
                        (风险评分: {{ msg.risk_score }})
                    </small>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            
            <form method="POST" action="/ask">
                <div class="form-group">
                    <label for="question">您的问题:</label>
                    <textarea id="question" name="question" required placeholder="请输入您的问题..."></textarea>
                </div>
                <button type="submit">发送问题</button>
            </form>
            {% endif %}
        </div>
        
        <!-- 审计报告 -->
        <div class="audit-report">
            <h3>📊 实时审计信息</h3>
            <form method="POST" action="/audit_report">
                <button type="submit">查看审计报告</button>
            </form>
            
            {% if audit_report %}
            <div style="margin-top: 15px;">
                <h4>最近1小时活动摘要:</h4>
                <ul>
                    <li>总事件数: {{ audit_report.total_events }}</li>
                    <li>系统健康: {{ audit_report.system_health }}</li>
                    <li>高风险事件: {{ audit_report.risk_distribution.high }}</li>
                    <li>错误事件: {{ audit_report.error_count }}</li>
                    <li>敏感数据访问: {{ audit_report.sensitive_data_access }}</li>
                </ul>
            </div>
            {% endif %}
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="/logout" style="color: #dc3545; text-decoration: none;">🚪 退出登录</a>
        </div>
        {% endif %}
        
        {% if error %}
        <div class="error">❌ {{ error }}</div>
        {% endif %}
        
        {% if success %}
        <div class="success">✅ {{ success }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    """用户登录"""
    user_id = request.form.get('user_id', '').strip()
    password = request.form.get('password', '').strip()
    
    # 简单的验证逻辑 (生产环境中应使用真实的认证系统)
    if not user_id or len(user_id) < 3:
        return render_template_string(HTML_TEMPLATE, error="用户ID至少3个字符")
    
    if not password or len(password) < 6:
        return render_template_string(HTML_TEMPLATE, error="密码至少6个字符")
    
    # 创建会话
    session_id = str(uuid.uuid4())
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    
    session['user_id'] = user_id
    session['session_id'] = session_id
    session['ip_address'] = ip_address
    session['user_agent'] = user_agent
    session['chat_history'] = []
    session['rag_initialized'] = False
    
    # 记录登录事件
    auditor = get_auditor()
    auditor.log_event(
        event_type=AuditEventType.AUTHENTICATION,
        level=AuditLevel.INFO,
        action="web_login",
        user_id=user_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"login_method": "web_form"},
        success=True
    )
    
    return render_template_string(HTML_TEMPLATE, success=f"欢迎 {user_id}！")

@app.route('/logout')
def logout():
    """用户登出"""
    user_id = session.get('user_id')
    session_id = session.get('session_id')
    
    if user_id:
        # 记录登出事件
        auditor = get_auditor()
        auditor.log_event(
            event_type=AuditEventType.USER_SESSION_END,
            level=AuditLevel.INFO,
            action="web_logout",
            user_id=user_id,
            session_id=session_id,
            ip_address=session.get('ip_address'),
            details={"logout_method": "web_link"},
            success=True
        )
        
        # 清理RAG实例
        if session_id in rag_instances:
            del rag_instances[session_id]
    
    session.clear()
    return render_template_string(HTML_TEMPLATE, success="已安全退出")

@app.route('/init_rag', methods=['POST'])
def init_rag():
    """初始化RAG系统"""
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE, error="请先登录")
    
    try:
        # 检查文件是否存在
        pdf_file = "./jr.pdf"
        if not os.path.exists(pdf_file):
            return render_template_string(HTML_TEMPLATE, error="找不到jr.pdf文件，请确保文件存在于当前目录")
        
        # 创建RAG实例
        rag = AuditedQuickRAG(
            user_id=session['user_id'],
            session_id=session['session_id'],
            ip_address=session['ip_address'],
            user_agent=session['user_agent']
        )
        
        # 构建RAG系统
        success = rag.build_rag_system(pdf_file)
        
        if success:
            rag_instances[session['session_id']] = rag
            session['rag_initialized'] = True
            return render_template_string(HTML_TEMPLATE, success="RAG系统初始化成功！")
        else:
            return render_template_string(HTML_TEMPLATE, error="RAG系统初始化失败")
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"初始化错误: {str(e)}")

@app.route('/ask', methods=['POST'])
def ask_question():
    """处理问答请求"""
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE, error="请先登录")
    
    if not session.get('rag_initialized'):
        return render_template_string(HTML_TEMPLATE, error="请先初始化RAG系统")
    
    question = request.form.get('question', '').strip()
    if not question:
        return render_template_string(HTML_TEMPLATE, error="请输入问题")
    
    try:
        # 获取RAG实例
        rag = rag_instances.get(session['session_id'])
        if not rag:
            session['rag_initialized'] = False
            return render_template_string(HTML_TEMPLATE, error="RAG实例不存在，请重新初始化")
        
        # 处理问题
        answer = rag.ask_question(question)
        
        # 计算风险评分 (从最后一个审计事件中获取)
        recent_events = rag.auditor.generate_audit_report(hours=0.1)  # 最近6分钟
        risk_score = 0
        if recent_events['total_events'] > 0:
            # 查找最近的查询事件
            for event in reversed(recent_events.get('event_types', [])):
                break  # 简化实现，实际应该解析具体事件
            risk_score = 15  # 默认风险评分
        
        # 保存聊天历史
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        session['chat_history'].append({
            'type': 'user',
            'content': question,
            'risk_score': risk_score
        })
        session['chat_history'].append({
            'type': 'bot', 
            'content': answer,
            'risk_score': None
        })
        
        # 保持聊天历史长度在合理范围
        if len(session['chat_history']) > 20:
            session['chat_history'] = session['chat_history'][-20:]
        
        session.modified = True
        
        return render_template_string(HTML_TEMPLATE)
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"处理问题时出错: {str(e)}")

@app.route('/audit_report', methods=['POST'])
def audit_report():
    """生成审计报告"""
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE, error="请先登录")
    
    try:
        auditor = get_auditor()
        report = auditor.generate_audit_report(hours=1)
        return render_template_string(HTML_TEMPLATE, audit_report=report)
    
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"生成审计报告时出错: {str(e)}")

@app.route('/api/user_activity/<user_id>')
def get_user_activity(user_id):
    """API: 获取用户活动摘要"""
    try:
        auditor = get_auditor()
        activity = auditor.get_user_activity_summary(user_id, hours=24)
        return jsonify(activity)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit_events')
def get_audit_events():
    """API: 获取审计事件"""
    try:
        hours = request.args.get('hours', 24, type=int)
        auditor = get_auditor()
        report = auditor.generate_audit_report(hours=hours)
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.before_request
def before_request():
    """请求前处理 - 记录API访问"""
    if request.endpoint and request.endpoint.startswith('api/'):
        # 记录API访问
        auditor = get_auditor()
        auditor.log_event(
            event_type=AuditEventType.QUERY_EXECUTION,
            level=AuditLevel.INFO,
            action="api_access",
            user_id=session.get('user_id', 'anonymous'),
            session_id=session.get('session_id'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            resource=request.endpoint,
            details={
                "method": request.method,
                "path": request.path,
                "args": dict(request.args)
            }
        )

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    auditor = get_auditor()
    auditor.log_event(
        event_type=AuditEventType.SYSTEM_ERROR,
        level=AuditLevel.WARN,
        action="page_not_found",
        user_id=session.get('user_id', 'anonymous'),
        session_id=session.get('session_id'),
        ip_address=request.remote_addr,
        resource=request.path,
        details={"error_code": 404},
        success=False
    )
    return render_template_string(HTML_TEMPLATE, error="页面不存在"), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    auditor = get_auditor()
    auditor.log_event(
        event_type=AuditEventType.SYSTEM_ERROR,
        level=AuditLevel.ERROR,
        action="internal_server_error",
        user_id=session.get('user_id', 'anonymous'),
        session_id=session.get('session_id'),
        ip_address=request.remote_addr,
        resource=request.path,
        details={
            "error_code": 500,
            "error_message": str(error)
        },
        success=False
    )
    return render_template_string(HTML_TEMPLATE, error="服务器内部错误"), 500

def main():
    """启动Web应用"""
    print("🌐 启动Letta RAG Web安全审计系统")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5001")
    print("测试用户: 任意用户ID (至少3个字符)")
    print("测试密码: 任意密码 (至少6个字符)")
    print("确保当前目录有 jr.pdf 文件")
    print("=" * 50)
    
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    # 启动应用
    app.run(debug=True, host='127.0.0.1', port=5001)

if __name__ == "__main__":
    main()
