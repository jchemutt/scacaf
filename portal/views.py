from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from wagtail.models import Site

from .forms import FooterNewsletterForm
from .models import NewsletterSubscriber


@require_POST
def newsletter_subscribe(request):
    form = FooterNewsletterForm(request.POST)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"

    if not form.is_valid():
        messages.error(request, "Please enter a valid email address.")
        return redirect(next_url)

    email = form.cleaned_data["email"].strip().lower()
    source = (request.POST.get("source") or "footer").strip()[:50]

    current_site = None
    try:
        current_site = Site.find_for_request(request)
    except Exception:
        current_site = None

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "site": current_site,
            "source": source,
            "status": NewsletterSubscriber.Status.SUBSCRIBED,
        },
    )

    if created:
        messages.success(request, "Thanks for subscribing — you’ll receive updates from SCACAF e-Hub.")
        return redirect(next_url)

    # Existing subscriber found
    if subscriber.status == NewsletterSubscriber.Status.UNSUBSCRIBED:
        subscriber.status = NewsletterSubscriber.Status.SUBSCRIBED
        subscriber.unsubscribed_at = None
        if current_site and not subscriber.site:
            subscriber.site = current_site
        if source and not subscriber.source:
            subscriber.source = source
        subscriber.save()
        messages.success(request, "Welcome back — your subscription has been re-activated.")
        return redirect(next_url)

    messages.info(request, "You’re already subscribed with that email.")
    return redirect(next_url)


