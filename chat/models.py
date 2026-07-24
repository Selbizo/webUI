from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ChatSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    messages = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session {self.session_id} - {self.user or 'guest'}"
    
    class Meta:
        ordering = ['-updated_at']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=50, default='user')
    created_at = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.department}"
