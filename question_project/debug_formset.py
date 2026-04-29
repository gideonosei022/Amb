from question_app.forms import QuestionFormSet
from question_app.models import User, Quiz

user = User.objects.filter(is_teacher=True).first()
if not user:
    raise SystemExit('No teacher user found')

quiz = Quiz.objects.filter(created_by=user).first()
if not quiz:
    raise SystemExit('No quiz found for teacher')

print('Using teacher:', user.username)
print('Using quiz:', quiz.title, quiz.id)

data = {
    'form-TOTAL_FORMS': '1',
    'form-INITIAL_FORMS': '0',
    'form-MIN_NUM_FORMS': '1',
    'form-MAX_NUM_FORMS': '1000',
    'form-0-quiz': str(quiz.id),
    'form-0-title': 'Test save',
    'form-0-question_text': 'Test question',
    'form-0-question_url': '',
    'form-0-question_type': 'theory',
    'form-0-option_a': '',
    'form-0-option_b': '',
    'form-0-option_c': '',
    'form-0-option_d': '',
    'form-0-correct_answer': 'Test answer',
    'form-0-marks': '5',
}

formset = QuestionFormSet(data, form_kwargs={'user': user})
print('valid:', formset.is_valid())
print('errors:', formset.errors)
print('non_form_errors:', formset.non_form_errors())

if formset.is_valid():
    for idx, form in enumerate(formset):
        print('form', idx, 'cleaned_data:', form.cleaned_data)
        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
            question = form.save()
            print('saved question id', question.id, 'title', question.title)
