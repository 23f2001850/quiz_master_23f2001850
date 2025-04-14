from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Subject, Chapter, Quiz, Question, Score
from forms import LoginForm, RegisterForm, SubjectForm, ChapterForm, QuizForm, QuestionForm
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz_master.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables and admin user
def create_tables():
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Check if admin exists, if not create one
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            admin = User(
                username='admin@quizmaster.com',
                full_name='Quiz Master Admin',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            qualification=form.qualification.data,
            dob=form.dob.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    subjects_count = Subject.query.count()
    chapters_count = Chapter.query.count()
    quizzes_count = Quiz.query.count()
    users_count = User.query.filter_by(is_admin=False).count()
    
    # Get quiz statistics by subject - Fixed query with explicit joins
    subject_quiz_stats = db.session.query(
        Subject.name, 
        db.func.count(Quiz.id)
    ).select_from(Subject).join(
        Chapter, Chapter.subject_id == Subject.id
    ).join(
        Quiz, Quiz.chapter_id == Chapter.id
    ).group_by(Subject.name).all()
    
    subject_names = [stat[0] for stat in subject_quiz_stats] if subject_quiz_stats else []
    quiz_counts = [stat[1] for stat in subject_quiz_stats] if subject_quiz_stats else []
    
    # Get user registration data by month - simplified approach
    from datetime import datetime, timedelta
    
    # Get the last 6 months
    today = datetime.today()
    months = []
    user_registrations = []
    
    # For demo purposes, generate some sample data
    # In a real app, you would query this from your database
    for i in range(5, -1, -1):
        month = today.replace(day=1) - timedelta(days=i*30)
        months.append(month.strftime('%B %Y'))
        
        # Just count all users for now (we'll improve this later)
        count = User.query.filter_by(is_admin=False).count()
        # Distribute users across months for demo purposes
        adjusted_count = max(0, count - i*2)  # More recent months have more users
        
        user_registrations.append(adjusted_count)
    
    return render_template('admin/dashboard.html', 
                          subjects_count=subjects_count,
                          chapters_count=chapters_count,
                          quizzes_count=quizzes_count,
                          users_count=users_count,
                          subject_names=subject_names,
                          quiz_counts=quiz_counts,
                          months=months,
                          user_registrations=user_registrations)

# Add this new route for admin users management
@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/users.html', users=users)

# Subject management
@app.route('/admin/subjects')
@login_required
def admin_subjects():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=subjects)

@app.route('/admin/subjects/add', methods=['GET', 'POST'])
@login_required
def add_subject():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully', 'success')
        return redirect(url_for('admin_subjects'))
    return render_template('admin/add_subject.html', form=form)

