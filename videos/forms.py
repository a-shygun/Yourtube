from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Write a comment...",
                "class": "w-full border border-input-border bg-surface px-3 py-2 text-sm",
            }),
        }
