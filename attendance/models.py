from django.db import models
from django.utils import timezone
import random
import string

def generate_unique_id():
    # Example format: ID-ABCDE
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"ID-{random_str}"

def generate_institute_code():
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"INST-{random_str}"

class Institute(models.Model):
    name = models.CharField(max_length=200)
    unique_code = models.CharField(max_length=15, unique=True, default=generate_institute_code)
    password = models.CharField(max_length=128)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.unique_code})"


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )

    user_id = models.CharField(max_length=10, unique=True, default=generate_unique_id)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    
    # Specific fields
    department = models.CharField(max_length=100, blank=True, null=True)     # For teachers
    grade_class = models.CharField(max_length=50, blank=True, null=True)     # For students
    roll_number = models.CharField(max_length=50, blank=True, null=True)     # For students

    # Authentication
    password = models.CharField(max_length=128, blank=True, null=True)

    # The face_encoding will store a JSON-encoded array of 128 floats
    face_encoding = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_role_display()}] {self.name} - {self.user_id}"

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('Present', 'Present'),
        ('Late', 'Late'),
    )
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='attendances')
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Present')

    def __str__(self):
        return f"{self.user.name} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({self.status})"
