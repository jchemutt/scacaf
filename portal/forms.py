from django import forms

class FooterNewsletterForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "placeholder": "Your email",
            "autocomplete": "email",
        })
    )
    # Honeypot anti-spam field (should stay empty)
    website = forms.CharField(required=False)

    def clean_website(self):
        val = self.cleaned_data.get("website", "")
        if val:
            raise forms.ValidationError("Spam detected.")
        return val
    


class ContactUsForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-xl border border-slate-300/70 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500",
            "placeholder": "Your full name",
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full rounded-xl border border-slate-300/70 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500",
            "placeholder": "you@example.org",
        })
    )

    organization = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-xl border border-slate-300/70 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500",
            "placeholder": "Organization (optional)",
        })
    )

    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-xl border border-slate-300/70 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500",
            "placeholder": "Subject",
        })
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 6,
            "class": "w-full rounded-xl border border-slate-300/70 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500",
            "placeholder": "How can we help you?",
        })
    )

    # Honeypot (hidden field): real users won't fill it, bots often do
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "tabindex": "-1",
            "autocomplete": "off",
            "class": "hidden",
            "aria-hidden": "true",
        })
    )    