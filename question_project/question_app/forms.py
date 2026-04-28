from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Quiz, Question, Submission, User


# 🧑‍🎓 USER REGISTRATION (ALWAYS STUDENT)
class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'contact_number',
            'password1',
            'password2'
        ]

    def save(self, commit=True):
        user = super().save(commit=False)

        user.is_teacher = False
        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()
        return user


# 📝 QUIZ FORM (TEACHERS ONLY)
class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'source_file_url']  # ❌ removed "section"

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if not self.user or not self.user.is_teacher:
            raise forms.ValidationError("Only teachers can create quizzes.")

        return cleaned_data

    def save(self, commit=True):
        quiz = super().save(commit=False)

        # 🔥 FIX: assign creator from form user
        if self.user:
            quiz.created_by = self.user

        if commit:
            quiz.save()
        return quiz

# ❓ QUESTION FORM (TEACHERS ONLY)



class QuestionForm(forms.ModelForm):
    correct_answer = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Enter correct answer'
        }),
        required=True
    )

    class Meta:
        model = Question
        fields = [
            'quiz',
            'question_text',     # direct typed question
            'question_url',      # pasted question link
            'question_type',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer',
            'marks'
        ]

        widgets = {
            'question_text': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Type question here'
            }),

            'question_url': forms.URLInput(attrs={
                'placeholder': 'Paste URL containing question'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # MCQ options optional by default
        for field in ['option_a', 'option_b', 'option_c', 'option_d']:
            self.fields[field].required = False

        # quiz filtering by teacher
        if self.user:
            if self.user.is_superuser:
                self.fields['quiz'].queryset = Quiz.objects.all()

            elif self.user.is_teacher:
                self.fields['quiz'].queryset = Quiz.objects.filter(
                    created_by=self.user
                )

            else:
                self.fields['quiz'].queryset = Quiz.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        if not self.user or not self.user.is_teacher:
            raise forms.ValidationError(
                "Only teachers can add questions."
            )

        quiz = cleaned_data.get('quiz')

        if quiz and quiz.created_by != self.user:
            raise forms.ValidationError(
                "You can only add questions to your own quizzes."
            )

        question_text = cleaned_data.get('question_text')
        question_url = cleaned_data.get('question_url')

        # Must have either text or URL
        if not question_text and not question_url:
            raise forms.ValidationError(
                "Enter question text or paste question URL."
            )

        q_type = cleaned_data.get('question_type')

        # MCQ validation
        if q_type == 'mcq':
            missing = [
                f for f in [
                    'option_a',
                    'option_b',
                    'option_c',
                    'option_d'
                ]
                if not cleaned_data.get(f)
            ]

            if missing:
                raise forms.ValidationError(
                    "All options (A, B, C, D) are required for MCQ."
                )

        # Theory question
        elif q_type == 'theory':
            cleaned_data['option_a'] = None
            cleaned_data['option_b'] = None
            cleaned_data['option_c'] = None
            cleaned_data['option_d'] = None

        return cleaned_data
    

# 📤 SUBMISSION FORM (STUDENTS ONLY)
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = []

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.quiz = kwargs.pop('quiz', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if not self.user or self.user.is_teacher:
            raise forms.ValidationError("Only students can submit quizzes.")

        return cleaned_data

    def save(self, commit=True):
        submission = super().save(commit=False)

        # 🔥 REQUIRED MODEL FIELDS
        submission.student = self.user
        submission.quiz = self.quiz

        if commit:
            submission.save()

        return submission