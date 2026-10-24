from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class StudentSerializer(serializers.ModelSerializer):
    """A student as seen in the staff directory and on reservations."""

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email', 'student_number', 'course', 'year']
        read_only_fields = ['username']


class CurrentUserSerializer(serializers.ModelSerializer):
    """The signed-in user, including the role the frontend uses to shape its navigation."""

    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name', 'email', 'student_number', 'course', 'year',
            'is_staff', 'role',
        ]
        read_only_fields = ['username', 'student_number', 'is_staff']

    def get_role(self, user) -> str:
        return 'staff' if user.is_staff else 'student'

    def validate_email(self, email):
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('An account with this email address already exists.')
        return email


class RegisterSerializer(serializers.ModelSerializer):
    """Self-service sign-up, which always creates a student account."""

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'student_number', 'course', 'year']
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'student_number': {'required': True, 'allow_null': False, 'allow_blank': False},
            'course': {'required': True, 'allow_blank': False},
            'year': {'required': True, 'allow_null': False},
        }

    def validate_email(self, email):
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email address already exists.')
        return email

    def validate_student_number(self, student_number):
        student_number = student_number.strip().upper()
        if User.objects.filter(student_number__iexact=student_number).exists():
            raise serializers.ValidationError('An account with this student number already exists.')
        return student_number

    def validate(self, attrs):
        # Django's password validators also compare the password with the other details.
        candidate = User(**{key: value for key, value in attrs.items() if key != 'password'})
        try:
            validate_password(attrs['password'], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
