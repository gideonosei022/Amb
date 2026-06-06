from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from .models import Quiz, Question, Submission, Answer, Result
from .forms import QuizForm, QuestionForm, QuestionFormSet, PreviewQuestionFormSet, UserRegistrationForm

import requests
from bs4 import BeautifulSoup
import re


def _clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def _fetch_text_from_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Handle public Google Docs URLs by using the export endpoint.
    google_docs_match = re.search(r'https?://docs\.google\.com/document/d/([^/]+)/', url)
    if google_docs_match:
        doc_id = google_docs_match.group(1)
        export_url = f'https://docs.google.com/document/d/{doc_id}/export?format=txt'
        response = requests.get(export_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        # If export endpoint fails, fall back to HTML fetch.

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    content_type = response.headers.get('content-type', '').lower()
    if 'text/html' not in content_type:
        return ''

    soup = BeautifulSoup(response.content, 'lxml')
    for script in soup(['script', 'style']):
        script.decompose()

    content_selectors = [
        'main',
        '[class*="content"]',
        '[class*="post"]',
        '[class*="article"]',
        '[class*="entry"]',
        'article',
        '.post-content',
        '.entry-content',
        '.content',
        'body'
    ]

    text_content = ''
    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            text_content = elements[0].get_text(separator='\n', strip=True)
            if len(text_content) > 100:
                break

    if not text_content and soup.body:
        text_content = soup.body.get_text(separator='\n', strip=True)

    return text_content


def _find_question_blocks(text):
    if not text:
        return []

    cleaned = _clean_text(text)

    numbered_blocks = re.findall(
        r'(?:(?:Question|Q)\s*\d+[:\)\.\-]?\s*.*?)(?=(?:Question|Q)\s*\d+[:\)\.\-]?\s*|\d+[\.\)]\s*|$)',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    numbered_blocks = [block.strip() for block in numbered_blocks if len(_clean_text(block)) > 40]
    if numbered_blocks:
        return numbered_blocks

    bullet_blocks = re.findall(
        r'(?m)^((?:\d+)[\.\)]\s*.*?)(?=^\d+[\.\)]\s*|\Z)',
        text,
        flags=re.DOTALL
    )
    bullet_blocks = [block.strip() for block in bullet_blocks if len(_clean_text(block)) > 40]
    if bullet_blocks:
        return bullet_blocks

    top_level_numbered = re.findall(r'(?m)^\s*\d+[\.\)]\s*', text)
    top_level_question_label = re.findall(r'(?im)^\s*(?:Question|Q)\s*\d+[:\)\.\-]?\s*', text)
    subquestion_marker = re.search(r'(?m)^\s*[a-eA-E][\.\)]\s*', text)
    if subquestion_marker and (len(top_level_numbered) == 1 or len(top_level_question_label) == 1):
        return [text.strip()]

    question_sentences = re.findall(r'[^.?!\n]*\?[^.?!\n]*', cleaned)
    question_sentences = [_clean_text(sentence) for sentence in question_sentences if len(_clean_text(sentence)) > 40]
    if len(question_sentences) > 1:
        return question_sentences
    if len(question_sentences) == 1:
        return question_sentences

    paragraphs = [p.strip() for p in re.split(r'\n{2,}|\r\n{2,}', text) if len(p.strip()) > 40]
    paragraphs = [_clean_text(p) for p in paragraphs]
    if len(paragraphs) > 1:
        return paragraphs

    return [cleaned] if cleaned else []


def _parse_mcq_from_text(text):
    parsed = {
        'text': _clean_text(text),
        'is_mcq': False,
        'option_a': None,
        'option_b': None,
        'option_c': None,
        'option_d': None,
        'option_e': None,
        'correct_answer': ''
    }

    if not text:
        return parsed

    normalized = re.sub(r'\r\n?', '\n', text)

    def parse_inline_options(source):
        marker_pattern = re.compile(r'(?i)\b([A-E])([\.|\)])\s*')
        matches = list(marker_pattern.finditer(source))
        if len(matches) < 4:
            return None

        letters = [m.group(1).upper() for m in matches]
        if letters[0] != 'A' or letters[1] != 'B' or letters[2] != 'C' or letters[3] != 'D':
            return None
        if len(letters) == 5 and letters[4] != 'E':
            return None
        if len(letters) not in (4, 5):
            return None

        options = {}
        for idx, match in enumerate(matches):
            letter = match.group(1).upper()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
            options[letter] = source[start:end].strip()

        stem = source[:matches[0].start()].strip()
        if not stem:
            return None

        if any(not options.get(letter) for letter in ['A', 'B', 'C', 'D']):
            return None
        return {'stem': stem, 'options': options}

    inline_match = parse_inline_options(normalized)
    if inline_match:
        parsed['is_mcq'] = True
        parsed['text'] = _clean_text(inline_match['stem'])
        parsed['option_a'] = _clean_text(inline_match['options'].get('A'))
        parsed['option_b'] = _clean_text(inline_match['options'].get('B'))
        parsed['option_c'] = _clean_text(inline_match['options'].get('C'))
        parsed['option_d'] = _clean_text(inline_match['options'].get('D'))
        parsed['option_e'] = _clean_text(inline_match['options'].get('E')) if inline_match['options'].get('E') else None

        answer_match = re.search(r'(?i)(?:Answer|Correct Answer|Correct)\s*[:\-]?\s*([A-E])', normalized)
        if answer_match:
            letter = answer_match.group(1).upper()
            parsed['correct_answer'] = {
                'A': parsed['option_a'],
                'B': parsed['option_b'],
                'C': parsed['option_c'],
                'D': parsed['option_d'],
                'E': parsed['option_e']
            }.get(letter, '')
        return parsed

    five_option_pattern = (
        r'(?si)(?P<stem>.*?)(?:\n|^)\s*A[\.\)\:]\s*(?P<option_a>.*?)(?=\n\s*B[\.\)\:]\s*)'
        r'\n\s*B[\.\)\:]\s*(?P<option_b>.*?)(?=\n\s*C[\.\)\:]\s*)'
        r'\n\s*C[\.\)\:]\s*(?P<option_c>.*?)(?=\n\s*D[\.\)\:]\s*)'
        r'\n\s*D[\.\)\:]\s*(?P<option_d>.*?)(?=\n\s*E[\.\)\:]\s*)'
        r'\n\s*E[\.\)\:]\s*(?P<option_e>.*?)(?=\n\s*(?:Answer|Correct Answer|Correct)[\:\-]?\s*|$)'
    )

    four_option_pattern = (
        r'(?si)(?P<stem>.*?)(?:\n|^)\s*A[\.\)\:]\s*(?P<option_a>.*?)(?=\n\s*B[\.\)\:]\s*)'
        r'\n\s*B[\.\)\:]\s*(?P<option_b>.*?)(?=\n\s*C[\.\)\:]\s*)'
        r'\n\s*C[\.\)\:]\s*(?P<option_c>.*?)(?=\n\s*D[\.\)\:]\s*)'
        r'\n\s*D[\.\)\:]\s*(?P<option_d>.*?)(?=\n\s*(?:Answer|Correct Answer|Correct)[\:\-]?\s*|$)'
    )

    mcq_match = re.search(five_option_pattern, normalized) or re.search(four_option_pattern, normalized)

    if mcq_match:
        parsed['is_mcq'] = True
        parsed['text'] = _clean_text(mcq_match.group('stem'))
        parsed['option_a'] = _clean_text(mcq_match.group('option_a'))
        parsed['option_b'] = _clean_text(mcq_match.group('option_b'))
        parsed['option_c'] = _clean_text(mcq_match.group('option_c'))
        parsed['option_d'] = _clean_text(mcq_match.group('option_d'))
        parsed['option_e'] = _clean_text(mcq_match.group('option_e')) if mcq_match.groupdict().get('option_e') else None

        answer_match = re.search(r'(?i)(?:Answer|Correct Answer|Correct)\s*[:\-]?\s*([A-E])', normalized)
        if answer_match:
            letter = answer_match.group(1).upper()
            parsed['correct_answer'] = {
                'A': parsed['option_a'],
                'B': parsed['option_b'],
                'C': parsed['option_c'],
                'D': parsed['option_d'],
                'E': parsed['option_e']
            }.get(letter, '')

    return parsed


def _parse_theory_subquestions(text):
    normalized = re.sub(r'\r\n?', '\n', text).strip()
    parsed = {
        'text': normalized,
        'subquestion_labels': []
    }

    if not normalized:
        return parsed

    pattern = re.compile(r'(?m)^\s*([a-eA-E])[\.\)]\s*')
    matches = list(pattern.finditer(normalized))
    if not matches:
        return parsed

    labels = []
    for match in matches:
        label = match.group(1).lower()
        if label not in labels:
            labels.append(label)

    parsed['subquestion_labels'] = labels
    return parsed


def extract_questions_from_url(url):
    try:
        text_content = _fetch_text_from_url(url)
        if not text_content:
            return []

        questions = _find_question_blocks(text_content)
        return questions[:20]
    except Exception:
        return []


def extract_question_from_url(url):
    questions = extract_questions_from_url(url)
    return questions[0] if questions else f"Unable to extract question text from the URL."


def _hide_preview_fields(formset):
    hidden_fields = [
        'question_url',
        'title',
        'section'
    ]
    for form in formset:
        for field_name in hidden_fields:
            if field_name in form.fields:
                form.fields[field_name].widget = forms.HiddenInput()

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
    return redirect('home')

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
def upload_question(request, quiz_id=None, section=None):
    if not request.user.is_teacher:
        return HttpResponse("Unauthorized", status=403)

    initial = {}
    if quiz_id is not None:
        initial['quiz'] = quiz_id
    if section in ['A', 'B']:
        initial['section'] = section

    preview = False
    form = None
    formset = None
    question_url = None

    if request.method == "POST":
        if request.POST.get('form-TOTAL_FORMS'):
            formset = PreviewQuestionFormSet(request.POST, form_kwargs={'user': request.user})
            preview = True
            if formset.is_valid():
                saved_questions = []
                redirect_quiz_id = None
                for form_item in formset:
                    if not form_item.cleaned_data:
                        continue
                    if not form_item.cleaned_data.get('DELETE', False):
                        saved_questions.append(form_item.save())
                    elif redirect_quiz_id is None:
                        quiz = form_item.cleaned_data.get('quiz')
                        if quiz:
                            redirect_quiz_id = quiz.id

                if saved_questions:
                    redirect_quiz_id = saved_questions[0].quiz.id

                if redirect_quiz_id:
                    return redirect('quiz_detail', quiz_id=redirect_quiz_id)
                return redirect('quiz_list')
        else:
            post_data = request.POST.copy()

            section = section or post_data.get('section', 'A')
            post_data['question_type'] = 'mcq' if section == 'A' else 'theory'
            if 'correct_answer' not in post_data:
                post_data['correct_answer'] = 'To be evaluated manually'
            if 'marks' not in post_data:
                post_data['marks'] = '1'

            # Keep the selected quiz and section for preview rows
            if post_data.get('quiz'):
                initial['quiz'] = post_data.get('quiz')
            initial['section'] = section

            question_url = post_data.get('question_url', '').strip()
            if question_url:
                extracted_questions = extract_questions_from_url(question_url)
                # For Section B (theory) prefer merging subquestion-only blocks
                # into the preceding numbered question so that 1. + a. b. c. stay together
                if section == 'B' and len(extracted_questions) > 1:
                    merged = []
                    subq_re = re.compile(r'(?m)^\s*[a-eA-E][\.\)]\s*')
                    for block in extracted_questions:
                        if subq_re.match(block):
                            if merged:
                                # append subquestion block to previous block preserving newline
                                merged[-1] = merged[-1].rstrip() + '\n' + block.lstrip()
                            else:
                                # no previous block; start new
                                merged.append(block)
                        else:
                            merged.append(block)
                    extracted_questions = merged
                if len(extracted_questions) > 1:
                    initial_questions = []
                    parsed_items = []
                    for question_text in extracted_questions:
                        if section == 'A':
                            parsed = _parse_mcq_from_text(question_text)
                        else:
                            parsed = _parse_theory_subquestions(question_text)

                        item = initial.copy()
                        item.update({
                            'question_url': question_url,
                            'question_text': parsed.get('text', ''),
                            'section': section,
                            'question_type': 'mcq' if section == 'A' else 'theory',
                            'correct_answer': parsed.get('correct_answer', '') or 'To be evaluated manually',
                            'marks': 1,
                            'option_a': parsed.get('option_a', '') if section == 'A' else '',
                            'option_b': parsed.get('option_b', '') if section == 'A' else '',
                            'option_c': parsed.get('option_c', '') if section == 'A' else '',
                            'option_d': parsed.get('option_d', '') if section == 'A' else '',
                            'option_e': parsed.get('option_e', '') if section == 'A' else ''
                        })
                        initial_questions.append(item)
                        parsed_items.append(parsed)

                    formset = PreviewQuestionFormSet(form_kwargs={'user': request.user}, initial=initial_questions)
                    _hide_preview_fields(formset)
                    for form_item, parsed in zip(formset, parsed_items):
                        if 'question_text' in form_item.fields:
                            form_item.fields['question_text'].widget.attrs['readonly'] = True
                        if section == 'B':
                            form_item.subanswer_fields = [
                                (label, form_item[f'sub_answer_{label}'])
                                for label in parsed.get('subquestion_labels', [])
                                if f'sub_answer_{label}' in form_item.fields
                            ]
                    preview = True
                    return render(request, 'upload_question.html', {
                        'formset': formset,
                        'preview': preview,
                        'question_url': question_url,
                        'section': section
                    })
                elif len(extracted_questions) == 1:
                    if section == 'A':
                        parsed = _parse_mcq_from_text(extracted_questions[0])
                    else:
                        parsed = _parse_theory_subquestions(extracted_questions[0])

                    if not post_data.get('question_text', '').strip():
                        post_data['question_text'] = parsed.get('text', '')
                    post_data['question_type'] = 'mcq' if section == 'A' else 'theory'
                    post_data['section'] = section
                    post_data['correct_answer'] = parsed.get('correct_answer', '') or 'To be evaluated manually'
                    post_data['marks'] = '1'
                    if section == 'A':
                        post_data['option_a'] = parsed.get('option_a', '') or ''
                        post_data['option_b'] = parsed.get('option_b', '') or ''
                        post_data['option_c'] = parsed.get('option_c', '') or ''
                        post_data['option_d'] = parsed.get('option_d', '') or ''
                        post_data['option_e'] = parsed.get('option_e', '') or ''
                    else:
                        post_data['option_a'] = ''
                        post_data['option_b'] = ''
                        post_data['option_c'] = ''
                        post_data['option_d'] = ''
                        post_data['option_e'] = ''

                        formset = PreviewQuestionFormSet(form_kwargs={'user': request.user}, initial=[{
                            **initial,
                            'question_url': question_url,
                            'question_text': parsed.get('text', ''),
                            'section': section,
                            'question_type': 'theory',
                            'correct_answer': 'To be evaluated manually',
                            'marks': 1,
                        }])
                        _hide_preview_fields(formset)
                        form_item = formset.forms[0]
                        if 'question_text' in form_item.fields:
                            form_item.fields['question_text'].widget.attrs['readonly'] = True
                        form_item.subanswer_fields = [
                            (label, form_item[f'sub_answer_{label}'])
                            for label in parsed.get('subquestion_labels', [])
                            if f'sub_answer_{label}' in form_item.fields
                        ]
                        preview = True
                        return render(request, 'upload_question.html', {
                            'formset': formset,
                            'preview': preview,
                            'question_url': question_url,
                            'section': section
                        })

            form = QuestionForm(post_data, user=request.user)
            if form.is_valid():
                form.save()
                return redirect('quiz_detail', quiz_id=form.cleaned_data['quiz'].id)
    else:
        form = QuestionForm(user=request.user, initial=initial)

    context = {
        'form': form,
        'formset': formset,
        'preview': preview,
        'question_url': question_url,
        'section': section
    }
    return render(request, 'upload_question.html', context)

@login_required
def quiz_list(request):
    quizzes = Quiz.objects.all()
    return render(request, 'quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not request.user.is_teacher or quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    section_a_questions = quiz.questions.filter(section='A').order_by('question_number')
    section_b_questions = quiz.questions.filter(section='B').order_by('question_number')

    return render(request, 'quiz_detail.html', {
        'quiz': quiz,
        'section_a_questions': section_a_questions,
        'section_b_questions': section_b_questions,
    })

@login_required
def quiz_section_detail(request, quiz_id, section):
    if not request.user.is_teacher:
        return HttpResponse("Unauthorized", status=403)

    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    if section not in ['A', 'B']:
        return HttpResponse("Invalid section", status=400)

    questions = quiz.questions.filter(section=section).order_by('question_number')
    section_label = 'Section A' if section == 'A' else 'Section B'

    return render(request, 'quiz_section_detail.html', {
        'quiz': quiz,
        'questions': questions,
        'section': section,
        'section_label': section_label,
    })

@login_required
def add_question(request, quiz_id=None, section=None):
    if not request.user.is_teacher:
        return HttpResponse("Unauthorized", status=403)

    initial = {}
    if quiz_id is not None:
        initial['quiz'] = quiz_id

    if section in ['A', 'B']:
        initial['section'] = section
        initial['question_type'] = 'mcq' if section == 'A' else 'theory'

    if request.method == "POST":
        formset = QuestionFormSet(request.POST, form_kwargs={'user': request.user})
        if formset.is_valid():
            saved_questions = []
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    question = form.save()
                    saved_questions.append(question)

            if saved_questions:
                return redirect('quiz_detail', quiz_id=saved_questions[0].quiz.id)
    else:
        initial_data = [initial] if initial else [{}]
        formset = QuestionFormSet(form_kwargs={'user': request.user}, initial=initial_data)

    return render(request, 'add_question.html', {
        'formset': formset,
        'section': section,
    })

@login_required
def take_quiz(request, quiz_id):
    if request.user.is_teacher:
        return HttpResponse("Only students can take quizzes", status=403)

    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Removed check for existing submission to allow unlimited attempts

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
def edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)

    if not request.user.is_teacher or question.quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('quiz_detail', quiz_id=question.quiz.id)
    else:
        form = QuestionForm(instance=question, user=request.user)

    return render(request, 'edit_question.html', {'form': form, 'question': question})


@login_required
def delete_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)

    if not request.user.is_teacher or question.quiz.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    if request.method == "POST":
        quiz_id = question.quiz.id
        question.delete()
        return redirect('quiz_detail', quiz_id=quiz_id)

    return render(request, 'confirm_delete.html', {
        'object': question,
        'object_type': 'Question'
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