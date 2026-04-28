from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),

    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quiz/create/', views.create_quiz, name='create_quiz'),
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),

    path('question/add/', views.add_question, name='add_question'),

    path('quiz/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),

    # ✅ THIS MUST MATCH YOUR VIEW NAME
    path('quiz/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),

    path('result/<int:submission_id>/', views.result_view, name='result'),
]


