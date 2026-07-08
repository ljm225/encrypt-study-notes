import os
import sys

# 获取当前文件所在目录的绝对路径
basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = "dev-key-2025"

# ---------- 用户数据库（明文密码，仅供教学演示）----------
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
    if username and username in USERS:
        # 取出完整的用户信息（包含密码），传给模板
        user_info = USERS[username]
    return render_template("index.html", username=username, user_info=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录路由：GET 显示表单，POST 验证身份"""
    error = None
    user_info = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # 直接从 USERS 字典中比对密码（字符串直接比较）
        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            user_info = USERS[username]  # 完整信息（含密码）传给模板
            return render_template("index.html", username=username, user_info=user_info)
        else:
            error = "用户名或密码错误，请重试。"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """登出：清除 session 后重定向到首页"""
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    # 确保 templates 和 static 目录存在
    os.makedirs(os.path.join(basedir, "templates"), exist_ok=True)
    os.makedirs(os.path.join(basedir, "static", "css"), exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
