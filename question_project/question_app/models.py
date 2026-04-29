from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


class User(AbstractUser):
    is_teacher = models.BooleanField(default=False)  # 👈 only admin changes this
    contact_number = models.CharField(max_length=15, blank=True, null=True)

    def is_student(self):
        return not self.is_teacher

    def __str__(self):
        role = "Teacher" if self.is_teacher else "Student"
        return f"{self.username} ({role})"
    
class Quiz(models.Model):
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    source_file_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Validation moved to QuizForm.clean() to avoid issues during form validation
        # when created_by is not yet set
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    
# ❓ QUESTION


class Question(models.Model):
    QUESTION_TYPES = (
        ('mcq', 'Multiple Choice'),
        ('theory', 'Theory'),
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )

    # Question title/label
    title = models.CharField(max_length=255, blank=True, null=True)

    # Teacher can type question directly
    question_text = models.TextField(blank=True, null=True)

    # Teacher can paste URL containing question
    question_url = models.URLField(blank=True, null=True)

    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPES
    )

    # MCQ options
    option_a = models.CharField(max_length=255, blank=True, null=True)
    option_b = models.CharField(max_length=255, blank=True, null=True)
    option_c = models.CharField(max_length=255, blank=True, null=True)
    option_d = models.CharField(max_length=255, blank=True, null=True)

    correct_answer = models.TextField()
    marks = models.IntegerField(default=1)

    def clean(self):
        # Validation moved to QuestionForm.clean() to avoid issues during form validation
        # when related fields might not be set yet

        # Must have either text OR URL
        if not self.question_text and not self.question_url:
            raise ValidationError(
                "Provide question text or question URL."
            )

        # Validate URL if entered
        if self.question_url:
            validator = URLValidator()
            validator(self.question_url)

        # MCQ rules
        if self.question_type == 'mcq':
            if not all([
                self.option_a,
                self.option_b,
                self.option_c,
                self.option_d
            ]):
                raise ValidationError(
                    "All MCQ options are required."
                )

        # Theory rules
        elif self.question_type == 'theory':
            self.option_a = None
            self.option_b = None
            self.option_c = None
            self.option_d = None

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.question_text:
            return self.question_text[:50]
        return f"Question Link: {self.question_url}"

    
class Submission(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)

    submitted_at = models.DateTimeField(auto_now_add=True)

    # Removed unique_together to allow multiple submissions per student per quiz

    def clean(self):
        # Validation moved to SubmissionForm.clean() to avoid issues during form validation
        # when related fields might not be set yet
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
class Answer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    selected_answer = models.TextField()  # 🔥 changed to TextField

    def __str__(self):
        return f"{self.question} - {self.selected_answer[:30]}"


class Result(models.Model):
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE)

    score = models.IntegerField()
    total_marks = models.IntegerField()
    percentage = models.FloatField()

    graded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.submission.student} - {self.score}/{self.total_marks}"
        
