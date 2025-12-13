# portal/context_processors.py
from wagtail.models import Site
from .models import RepositoryIndexPage, ExpertIndexPage, WebinarIndexPage, TestimonialIndexPage

def portal_index_pages(request):
    site = Site.find_for_request(request)
    if not site:
        return {}

    root = site.root_page

    return {
        "repo_index": RepositoryIndexPage.objects.child_of(root).live().first(),
        "experts_index": ExpertIndexPage.objects.child_of(root).live().first(),
        "webinars_index": WebinarIndexPage.objects.child_of(root).live().first(),
        "testimonials_index": TestimonialIndexPage.objects.child_of(root).live().first(),
    }
