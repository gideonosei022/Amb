#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'question_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
User = get_user_model()
from question_app.forms import QuestionForm
from question_app.models import Quiz

def test_question_form():
    # Create a test user
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user('testuser', 'test@example.com', 'password')

    # Create a test quiz
    try:
        quiz = Quiz.objects.get(title='Test Quiz')
    except Quiz.DoesNotExist:
        quiz = Quiz.objects.create(title='Test Quiz', created_by=user)

    # Create a request factory
    factory = RequestFactory()

    # Test MCQ form data
    mcq_data = {
        'quiz': quiz.id,
        'title': 'Test MCQ Question',
        'question_type': 'mcq',
        'marks': 5,
        'question_text': 'What is 2 + 2?',
        'option_a': '3',
        'option_b': '4',
        'option_c': '5',
        'option_d': '6',
        'correct_answer': 'B'
    }

    # Create request with user
    request = factory.post('/add_question/', mcq_data)
    request.user = user

    # Test the form
    form = QuestionForm(data=mcq_data, user=user)

    print("Form is valid:", form.is_valid())
    if not form.is_valid():
        print("Form errors:", form.errors)
        return False

    # Try to save
    try:
        question = form.save()
        print("Question saved successfully!")
        print("Question ID:", question.id)
        print("Question title:", question.title)
        print("Question type:", question.question_type)
        return True
    except Exception as e:
        print("Error saving question:", str(e))
        return False

if __name__ == '__main__':
    success = test_question_form()
    print("Test result:", "PASSED" if success else "FAILED")