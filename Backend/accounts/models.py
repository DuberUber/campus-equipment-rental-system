from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Upper


class User(AbstractUser):
    """A campus account. Students reserve equipment with it; desk staff (``is_staff``) sign in with one too."""

    # unique=True gives email its (unique) index; the Upper() index below serves case-insensitive lookups.
    email = models.EmailField('email address', unique=True)
    # Students only; staff accounts leave it empty (NULL, so the unique constraint ignores them).
    student_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    course = models.CharField(max_length=120, blank=True)
    year = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(7)], help_text='Year of study.'
    )

    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['last_name', 'first_name', 'username']
        indexes = [
            models.Index(Upper('email'), name='user_email_ci_idx'),
            # Backs the default ordering and name searches in the student directory.
            models.Index(fields=['last_name', 'first_name'], name='user_name_idx'),
        ]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        # Forms submit a blank student number as ''; store NULL so several staff accounts can leave it empty.
        if not self.student_number:
            self.student_number = None
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_student(self) -> bool:
        return not self.is_staff
