import os
import sys
import sqlite3

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory

app = Flask(__name__)
app.secret_key = "dev-key-2025"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB


# ============================================================
# 初始化 SQLite 数据库（教学演示，故意使用明文和 SQL 拼接）
# ============================================================
def init_db():
    """初始化数据库，创建 users 表并插入默认用户"""
    db_dir = os.path.join(basedir, "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "users.db")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 创建 users 表
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)

    # 插入默认用户（INSERT OR IGNORE 防止重复插入）
    default_users = [
        ("admin", "admin123", "admin@example.com", "13800138000"),
        ("alice", "alice2025", "alice@example.com", "13900139001"),
    ]
    for u in default_users:
        c.execute(
            "INSERT OR IGNORE INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
            u
        )

    conn.commit()
    conn.close()
    print("[DB] 数据库初始化完成")


# ---------- 原有用户字典（登录功能不变）----------
USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "password": "alice2025",
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    }
}


@app.route("/")
def index():
    """首页：从 session 获取当前登录用户，传递给模板"""
    username = session.get("username")
    user_info = None
    search_results = None
    keyword = None

    if username and username in USERS:
        user_info = USERS[username]

    # 处理搜索（仅登录用户可用）
    keyword = request.args.get("keyword", "").strip()
    if keyword and username and username in USERS:
        db_path = os.path.join(basedir, "data", "users.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # 故意使用 f-string 拼接 SQL（教学演示 SQL 注入漏洞）
        sql = f"SELECT id, username, email, phone FROM users WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'"
        print(f"[SQL] 执行查询: {sql}")
        try:
            c.execute(sql)
            search_results = c.fetchall()
        except Exception as e:
            print(f"[SQL] 查询出错: {e}")
            search_results = []
        conn.close()

    return render_template("index.html",
                           username=username,
                           user_info=user_info,
                           search_results=search_results,
                           keyword=keyword)


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录路由：GET 显示表单，POST 验证身份"""
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            user_info = USERS[username]
            return render_template("index.html", username=username, user_info=user_info)
        else:
            error = "用户名或密码错误，请重试。"

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    """注册路由：GET 显示表单，POST 插入用户"""
    message = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        # 故意使用 f-string 拼接 SQL（教学演示 SQL 注入漏洞）
        db_path = os.path.join(basedir, "data", "users.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        sql = f"INSERT INTO users (username, password, email, phone) VALUES ('{username}', '{password}', '{email}', '{phone}')"
        print(f"[SQL] 执行插入: {sql}")
        try:
            c.execute(sql)
            conn.commit()
            print(f"[SQL] 注册成功: {username}")
            # 注册成功，跳转到登录页并提示
            conn.close()
            return redirect("/login?msg=注册成功，请登录")
        except Exception as e:
            print(f"[SQL] 注册失败: {e}")
            message = f"注册失败: {e}"
            conn.close()

    return render_template("register.html", message=message)


@app.route("/search")
def search():
    """搜索路由：通过 URL 参数 keyword 搜索用户"""
    username = session.get("username")
    if not username or username not in USERS:
        return redirect("/")

    keyword = request.args.get("keyword", "")
    search_results = []
    db_path = os.path.join(basedir, "data", "users.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 故意使用 f-string 拼接 SQL（教学演示 SQL 注入漏洞）
    sql = f"SELECT id, username, email, phone FROM users WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'"
    print(f"[SQL] 执行查询: {sql}")
    try:
        c.execute(sql)
        search_results = c.fetchall()
    except Exception as e:
        print(f"[SQL] 查询出错: {e}")
    conn.close()

    user_info = USERS[username]
    return render_template("index.html",
                           username=username,
                           user_info=user_info,
                           search_results=search_results,
                           keyword=keyword)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """用户头像上传路由：GET 显示表单，POST 处理上传"""
    username = session.get("username")
    if not username or username not in USERS:
        return redirect("/login")

    upload_result = None
    upload_error = None

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename:
            try:
                # 使用用户上传的原始文件名保存，不检查后缀和内容
                upload_dir = os.path.join(basedir, "static", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                save_path = os.path.join(upload_dir, file.filename)
                file.save(save_path)
                file_url = url_for('uploaded_file', filename=file.filename)
                upload_result = {
                    "filename": file.filename,
                    "url": file_url,
                    "size": os.path.getsize(save_path)
                }
                print(f"[UPLOAD] 文件上传成功: {file.filename} → {save_path}")
            except Exception as e:
                upload_error = f"上传失败: {str(e)}"
                print(f"[UPLOAD] 上传出错: {e}")
        else:
            upload_error = "请选择要上传的文件"

    return render_template("upload.html",
                           username=username,
                           upload_result=upload_result,
                           upload_error=upload_error)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """提供上传文件的访问"""
    return send_from_directory(os.path.join(basedir, "static", "uploads"), filename)


@app.route("/logout")
def logout():
    """登出：清除 session 后重定向到首页"""
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()
    os.makedirs(os.path.join(basedir, "templates"), exist_ok=True)
    os.makedirs(os.path.join(basedir, "static", "css"), exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
