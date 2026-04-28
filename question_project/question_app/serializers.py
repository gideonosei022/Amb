from rest_framework import serializers
from .models import User, Quiz, Question, Submission, Answer, Result

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'contact_number', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            contact_number=validated_data.get('contact_number')
        )

        user.set_password(validated_data['password'])

        # 🔒 force student by default
        user.is_teacher = False
        user.is_staff = False
        user.is_superuser = False

        user.save()
        return user
    
class QuizSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = ['id', 'title', 'source_file_url', 'created_by', 'created_at']
        read_only_fields = ['created_by', 'created_at']

    def validate(self, data):
        user = self.context['request'].user

        if not user.is_teacher:
            raise serializers.ValidationError("Only teachers can create quizzes.")

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            'id',
            'quiz',
            'question_text',
            'question_type',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer',
            'marks'
        ]

    def validate(self, data):
        user = self.context['request'].user

        # 🔒 only teachers allowed
        if not user.is_teacher:
            raise serializers.ValidationError("Only teachers can add questions.")

        q_type = data.get('question_type')

        if q_type == 'mcq':
            for opt in ['option_a', 'option_b', 'option_c', 'option_d']:
                if not data.get(opt):
                    raise serializers.ValidationError("All MCQ options are required.")

        elif q_type == 'theory':
            data['option_a'] = None
            data['option_b'] = None
            data['option_c'] = None
            data['option_d'] = None

        return data
    
class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['id', 'student', 'quiz', 'submitted_at']
        read_only_fields = ['submitted_at']

    def validate(self, data):
        user = self.context['request'].user

        if user.is_teacher:
            raise serializers.ValidationError("Teachers cannot submit quizzes.")

        return data

    def create(self, validated_data):
        validated_data['student'] = self.context['request'].user
        return super().create(validated_data)

class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'submission', 'question', 'selected_answer']

class ResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Result
        fields = ['id', 'submission', 'score', 'total_marks', 'percentage', 'graded_at']
        read_only_fields = fields