# Add these new routes for editing and deleting subjects
@app.route('/admin/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm(obj=subject)
    
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data
        db.session.commit()
        flash('Subject updated successfully', 'success')
        return redirect(url_for('admin_subjects'))
    
    return render_template('admin/edit_subject.html', form=form, subject=subject)

@app.route('/admin/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    subject = Subject.query.get_or_404(subject_id)
    force_delete = request.form.get('force_delete') == 'true'
    
    # Check if subject has chapters
    if subject.chapters and not force_delete:
        flash('Cannot delete subject with associated chapters. Use force delete to remove all related data.', 'warning')
        return redirect(url_for('admin_subjects'))
    
    if force_delete:
        # Delete all associated chapters, quizzes, questions, and scores
        for chapter in subject.chapters:
            for quiz in chapter.quizzes:
                # Delete all questions for this quiz
                Question.query.filter_by(quiz_id=quiz.id).delete()
                # Delete all scores for this quiz
                Score.query.filter_by(quiz_id=quiz.id).delete()
            # Delete all quizzes for this chapter
            Quiz.query.filter_by(chapter_id=chapter.id).delete()
        # Delete all chapters for this subject
        Chapter.query.filter_by(subject_id=subject.id).delete()
    
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully', 'success')
    return redirect(url_for('admin_subjects'))

# Chapter management
@app.route('/admin/chapters')
@login_required
def admin_chapters():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    chapters = Chapter.query.all()
    return render_template('admin/chapters.html', chapters=chapters)

@app.route('/admin/chapters/add', methods=['GET', 'POST'])
@login_required
def add_chapter():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    form = ChapterForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
    
    if form.validate_on_submit():
        chapter = Chapter(
            name=form.name.data,
            description=form.description.data,
            subject_id=form.subject_id.data
        )
        db.session.add(chapter)
        db.session.commit()
        flash('Chapter added successfully', 'success')
        return redirect(url_for('admin_chapters'))
    return render_template('admin/add_chapter.html', form=form)

# Add these new routes for editing and deleting chapters
@app.route('/admin/chapters/edit/<int:chapter_id>', methods=['GET', 'POST'])
@login_required
def edit_chapter(chapter_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    form = ChapterForm(obj=chapter)
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
    
    if form.validate_on_submit():
        chapter.name = form.name.data
        chapter.description = form.description.data
        chapter.subject_id = form.subject_id.data
        db.session.commit()
        flash('Chapter updated successfully', 'success')
        return redirect(url_for('admin_chapters'))
    
    # Set default value for subject_id dropdown
    if request.method == 'GET':
        form.subject_id.data = chapter.subject_id
    
    return render_template('admin/edit_chapter.html', form=form, chapter=chapter)

@app.route('/admin/chapters/delete/<int:chapter_id>', methods=['POST'])
@login_required
def delete_chapter(chapter_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    force_delete = request.form.get('force_delete') == 'true'
    
    # Check if chapter has quizzes
    if chapter.quizzes and not force_delete:
        flash('Cannot delete chapter with associated quizzes. Use force delete to remove all related data.', 'warning')
        return redirect(url_for('admin_chapters'))
    
    if force_delete:
        # Delete all associated quizzes, questions, and scores
        for quiz in chapter.quizzes:
            # Delete all questions for this quiz
            Question.query.filter_by(quiz_id=quiz.id).delete()
            # Delete all scores for this quiz
            Score.query.filter_by(quiz_id=quiz.id).delete()
        # Delete all quizzes for this chapter
        Quiz.query.filter_by(chapter_id=chapter.id).delete()
    
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter deleted successfully', 'success')
    return redirect(url_for('admin_chapters'))

# Quiz management
@app.route('/admin/quizzes')
@login_required
def admin_quizzes():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    quizzes = Quiz.query.all()
    return render_template('admin/quizzes.html', quizzes=quizzes)

@app.route('/admin/quizzes/add', methods=['GET', 'POST'])
@login_required
def add_quiz():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    form = QuizForm()
    form.chapter_id.choices = [(c.id, f"{c.subject.name} - {c.name}") for c in Chapter.query.all()]
    
    if form.validate_on_submit():
        quiz = Quiz(
            chapter_id=form.chapter_id.data,
            date_of_quiz=form.date_of_quiz.data,
            time_duration=form.time_duration.data,
            remarks=form.remarks.data
        )
        db.session.add(quiz)
        db.session.commit()
        flash('Quiz added successfully', 'success')
        return redirect(url_for('admin_quizzes'))
    return render_template('admin/add_quiz.html', form=form)

# Add these new routes for editing and deleting quizzes
@app.route('/admin/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def edit_quiz(quiz_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuizForm(obj=quiz)
    form.chapter_id.choices = [(c.id, f"{c.subject.name} - {c.name}") for c in Chapter.query.all()]
    
    if form.validate_on_submit():
        quiz.chapter_id = form.chapter_id.data
        quiz.date_of_quiz = form.date_of_quiz.data
        quiz.time_duration = form.time_duration.data
        quiz.remarks = form.remarks.data
        db.session.commit()
        flash('Quiz updated successfully', 'success')
        return redirect(url_for('admin_quizzes'))
    
    # Set default value for chapter_id dropdown
    if request.method == 'GET':
        form.chapter_id.data = quiz.chapter_id
    
    return render_template('admin/edit_quiz.html', form=form, quiz=quiz)

@app.route('/admin/quizzes/delete/<int:quiz_id>', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    force_delete = request.form.get('force_delete') == 'true'
    
    # Check if quiz has questions or scores
    if (quiz.questions or quiz.scores) and not force_delete:
        flash('Cannot delete quiz with associated questions or scores. Use force delete to remove all related data.', 'warning')
        return redirect(url_for('admin_quizzes'))
    
    if force_delete:
        # Delete all questions for this quiz
        Question.query.filter_by(quiz_id=quiz.id).delete()
        # Delete all scores for this quiz
        Score.query.filter_by(quiz_id=quiz.id).delete()
    
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz deleted successfully', 'success')
    return redirect(url_for('admin_quizzes'))

# Question management
@app.route('/admin/quizzes/<int:quiz_id>/questions')
@login_required
def quiz_questions(quiz_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    return render_template('admin/questions.html', quiz=quiz, questions=questions)

@app.route('/admin/quizzes/<int:quiz_id>/questions/add', methods=['GET', 'POST'])
@login_required
def add_question(quiz_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuestionForm()
    
    if form.validate_on_submit():
        question = Question(
            quiz_id=quiz_id,
            question_statement=form.question_statement.data,
            option1=form.option1.data,
            option2=form.option2.data,
            option3=form.option3.data,
            option4=form.option4.data,
            correct_option=form.correct_option.data
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully', 'success')
        return redirect(url_for('quiz_questions', quiz_id=quiz_id))
    return render_template('admin/add_question.html', form=form, quiz=quiz)

# Add these new routes for editing and deleting questions
@app.route('/admin/questions/edit/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    question = Question.query.get_or_404(question_id)
    form = QuestionForm(obj=question)
    
    if form.validate_on_submit():
        question.question_statement = form.question_statement.data
        question.option1 = form.option1.data
        question.option2 = form.option2.data
        question.option3 = form.option3.data
        question.option4 = form.option4.data
        question.correct_option = form.correct_option.data
        db.session.commit()
        flash('Question updated successfully', 'success')
        return redirect(url_for('quiz_questions', quiz_id=question.quiz_id))
    
    # Make sure the correct_option field is properly set
    if request.method == 'GET':
        form.correct_option.data = question.correct_option
    
    return render_template('admin/edit_question.html', form=form, question=question)

@app.route('/admin/questions/delete/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    question = Question.query.get_or_404(question_id)
    quiz_id = question.quiz_id
    
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully', 'success')
    return redirect(url_for('quiz_questions', quiz_id=quiz_id))

# User dashboard
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    subjects = Subject.query.all()
    recent_scores = Score.query.filter_by(user_id=current_user.id).order_by(Score.timestamp.desc()).limit(5).all()
    
    # Calculate performance data for chart
    total_questions = 0
    total_correct = 0
    
    all_scores = Score.query.filter_by(user_id=current_user.id).all()
    for score in all_scores:
        total_questions += score.total_questions
        total_correct += score.total_scored
    
    # Default values if no quizzes taken
    correct_percentage = 0
    incorrect_percentage = 0
    
    if total_questions > 0:
        correct_percentage = (total_correct / total_questions) * 100
        incorrect_percentage = 100 - correct_percentage
    
    return render_template('user/dashboard.html', 
                          subjects=subjects,
                          recent_scores=recent_scores,
                          correct_percentage=correct_percentage,
                          incorrect_percentage=incorrect_percentage,
                          has_taken_quiz=(total_questions > 0))

@app.route('/user/subjects/<int:subject_id>/chapters')
@login_required
def user_chapters(subject_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    
    return render_template('user/chapters.html', subject=subject, chapters=chapters)

@app.route('/user/chapters/<int:chapter_id>/quizzes')
@login_required
def user_quizzes(chapter_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    chapter = Chapter.query.get_or_404(chapter_id)
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).all()
    
    return render_template('user/quizzes.html', chapter=chapter, quizzes=quizzes)

@app.route('/user/quizzes/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    if request.method == 'POST':
        score = 0
        for question in questions:
            selected_option = request.form.get(f'question_{question.id}')
            if selected_option and int(selected_option) == question.correct_option:
                score += 1
        
        # Save the score
        quiz_score = Score(
            quiz_id=quiz_id,
            user_id=current_user.id,
            total_scored=score,
            total_questions=len(questions)
        )
        db.session.add(quiz_score)
        db.session.commit()
        
        flash(f'Quiz completed! Your score: {score}/{len(questions)}', 'success')
        return redirect(url_for('quiz_result', score_id=quiz_score.id))
    
    return render_template('user/take_quiz.html', quiz=quiz, questions=questions)

@app.route('/user/scores/<int:score_id>')
@login_required
def quiz_result(score_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    score = Score.query.get_or_404(score_id)
    if score.user_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    
    return render_template('user/quiz_result.html', score=score)

@app.route('/user/history')
@login_required
def quiz_history():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    scores = Score.query.filter_by(user_id=current_user.id).order_by(Score.timestamp.desc()).all()
    
    # Calculate data for subject performance chart
    subject_data = {}
    for score in scores:
        subject_name = score.quiz.chapter.subject.name
        percentage = (score.total_scored / score.total_questions) * 100
        
        if subject_name in subject_data:
            subject_data[subject_name].append(percentage)
        else:
            subject_data[subject_name] = [percentage]
    
    subject_names = list(subject_data.keys())
    subject_scores = [sum(scores)/len(scores) for scores in subject_data.values()]
    
    # Calculate data for progress over time chart
    time_labels = []
    progress_scores = []
    
    if scores:
        # Group scores by month
        scores_by_month = {}
        for score in scores:
            month_key = score.timestamp.strftime('%b %Y')
            if month_key in scores_by_month:
                scores_by_month[month_key].append((score.total_scored / score.total_questions) * 100)
            else:
                scores_by_month[month_key] = [(score.total_scored / score.total_questions) * 100]
        
        # Sort months chronologically
        from datetime import datetime
        sorted_months = sorted(scores_by_month.keys(), 
                              key=lambda x: datetime.strptime(x, '%b %Y'))
        
        time_labels = sorted_months
        progress_scores = [sum(scores_by_month[month])/len(scores_by_month[month]) 
                          for month in sorted_months]
    
    return render_template('user/quiz_history.html', 
                          scores=scores,
                          subject_names=subject_names,
                          subject_scores=subject_scores,
                          time_labels=time_labels,
                          progress_scores=progress_scores)

# API endpoints
@app.route('/api/subjects', methods=['GET'])
def api_subjects():
    subjects = Subject.query.all()
    return jsonify([{
        'id': subject.id,
        'name': subject.name,
        'description': subject.description
    } for subject in subjects])

@app.route('/api/subjects/<int:subject_id>/chapters', methods=['GET'])
def api_chapters(subject_id):
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    return jsonify([{
        'id': chapter.id,
        'name': chapter.name,
        'description': chapter.description
    } for chapter in chapters])

@app.route('/api/chapters/<int:chapter_id>/quizzes', methods=['GET'])
def api_quizzes(chapter_id):
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).all()
    return jsonify([{
        'id': quiz.id,
        'date_of_quiz': quiz.date_of_quiz.strftime('%Y-%m-%d'),
        'time_duration': quiz.time_duration,
        'remarks': quiz.remarks
    } for quiz in quizzes])

if __name__ == '__main__':
    create_tables()  # Call the function to create tables before running the app
    app.run(debug=True)