from simpleeval import simple_eval
import datetime
import os
import json
import pymysql
from dbutils.pooled_db import PooledDB

def calculator(expression: str):
    result = simple_eval(expression)
    return str(result)
    
def get_weather(city: str):
    return simple_eval(city)
    
def get_weather(city: str):
    return f"{city}的天气是晴朗"

def get_time(format: str) -> str:
    # 模型可能传 Java 风格格式（yyyy-MM-dd HH:mm:ss EEEE），转成 Python strftime 指令
    java_to_python = {
        "yyyy": "%Y", "yy": "%y", "MM": "%m", "dd": "%d",
        "HH": "%H", "hh": "%I", "mm": "%M", "ss": "%S",
        "EEEE": "%A", "EEE": "%a",
    }
    for java, py in java_to_python.items():
        format = format.replace(java, py)
    return datetime.datetime.now().strftime(format)


# ---------- MySQL 用户信息存取 ----------
# 建表语句（在 MySQL 里执行一次）：
#   CREATE DATABASE IF NOT EXISTS gpt_teach CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#   CREATE TABLE IF NOT EXISTS gpt_teach.user_info (
#       id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#       user_id VARCHAR(64) NOT NULL,
#       info JSON NOT NULL,
#       created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
#       updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
#       UNIQUE KEY uk_user_id (user_id)
#   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

# _db_pool = None


# def _get_pool() -> PooledDB:
#     """懒加载全局连接池：只创建一次，多线程安全复用，避免每次请求都新建连接。"""
#     global _db_pool
#     if _db_pool is None:
#         _db_pool = PooledDB(
#             creator=pymysql,
#             maxconnections=10,   # 池上限
#             mincached=2,         # 空闲最小连接数
#             maxcached=5,         # 空闲最大连接数
#             blocking=True,       # 池满时阻塞等待而不是报错
#             host=os.getenv("MYSQL_HOST", "127.0.0.1"),
#             port=int(os.getenv("MYSQL_PORT", "3306")),
#             user=os.getenv("MYSQL_USER", "root"),
#             password=os.getenv("MYSQL_PASSWORD", ""),
#             database=os.getenv("MYSQL_DB", "miniagent"),
#             charset="utf8mb4",   # 中文支持
#             cursorclass=pymysql.cursors.DictCursor,
#         )
#     return _db_pool


# def save_user_info(user_id: str, info: dict) -> str:
#     """保存或更新用户信息（UPSERT）。返回给 LLM 的可读结果字符串。"""
#     if not user_id or not isinstance(info, dict):
#         return "参数错误：user_id 不能为空，info 必须是字典"

#     conn = _get_pool().connection()
#     try:
#         with conn.cursor() as cur:
#             # 参数化 SQL，防止 SQL 注入
#             sql = """
#                 INSERT INTO user_info (user_id, info)
#                 VALUES (%s, %s)
#                 ON DUPLICATE KEY UPDATE info = VALUES(info), updated_at = NOW()
#             """
#             cur.execute(sql, (user_id, json.dumps(info, ensure_ascii=False)))
#         conn.commit()
#         return f"用户 {user_id} 的信息已保存/更新"
#     except Exception as e:
#         conn.rollback()
#         return f"保存失败：{e}"
#     finally:
#         conn.close()  # 归还连接池，不是真的断开


# def get_user_info(user_id: str) -> str:
#     """按 user_id 查询用户信息，返回 JSON 字符串；不存在返回提示。"""
#     if not user_id:
#         return "参数错误：user_id 不能为空"

#     conn = _get_pool().connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 "SELECT info, created_at, updated_at FROM user_info WHERE user_id = %s",
#                 (user_id,),
#             )
#             row = cur.fetchone()
#         if row is None:
#             return f"未找到用户 {user_id} 的信息"
#         row["info"] = json.loads(row["info"])
#         return json.dumps(row, ensure_ascii=False)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
#     except Exception as e:
#         return f"查询失败：{e}"
#     finally:
#         conn.close()
user_profile = {}
def save_user_info(user_id:str, info:dict):
    user_id:str = user_id.strip()
    info:dict = info or {}
    user_profile[user_id] = info
    return "用户信息保存成功"


def get_user_info(user_id:str):
    user_id:str = user_id.strip()
    return user_profile.get(user_id, {})