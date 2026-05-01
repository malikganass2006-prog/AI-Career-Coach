import os
import json
import mysql.connector
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

def _conn():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'InterviewAI'),
        autocommit=True
    )

def init_db():
    db_name = os.environ.get('DB_NAME', 'InterviewAI')
    bootstrap = mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        autocommit=True
    )
    bootstrap.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    bootstrap.close()

    conn = _conn()
    cur = conn.cursor()

    # Users — includes profile fields + updated_at (was missing in old init_db)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INT PRIMARY KEY AUTO_INCREMENT,
            full_name       VARCHAR(255) NOT NULL,
            email           VARCHAR(255) UNIQUE NOT NULL,
            password        VARCHAR(255) NOT NULL,
            phone           VARCHAR(50)  DEFAULT NULL,
            bio             TEXT         DEFAULT NULL,
            linkedin        VARCHAR(255) DEFAULT NULL,
            github          VARCHAR(255) DEFAULT NULL,
            profile_picture VARCHAR(255) DEFAULT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # Migrate existing tables: add any missing columns safely
    _add_col(cur, 'users', 'phone',           'VARCHAR(50)  DEFAULT NULL AFTER password')
    _add_col(cur, 'users', 'bio',             'TEXT         DEFAULT NULL AFTER phone')
    _add_col(cur, 'users', 'linkedin',        'VARCHAR(255) DEFAULT NULL AFTER bio')
    _add_col(cur, 'users', 'github',          'VARCHAR(255) DEFAULT NULL AFTER linkedin')
    _add_col(cur, 'users', 'profile_picture', 'VARCHAR(255) DEFAULT NULL AFTER github')
    _add_col(cur, 'users', 'updated_at',
             'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            email      VARCHAR(255) PRIMARY KEY,
            code       VARCHAR(10),
            token      VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # Interviews — added cv_filename + FK
    cur.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            interview_id VARCHAR(100) PRIMARY KEY,
            user_id      INT,
            field        VARCHAR(255),
            cv_filename  VARCHAR(255) DEFAULT NULL,
            cv_analysis  JSON,
            answers      JSON,
            feedback     JSON,
            courses      JSON,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    _add_col(cur, 'interviews', 'cv_filename', 'VARCHAR(255) DEFAULT NULL AFTER field')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cv_uploads (
            id            INT PRIMARY KEY AUTO_INCREMENT,
            user_id       INT NOT NULL,
            filename      VARCHAR(500) NOT NULL,
            filepath      VARCHAR(500) NOT NULL DEFAULT '',
            original_name VARCHAR(255) DEFAULT NULL,
            field         VARCHAR(255) DEFAULT NULL,
            cv_text       MEDIUMTEXT   DEFAULT NULL,
            analysis      JSON         DEFAULT NULL,
            uploaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    _add_col(cur, 'cv_uploads', 'original_name', 'VARCHAR(255) DEFAULT NULL AFTER filename')

    cur.close()
    conn.close()


def _add_col(cur, table, column, definition):
    """Add a column only if it does not already exist."""
    db = os.environ.get('DB_NAME', 'InterviewAI')
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
    """, (db, table, column))
    (n,) = cur.fetchone()
    if n == 0:
        cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(name, email, password):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)",
        (name, email, password)
    )
    uid = cur.lastrowid
    cur.close(); conn.close()
    return uid

def get_user_by_email(email):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def get_user_by_id(user_id):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def email_exists(email):
    return get_user_by_email(email) is not None

def update_password(email, new_password):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password=%s WHERE email=%s", (new_password, email))
    cur.close(); conn.close()

def update_user_profile(user_id, full_name, phone, bio, linkedin, github):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET full_name=%s, phone=%s, bio=%s, linkedin=%s, github=%s
        WHERE id=%s
    """, (full_name, phone, bio, linkedin, github, user_id))
    cur.close(); conn.close()

def update_profile_picture(user_id, filename):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET profile_picture=%s WHERE id=%s", (filename, user_id))
    cur.close(); conn.close()


# ── Password Reset ─────────────────────────────────────────────────────────────

def save_reset_code(email, code):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO password_resets (email, code, token) VALUES (%s, %s, NULL)
        ON DUPLICATE KEY UPDATE code=%s, token=NULL, created_at=CURRENT_TIMESTAMP
    """, (email, code, code))
    cur.close(); conn.close()

def get_reset_entry(email):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM password_resets WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def save_reset_token(email, token):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("UPDATE password_resets SET token=%s WHERE email=%s", (token, email))
    cur.close(); conn.close()

def get_email_by_token(token):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT email FROM password_resets WHERE token=%s", (token,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row['email'] if row else None

def delete_reset_code(email):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM password_resets WHERE email=%s", (email,))
    cur.close(); conn.close()

def reset_password_direct(email, new_password):
    if not email_exists(email):
        return False
    update_password(email, new_password)
    return True


def save_cv_upload(user_id, filename, original_name, field):
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cv_uploads (user_id, filename, filepath, original_name, field) VALUES (%s, %s, %s, %s, %s)",
        (user_id, filename, filename, original_name, field)
    )
    cur.close(); conn.close()

def get_user_cvs(user_id):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, filename, COALESCE(original_name, filename) AS original_name, field, uploaded_at FROM cv_uploads WHERE user_id=%s ORDER BY uploaded_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close(); conn.close()
    for row in rows:
        if row.get('uploaded_at'):
            row['uploaded_at'] = row['uploaded_at'].isoformat()
    return rows


# ── Interviews ─────────────────────────────────────────────────────────────────

def save_interview(interview_id, user_id, field, cv_analysis, answers, feedback, courses, cv_filename=None):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO interviews
            (interview_id, user_id, field, cv_filename, cv_analysis, answers, feedback, courses)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            answers=VALUES(answers), feedback=VALUES(feedback),
            courses=VALUES(courses), cv_filename=VALUES(cv_filename),
            completed_at=CURRENT_TIMESTAMP
    """, (
        interview_id, user_id, field, cv_filename,
        json.dumps(cv_analysis), json.dumps(answers),
        json.dumps(feedback), json.dumps(courses)
    ))
    cur.close(); conn.close()

def get_interview(interview_id):
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM interviews WHERE interview_id=%s", (interview_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return None
    for key in ('cv_analysis', 'answers', 'feedback', 'courses'):
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    return row

def get_user_interviews(user_id):
    """All interviews for a user — lightweight list (no answers blob)."""
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT interview_id, field, cv_filename, feedback, courses, completed_at
        FROM interviews WHERE user_id=%s ORDER BY completed_at DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    for row in rows:
        for key in ('feedback', 'courses'):
            if isinstance(row.get(key), str):
                try:
                    row[key] = json.loads(row[key])
                except Exception:
                    row[key] = {}
        if row.get('completed_at'):
            row['completed_at'] = row['completed_at'].isoformat()
    return rows

def get_user_stats(user_id):
    """Aggregate stats for the profile page."""
    conn = _conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT COUNT(*) AS total_interviews,
               COUNT(DISTINCT field) AS fields_explored,
               MIN(completed_at) AS first_interview,
               MAX(completed_at) AS last_interview
        FROM interviews WHERE user_id=%s
    """, (user_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row:
        for k in ('first_interview', 'last_interview'):
            if row.get(k):
                row[k] = row[k].isoformat()
    return row or {}
