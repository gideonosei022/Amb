from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from .models import Quiz, Question, Submission, Answer, Result
from .forms import QuizForm, QuestionForm, UserRegistrationForm

# Create your views here.
def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('quiz_list')


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # 🔒 force student role
            user.is_teacher = False
            user.is_staff = False
            user.is_superuser = False

            user.save()  # ❌ NO set_password needed

            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def create_quiz(request):
    if not request.user.is_teacher:
        return HttpResponse("Unauthorized", status=403)

    if request.method == "POST":
        form = QuizForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('quiz_list')
    else:
        form = QuizForm(user=request.user)

    return render(request, 'create_quiz.html', {'form': form})

@login_required
def upload_question(request):
    if request.method == "POST":
        form = QuestionForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('success')

    else:
        form = QuestionForm()

    return render(request, 'upload.html', {'form': form})

@login_required
def quiz_list(request):
    quizzes = Quiz.objects.all()
    return render(request, 'quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not request.user.is_teacher or quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    questions = quiz.questions.all()

    return render(request, 'quiz_detail.html', {
        'quiz': quiz,
        'questions': questions
    })

@login_required
def add_question(request):
    if not request.user.is_teacher:
        return HttpResponse("Unauthorized", status=403)

    if request.method == "POST":
        form = QuestionForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('quiz_list')
    else:
        form = QuestionForm(user=request.user)

    return render(request, 'add_question.html', {'form': form})

@login_required
def take_quiz(request, quiz_id):
    if request.user.is_teacher:
        return HttpResponse("Only students can take quizzes", status=403)

    quiz = get_object_or_404(Quiz, id=quiz_id)

    if Submission.objects.filter(student=request.user, quiz=quiz).exists():
        return HttpResponse("You have already taken this quiz.")

    questions = quiz.questions.all()

    if request.method == "POST":
        submission = Submission.objects.create(
            student=request.user,
            quiz=quiz
        )

        total = 0
        score = 0

        for q in questions:
            answer = request.POST.get(str(q.id)) or ""

            Answer.objects.create(
                submission=submission,
                question=q,
                selected_answer=answer
            )

            total += q.marks

            if q.question_type == 'mcq':
                if answer.strip().lower() == (q.correct_answer or "").strip().lower():
                    score += q.marks
            # Note: Theory questions are not auto-graded and receive 0 marks

        percentage = (score / total) * 100 if total > 0 else 0

        Result.objects.create(
            submission=submission,
            score=score,
            total_marks=total,
            percentage=percentage
        )

        return redirect('result', submission_id=submission.id)

    return render(request, 'take_quiz.html', {
        'quiz': quiz,
        'questions': questions
    })


@login_required
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not request.user.is_teacher or quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    if request.method == "POST":
        quiz.delete()
        return redirect('quiz_list')

    return render(request, 'confirm_delete.html', {
        'object': quiz,
        'object_type': 'Quiz'
    })


@login_required
def result_view(request, submission_id):
    result = get_object_or_404(Result, submission_id=submission_id)
    submission = result.submission

    if submission.student != request.user:
        return HttpResponse("Unauthorized", status=403)

    answers = submission.answers.select_related('question')

    return render(request, 'result.html', {
        'result': result,
        'submission': submission,
        'answers': answers
    })