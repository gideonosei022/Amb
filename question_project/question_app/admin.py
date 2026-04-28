from django.contrib import admin
from .models import User, Quiz, Question, Submission, Answer, Result

# Register your models here.
admin.site.register(User)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Submission)
admin.site.register(Answer)
admin.site.register(Result)
