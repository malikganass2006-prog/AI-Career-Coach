from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import os
import json
import uuid
import random
from datetime import datetime
from werkzeug.utils import secure_filename

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ[key.strip()] = val.strip()

from groq_service import GroqService
from email_service import send_reset_code
from cv_analyzer import CVAnalyzer
from body_language import BodyLanguageAnalyzer
from database import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    email_exists, update_password, update_user_profile, update_profile_picture,
    save_reset_code, get_reset_entry, save_reset_token, get_email_by_token,
    delete_reset_code, save_interview, get_interview, reset_password_direct,
    get_user_interviews, get_user_stats, save_cv_upload, get_user_cvs,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ai-interview-secret-key-2024')
CORS(app)

UPLOAD_FOLDER = 'uploads'
PROFILE_PICS_FOLDER = 'uploads/profile_pics'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
ALLOWED_IMAGE_EXT  = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER']          = UPLOAD_FOLDER
app.config['PROFILE_PICS_FOLDER']    = PROFILE_PICS_FOLDER
app.config['MAX_CONTENT_LENGTH']     = 16 * 1024 * 1024

groq_service  = GroqService()
cv_analyzer   = CVAnalyzer(groq_service)
body_analyzer = BodyLanguageAnalyzer()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data     = request.get_json()
    name     = data.get('name', '').strip()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not all([name, email, password]):
        return jsonify({'error': 'All fields required'}), 400
    if email_exists(email):
        return jsonify({'error': 'Email already registered'}), 409

    user_id = create_user(name, email, password)
    session['user_id']    = user_id
    session['user_email'] = email
    session['user_name']  = name
    return jsonify({'success': True, 'name': name})

