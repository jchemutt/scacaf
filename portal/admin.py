from django.contrib import admin

# Register your models here.
from .models import ContactSubmission


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "subject", "status", "page")
    list_filter = ("status", "created_at", "page")
    search_fields = ("name", "email", "subject", "message", "organization")
    readonly_fields = ("created_at", "ip_address", "user_agent")

    fieldsets = (
        ("Submission", {
            "fields": ("page", "created_at", "status")
        }),
        ("Sender", {
            "fields": ("name", "email", "organization")
        }),
        ("Message", {
            "fields": ("subject", "message")
        }),
        ("Technical", {
            "fields": ("ip_address", "user_agent")
        }),
    )
