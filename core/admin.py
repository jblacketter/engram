from django.contrib import admin

from .models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ("id", "short_content", "source", "importance", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("content",)
    readonly_fields = ("id", "content_tsv", "created_at", "updated_at")

    def short_content(self, obj):
        return obj.content[:100]

    short_content.short_description = "Content"
