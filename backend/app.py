import os
import hashlib
import uuid
import json
import sys
import statistics
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
from collections import Counter
from flask import send_from_directory
from pathlib import Path
# ==================== 配置初始化 ====================

# ==================== 修复环境变量问题 ====================
# 如果环境变量不存在，直接设置默认值
if not os.getenv("SUPABASE_URL"):
    os.environ["SUPABASE_URL"] = "https://veffyhfyxydywjapjpgl.supabase.co"
    os.environ["SUPABASE_KEY"] = "eyJhb6ci0iJIUzI1NiISInRo5cCI6IKpXVCJ9.eyJpc35Mi0iJzdXBhYmFzZSIsSInJLZiI6InZLZmZ5a6Z5eHLKeXdqYXBqc6dsIIi"
    os.environ["TEACHER_USERNAME"] = "admin" 
    os.environ["TEACHER_PASSWORD"] = "654321"
    print("使用硬编码的环境变量")
else:
    print("使用Vercel环境变量")
# ==================== 修复结束 ====================
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

current_dir = Path(__file__).parent
frontend_dir = current_dir.parent / 'frontend'
if frontend_dir.exists():
    sys.path.append(str(frontend_dir))

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 教师账号配置
TEACHER_USERNAME = os.getenv("TEACHER_USERNAME")
TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD")


# ==================== 工具函数 ====================
def hash_password(password):
    """密码加密"""
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def generate_teacher_token():
    """生成教师认证令牌"""
    return hash_password(f"{TEACHER_USERNAME}-{TEACHER_PASSWORD}-{datetime.now().timestamp()}")


def verify_teacher(username, password):
    """验证教师身份"""
    return username == TEACHER_USERNAME and hash_password(password) == hash_password(TEACHER_PASSWORD)


def verify_teacher_token(token):
    """验证教师令牌"""
    return token is not None


def normalize_answer(answer):
    """规范化答案比较（去除首尾空格，忽略大小写）"""
    if not answer:
        return ""
    return answer.strip().lower()


def format_time_display(seconds):
    """格式化时间显示"""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"

from flask import send_from_directory

# 提供前端静态文件
@app.route('/')
def serve_frontend():
    return send_from_directory('../frontend', 'index.html')

# 提供前端静态资源（CSS、JS等）
@app.route('/<path:path>')
def serve_static_files(path):
    return send_from_directory('../frontend', path)



# ==================== 教师认证模块 ====================
@app.route("/api/teacher/login", methods=["POST"])
def teacher_login():
    """教师登录"""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if verify_teacher(username, password):
        token = generate_teacher_token()
        return jsonify({
            "success": True,
            "token": token,
            "message": "登录成功"
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": "用户名或密码错误"
        }), 401


def update_teacher_credentials(new_username, new_password):
    """更新教师凭据到环境变量文件"""
    try:
        env_path = '.env'
        if not os.path.exists(env_path):
            return False, "环境配置文件不存在"

        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated = False
        new_lines = []
        for line in lines:
            if line.startswith('TEACHER_USERNAME='):
                new_lines.append(f'TEACHER_USERNAME={new_username}\n')
                updated = True
            elif line.startswith('TEACHER_PASSWORD='):
                new_lines.append(f'TEACHER_PASSWORD={new_password}\n')
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f'TEACHER_USERNAME={new_username}\n')
            new_lines.append(f'TEACHER_PASSWORD={new_password}\n')

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        os.environ['TEACHER_USERNAME'] = new_username
        os.environ['TEACHER_PASSWORD'] = new_password

        return True, "更新成功"
    except Exception as e:
        return False, f"更新失败: {str(e)}"