@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = get_user_by_email(email)
    if not user or user['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401

    session['user_id']    = user['id']
    session['user_email'] = email
    session['user_name']  = user['full_name']
    return jsonify({'success': True, 'name': user['full_name']})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()
    if not email_exists(email):
        return jsonify({'error': 'No account found with that email'}), 404
    code = str(random.randint(100000, 999999))
    save_reset_code(email, code)
    sent = send_reset_code(email, code)
    if not sent:
        return jsonify({'error': 'Failed to send email. Check MAIL_EMAIL and MAIL_PASSWORD in .env'}), 500
    return jsonify({'success': True})

@app.route('/api/verify-reset-code', methods=['POST'])
def verify_reset_code():
    data  = request.get_json()
    email = data.get('email', '').strip().lower()
    code  = data.get('code', '').strip()
    entry = get_reset_entry(email)
    if not entry or entry['code'] != code:
        return jsonify({'error': 'Invalid or expired code'}), 400
    token = str(uuid.uuid4())
    save_reset_token(email, token)
    return jsonify({'success': True, 'token': token})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    data         = request.get_json()
    token        = data.get('token', '')
    new_password = data.get('new_password', '')
    if not new_password or len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    email = get_email_by_token(token)
    if not email:
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    update_password(email, new_password)
    delete_reset_code(email)
    return jsonify({'success': True})

@app.route('/api/auth/status')
def auth_status():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'name': session.get('user_name')})
    return jsonify({'authenticated': False})


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/interview')
def interview():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('interview.html')

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('results.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('profile.html')


# ─── Profile API ──────────────────────────────────────────────────────────────

@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Don't expose the password hash
    user.pop('password', None)

    # Timestamps → strings
    for k in ('created_at', 'updated_at'):
        if user.get(k):
            user[k] = user[k].isoformat()

    stats      = get_user_stats(session['user_id'])
    interviews = get_user_interviews(session['user_id'])
    cvs        = get_user_cvs(session['user_id'])

    return jsonify({
        'user':       user,
        'stats':      stats,
        'interviews': interviews,
        'cvs':        cvs,
    })


@app.route('/api/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data      = request.get_json()
    full_name = data.get('full_name', '').strip()
    phone     = data.get('phone', '').strip()
    bio       = data.get('bio', '').strip()
    linkedin  = data.get('linkedin', '').strip()
    github    = data.get('github', '').strip()

    if not full_name:
        return jsonify({'error': 'Name is required'}), 400

    update_user_profile(session['user_id'], full_name, phone, bio, linkedin, github)

    # Keep session name in sync
    session['user_name'] = full_name
    return jsonify({'success': True, 'name': full_name})


@app.route('/api/profile/picture', methods=['POST'])
def upload_profile_picture():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if 'picture' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['picture']
    if file.filename == '' or not allowed_image(file.filename):
        return jsonify({'error': 'Invalid image file. Use PNG, JPG, JPEG, GIF, or WEBP'}), 400

    os.makedirs(app.config['PROFILE_PICS_FOLDER'], exist_ok=True)
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"avatar_{session['user_id']}.{ext}")
    filepath = os.path.join(app.config['PROFILE_PICS_FOLDER'], filename)
    file.save(filepath)

    update_profile_picture(session['user_id'], filename)
    return jsonify({'success': True, 'filename': filename, 'url': f'/uploads/profile_pics/{filename}'})


@app.route('/api/profile/send-change-code', methods=['POST'])
def send_change_code():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    email = session['user_email']
    code = str(random.randint(100000, 999999))
    save_reset_code(email, code)
    sent = send_reset_code(email, code)
    if not sent:
        return jsonify({'error': 'Failed to send email'}), 500
    return jsonify({'success': True})


@app.route('/api/profile/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data         = request.get_json()
    code         = data.get('code', '').strip()
    new_password = data.get('new_password', '')

    if not new_password or len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    email = session['user_email']
    entry = get_reset_entry(email)
    if not entry or entry['code'] != code:
        return jsonify({'error': 'Invalid or expired verification code'}), 400

    update_password(email, new_password)
    delete_reset_code(email)
    return jsonify({'success': True})


@app.route('/api/interviews/<interview_id>', methods=['GET'])
def get_interview_detail(interview_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = get_interview(interview_id)
    if not data:
        return jsonify({'error': 'Interview not found'}), 404
    # Security: only the owner can fetch it
    if data.get('user_id') != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
    if data.get('completed_at'):
        data['completed_at'] = data['completed_at'].isoformat() if hasattr(data['completed_at'], 'isoformat') else data['completed_at']
    return jsonify(data)


# ─── Static uploads (profile pics) ───────────────────────────────────────────

@app.route('/uploads/profile_pics/<filename>')
def serve_profile_pic(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['PROFILE_PICS_FOLDER'], filename)


# ─── CV Upload & Analysis ─────────────────────────────────────────────────────

@app.route('/api/upload-cv', methods=['POST'])
def upload_cv():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if 'cv' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file  = request.files['cv']
    field = request.form.get('field', 'Software Engineering')

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use PDF, DOC, DOCX, or TXT'}), 400

    filename = secure_filename(f"{session['user_id']}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    save_cv_upload(session['user_id'], filename, file.filename, field)

    cv_text  = cv_analyzer.extract_text(filepath)
    if not cv_text:
        return jsonify({'error': 'Could not extract text from CV'}), 400

    analysis = cv_analyzer.analyze(cv_text, field)

    session['cv_text']      = cv_text
    session['cv_analysis']  = analysis
    session['field']        = field
    session['interview_id'] = str(uuid.uuid4())
    session['cv_filename']  = filename   # store for later save

    return jsonify({
        'success':    True,
        'analysis':   analysis,
        'cv_preview': cv_text[:500] + '...' if len(cv_text) > 500 else cv_text
    })


# ─── Question Generation ──────────────────────────────────────────────────────

@app.route('/api/get-questions', methods=['GET'])
def get_questions():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'questions': session.get('questions', []), 'field': session.get('field', '')})

@app.route('/api/generate-questions', methods=['POST'])
def generate_questions():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    cv_analysis = session.get('cv_analysis', {})
    field       = session.get('field', 'Software Engineering')
    cv_text     = session.get('cv_text', '')

    questions = groq_service.generate_questions(cv_text, cv_analysis, field)
    session['questions']        = questions
    session['current_question'] = 0
    session['answers']          = []
    return jsonify({'questions': questions})


# ─── Answer Processing ────────────────────────────────────────────────────────

@app.route('/api/process-answer', methods=['POST'])
def process_answer():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data           = request.get_json()
    transcript     = data.get('transcript', '')
    question_index = data.get('question_index', 0)
    body_data      = data.get('body_data', {})

    questions = session.get('questions', [])
    if question_index >= len(questions):
        return jsonify({'error': 'Invalid question index'}), 400

    question        = questions[question_index]
    answer_analysis = groq_service.analyze_answer(
        question=question, answer=transcript,
        field=session.get('field', ''), cv_analysis=session.get('cv_analysis', {})
    )
    body_analysis = body_analyzer.analyze(body_data)

    answers = session.get('answers', [])
    answers.append({
        'question': question, 'transcript': transcript,
        'answer_analysis': answer_analysis, 'body_analysis': body_analysis,
        'timestamp': datetime.now().isoformat()
    })
    session['answers'] = answers

    return jsonify({'answer_analysis': answer_analysis, 'body_analysis': body_analysis})


# ─── Final Feedback & Courses ─────────────────────────────────────────────────

@app.route('/api/generate-feedback', methods=['POST'])
def generate_feedback():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    answers     = session.get('answers', [])
    cv_analysis = session.get('cv_analysis', {})
    field       = session.get('field', 'General')
    questions   = session.get('questions', [])

    if not answers and questions:
        answers = [{
            'question': q, 'transcript': '',
            'answer_analysis': {
                'score': 0, 'clarity': 0, 'relevance': 0, 'confidence': 0,
                'feedback': 'No answer was recorded for this question.',
                'missing_points': q.get('expected_keywords', []),
                'strengths': [], 'improvements': ['Please answer this question in your next attempt.']
            },
            'body_analysis': {}, 'timestamp': datetime.now().isoformat()
        } for q in questions]
        session['answers'] = answers

    feedback = groq_service.generate_final_feedback(answers, cv_analysis, field)
    courses  = groq_service.recommend_courses(feedback, field, cv_analysis)

    interview_id = session.get('interview_id', str(uuid.uuid4()))
    cv_filename  = session.get('cv_filename')

    result = {
        'interview_id': interview_id, 'field': field,
        'cv_analysis': cv_analysis, 'answers': answers,
        'feedback': feedback, 'courses': courses,
        'completed_at': datetime.now().isoformat()
    }

    # Save to MySQL — now also persists cv_filename
    save_interview(
        interview_id, session['user_id'], field,
        cv_analysis, answers, feedback, courses,
        cv_filename=cv_filename
    )

    session['results'] = result
    return jsonify(result)


@app.route('/api/get-results')
def get_results():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    results = session.get('results', {})
    if not results:
        interview_id = session.get('interview_id')
        if interview_id:
            results = get_interview(interview_id) or {}
    return jsonify(results)


@app.route('/api/analyze-frame', methods=['POST'])
def analyze_frame():
    data       = request.get_json()
    frame_data = data.get('frame_data', {})
    return jsonify(body_analyzer.analyze(frame_data))


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROFILE_PICS_FOLDER, exist_ok=True)
    init_db()
    app.run(debug=True, port=5000, use_reloader=True, reloader_type='stat')