@app.route("/api/teacher/update-account", methods=["POST"])
def update_teacher_account():
    """更新教师账号信息"""
    global TEACHER_USERNAME, TEACHER_PASSWORD

    token = request.headers.get("Authorization")
    if not token or not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    data = request.get_json()
    new_username = data.get("new_username")
    new_password = data.get("new_password")
    current_password = data.get("current_password")

    if not new_username or not new_password or not current_password:
        return jsonify({"error": "请填写所有字段"}), 400

    if not verify_teacher(TEACHER_USERNAME, current_password):
        return jsonify({"error": "当前密码错误"}), 401

    try:
        success, message = update_teacher_credentials(new_username, new_password)

        if success:
            TEACHER_USERNAME = new_username
            TEACHER_PASSWORD = new_password

            return jsonify({
                "success": True,
                "message": "账号信息已更新，请重新登录"
            }), 200
        else:
            return jsonify({"error": message}), 500

    except Exception as e:
        print(f"更新账号失败: {str(e)}")
        return jsonify({"error": f"更新账号失败：{str(e)}"}), 500


# ==================== 图片管理模块 ====================
@app.route("/api/upload-image", methods=["POST"])
def upload_image():
    """上传题目图片"""
    token = request.headers.get("Authorization")
    if not token or not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    print("=== 开始图片上传处理 ===")

    if "image" not in request.files:
        print("错误: 未找到image字段")
        return jsonify({"error": "未上传图片"}), 400

    file = request.files["image"]
    if file.filename == "":
        print("错误: 文件名为空")
        return jsonify({"error": "未选择图片"}), 400

    print(f"接收文件: {file.filename}, 类型: {file.content_type}, 大小: {len(file.read())}")

    file.seek(0)

    allowed_extensions = {"png", "jpg", "jpeg", "gif"}
    file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ""

    if file_ext not in allowed_extensions:
        print(f"错误: 不支持的格式: {file_ext}")
        return jsonify({"error": "仅支持png、jpg、jpeg、gif格式"}), 400

    try:
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_data = file.read()

        if len(file_data) == 0:
            raise Exception("文件数据为空")

        print(f"文件数据大小: {len(file_data)} 字节")

        upload_response = supabase.storage.from_("question-images").upload(
            file=file_data,
            path=filename,
            file_options={"content-type": file.content_type}
        )

        if hasattr(upload_response, 'error') and upload_response.error:
            raise Exception(f"图片上传失败: {upload_response.error}")

        print("图片上传成功")

        public_url_response = supabase.storage.from_("question-images").get_public_url(filename)

        if hasattr(public_url_response, 'public_url'):
            public_url = public_url_response.public_url
        else:
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/question-images/{filename}"

        print(f"生成的公开URL: {public_url}")

        return jsonify({
            "success": True,
            "image_url": public_url
        }), 200

    except Exception as e:
        print(f"图片上传错误: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        print(f"错误堆栈:\n{error_details}")
        return jsonify({"error": f"图片上传失败：{str(e)}"}), 500


# ==================== 题目管理模块 ====================
@app.route("/api/questions", methods=["POST"])
def add_question():
    """添加新题目"""
    token = request.headers.get("Authorization")
    if not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    data = request.get_json()
    title = data.get("title")
    answers = data.get("answers")
    image_url = data.get("image_url")

    if not title or not answers or not isinstance(answers, list) or len(answers) == 0:
        return jsonify({"error": "题目标题和答案不能为空"}), 400

    try:
        response = supabase.table("questions").insert({
            "id": str(uuid.uuid4()),
            "title": title,
            "answers": answers,
            "image_url": image_url,
            "created_at": datetime.now().isoformat()
        }).execute()
        return jsonify({
            "success": True,
            "message": "题目添加成功",
            "data": response.data[0]
        }), 201
    except Exception as e:
        return jsonify({"error": f"添加失败：{str(e)}"}), 500




# ==================== 学生答题模块 ====================
@app.route("/api/student/login", methods=["POST"])
def student_login():
    """学生登录"""
    try:
        data = request.get_json()
        print(f"=== 学生登录请求 ===")
        print(f"请求数据: {data}")

        if not data:
            return jsonify({"error": "请求数据为空"}), 400

        name = data.get("name")
        print(f"获取到的姓名: {name}")

        if not name:
            return jsonify({"error": "请输入姓名"}), 400

        student_id = str(uuid.uuid4())
        response_data = {
            "success": True,
            "student_id": student_id,
            "name": name
        }
        print(f"返回数据: {response_data}")
        return jsonify(response_data), 200

    except Exception as e:
        print(f"学生登录异常: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return jsonify({"error": f"登录处理失败：{str(e)}"}), 500


@app.route("/api/student/quiz", methods=["GET"])
def get_quiz():
    """获取所有题目用于答题"""
    try:
        response = supabase.table("questions").select("*").execute()
        if not response.data:
            return jsonify({"error": "暂无题目"}), 404
        return jsonify({"data": response.data}), 200
    except Exception as e:
        return jsonify({"error": f"获取题目失败：{str(e)}"}), 500


@app.route("/api/student/submit", methods=["POST"])
def submit_answer():
    data = request.get_json()
    student_id = data.get("student_id")
    student_name = data.get("name")
    question_id = data.get("question_id")
    user_answers = data.get("answers")
    time_used = data.get("time_used")
    hint_used = data.get("hint_used", False)

    if not all([student_id, student_name, question_id, user_answers]):
        return jsonify({"error": "提交数据不完整"}), 400

    try:
        # 获取正确答案
        question_response = supabase.table("questions").select("*").eq("id", question_id).execute()
        if not question_response.data:
            return jsonify({"error": "题目不存在"}), 404

        question = question_response.data[0]
        correct_answers = question["answers"]

        # 计算正确数量并保存答案对比
        correct_count = 0
        answer_comparison = []  # 新增：存储每个答案的对比结果

        for i, (user_answer, correct_answer) in enumerate(zip(user_answers, correct_answers)):
            norm_user = normalize_answer(user_answer)
            norm_correct = normalize_answer(correct_answer)

            is_correct = norm_user == norm_correct
            if is_correct:
                correct_count += 1

            answer_comparison.append({
                "index": i,
                "student_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })

        total_count = len(correct_answers)
        accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0

        print(f"答案比较详情:")
        print(f"用户答案: {user_answers}")
        print(f"正确答案: {correct_answers}")
        print(f"正确数量: {correct_count}/{total_count}")
        print(f"答案对比数据: {answer_comparison}")

        # 检查是否已有该学生的总体记录
        existing_record = supabase.table("student_overall_records").select("*").eq("student_id", student_id).execute()

        if existing_record.data:
            # 更新现有记录
            record = existing_record.data[0]
            new_total_correct = record["total_correct"] + correct_count
            new_total_questions = record["total_questions"] + total_count
            new_total_time = record["total_time"] + time_used

            update_response = supabase.table("student_overall_records").update({
                "total_correct": new_total_correct,
                "total_questions": new_total_questions,
                "total_time": new_total_time,
                "accuracy": (new_total_correct / new_total_questions) * 100,
                "last_submitted_at": datetime.now().isoformat()
            }).eq("student_id", student_id).execute()
        else:
            # 创建新记录
            new_record = {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "student_name": student_name,
                "total_correct": correct_count,
                "total_questions": total_count,
                "total_time": time_used,
                "accuracy": accuracy,
                "last_submitted_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            }
            supabase.table("student_overall_records").insert(new_record).execute()

        # 同时保存详细答题记录，包含具体答案对比
        detail_record = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "student_name": student_name,
            "question_id": question_id,
            "correct_count": correct_count,
            "total_count": total_count,
            "accuracy": accuracy,
            "time_used": time_used,
            "hint_used": hint_used,
            "answer_comparison": answer_comparison,  # 新增：存储答案对比详情
            "submitted_at": datetime.now().isoformat()
        }
        supabase.table("records").insert(detail_record).execute()

        return jsonify({
            "success": True,
            "score": f"{correct_count}/{total_count}",
            "accuracy": f"{accuracy:.1f}%",
            "correct_answers": correct_answers,
            "answer_comparison": answer_comparison,  # 返回答案对比详情
            "debug_info": {
                "user_answers": user_answers,
                "normalized_user_answers": [normalize_answer(a) for a in user_answers],
                "normalized_correct_answers": [normalize_answer(a) for a in correct_answers]
            }
        }), 200

    except Exception as e:
        print(f"提交失败: {str(e)}")
        return jsonify({"error": f"提交失败：{str(e)}"}), 500


# ==================== 数据分析模块 ====================
@app.route("/api/analysis/student/<student_id>", methods=["GET"])
def get_student_analysis(student_id):
    """获取学生详细分析数据"""
    token = request.headers.get("Authorization")
    if not token or not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    try:
        overall_response = supabase.table("student_overall_records").select("*").eq("student_id", student_id).execute()

        if not overall_response.data:
            return jsonify({"error": "学生记录不存在"}), 404

        overall_record = overall_response.data[0]

        detail_response = supabase.table("records").select("*").eq("student_id", student_id).order(
            "submitted_at").execute()
        detail_records = detail_response.data

        questions_response = supabase.table("questions").select("*").execute()
        questions = {q["id"]: q for q in questions_response.data}

        return jsonify({
            "success": True,
            "student_info": {
                "student_id": overall_record["student_id"],
                "student_name": overall_record["student_name"],
                "total_questions": overall_record["total_questions"],
                "total_correct": overall_record["total_correct"],
                "overall_accuracy": overall_record["accuracy"],
                "total_time": overall_record["total_time"],
                "last_submission": overall_record["last_submitted_at"]
            },
            "detail_records": detail_records,
            "questions": questions
        }), 200

    except Exception as e:
        print(f"学生分析失败: {str(e)}")
        return jsonify({"error": f"分析失败：{str(e)}"}), 500


@app.route("/api/analysis/students", methods=["GET"])
def get_all_students_analysis():
    """获取所有学生的分析概览"""
    token = request.headers.get("Authorization")
    if not token or not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    try:
        overall_response = supabase.table("student_overall_records").select("*").order("accuracy", desc=True).execute()
        students = overall_response.data

        analysis_data = []
        for student in students:
            detail_response = supabase.table("records").select("*").eq("student_id", student["student_id"]).order(
                "submitted_at", desc=True).limit(10).execute()
            recent_records = detail_response.data

            improvement = calculate_student_improvement(recent_records)

            analysis_data.append({
                "student_id": student["student_id"],
                "student_name": student["student_name"],
                "overall_accuracy": student["accuracy"],
                "total_questions": student["total_questions"],
                "total_correct": student["total_correct"],
                "total_time": student["total_time"],
                "improvement": improvement,
                "last_active": student["last_submitted_at"]
            })

        return jsonify({
            "success": True,
            "students": analysis_data
        }), 200

    except Exception as e:
        print(f"学生分析概览失败: {str(e)}")
        return jsonify({"error": f"分析失败：{str(e)}"}), 500


def calculate_student_improvement(records):
    """计算学生进步情况"""
    if len(records) < 2:
        return "数据不足"

    recent_avg = statistics.mean([r["accuracy"] for r in records[:3]])
    older_avg = statistics.mean([r["accuracy"] for r in records[-3:]])

    improvement = recent_avg - older_avg

    if improvement > 10:
        return "显著进步"
    elif improvement > 5:
        return "有所进步"
    elif improvement > -5:
        return "保持稳定"
    elif improvement > -10:
        return "略有下降"
    else:
        return "明显下降"


# ==================== 记录管理模块 ====================
@app.route("/api/records", methods=["GET"])
def get_records():
    """获取所有学生记录"""
    token = request.headers.get("Authorization")
    if not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    try:
        response = supabase.table("student_overall_records").select("*").order("last_submitted_at", desc=True).execute()
        return jsonify({"data": response.data}), 200
    except Exception as e:
        return jsonify({"error": f"查询失败：{str(e)}"}), 500


@app.route("/api/records/clear", methods=["DELETE"])
def clear_records():
    """清空所有记录"""
    token = request.headers.get("Authorization")
    if not token or not verify_teacher_token(token):
        return jsonify({"error": "未授权访问"}), 401

    print("=== 开始清空记录 ===")

    try:
        print("清空 student_overall_records 表...")
        records = supabase.table("student_overall_records").select("*").execute()
        deleted_count = 0

        if records.data:
            for record in records.data:
                try:
                    supabase.table("student_overall_records").delete().eq("id", record["id"]).execute()
                    deleted_count += 1
                except Exception as e:
                    print(f"删除记录 {record['id']} 失败: {e}")

            print(f"已删除 {deleted_count} 条总体记录")

        print("清空 records 表...")
        detail_records = supabase.table("records").select("*").execute()
        detail_deleted_count = 0

        if detail_records.data:
            for record in detail_records.data:
                try:
                    supabase.table("records").delete().eq("id", record["id"]).execute()
                    detail_deleted_count += 1
                except Exception as e:
                    print(f"删除详细记录 {record['id']} 失败: {e}")

            print(f"已删除 {detail_deleted_count} 条详细记录")

        return jsonify({
            "success": True,
            "message": f"所有答题记录已清空（总体记录: {deleted_count} 条，详细记录: {detail_deleted_count} 条）"
        }), 200

    except Exception as e:
        print(f"清空记录失败: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")
        return jsonify({"error": f"清空记录失败：{str(e)}"}), 500


# ==================== 系统工具接口 ====================
@app.route("/api/debug/answer-comparison", methods=["POST"])
def debug_answer_comparison():
    """调试答案比较问题"""
    data = request.get_json()
    user_answer = data.get("user_answer", "")
    correct_answer = data.get("correct_answer", "")

    norm_user = normalize_answer(user_answer)
    norm_correct = normalize_answer(correct_answer)

    return jsonify({
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "normalized_user": norm_user,
        "normalized_correct": norm_correct,
        "are_equal": norm_user == norm_correct,
        "user_length": len(user_answer),
        "correct_length": len(correct_answer),
        "normalized_user_length": len(norm_user),
        "normalized_correct_length": len(norm_correct)
    })


@app.route("/api/test", methods=["GET", "POST"])
def test_endpoint():
    """测试接口"""
    print("=== 测试端点被调用 ===")
    print(f"方法: {request.method}")
    print(f"头信息: {dict(request.headers)}")
    if request.method == "POST":
        data = request.get_json()
        print(f"请求数据: {data}")
    return jsonify({"status": "ok", "message": "测试成功"})


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok", "message": "服务正常运行"}), 200


# ==================== 启动配置 ====================
def test_supabase_connection():
    """测试Supabase连接"""
    try:
        print("=== 测试Supabase连接 ===")

        test_db = supabase.table("questions").select("id").limit(1).execute()
        print(f"数据库连接测试: {len(test_db.data)} 条记录")

        try:
            buckets = supabase.storage.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]
            print(f"可用存储桶: {bucket_names}")

            if "question-images" in bucket_names:
                print("✓ question-images 存储桶存在")
                try:
                    files = supabase.storage.from_("question-images").list()
                    print(f"存储桶文件数量: {len(files)}")
                except Exception as bucket_error:
                    print(f"存储桶访问测试失败: {bucket_error}")
            else:
                print("✗ question-images 存储桶不存在")

        except Exception as storage_error:
            print(f"存储桶列表获取失败: {storage_error}")

    except Exception as e:
        print(f"Supabase连接测试失败: {e}")


if __name__ == "__main__":
    test_supabase_connection()
    app.run(host="0.0.0.0", port=5000, debug=True)
