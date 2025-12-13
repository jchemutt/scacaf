from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.contrib.taggit import ClusterTaggableManager
from taggit.models import TaggedItemBase

from wagtail import blocks
from wagtail.admin.panels import (
    FieldPanel, MultiFieldPanel, InlinePanel, HelpPanel
)
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page, Orderable
from wagtail.search import index
from wagtail.snippets.models import register_snippet
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.models import Image
from django.core.exceptions import ValidationError
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet
from django.db.models import F

# Optional media (video/audio) support
try:
    from wagtailmedia.blocks import VideoChooserBlock
    HAS_MEDIA = True
except Exception:
    HAS_MEDIA = False


# ============================================================
#  SHARED SNIPPETS (Taxonomies)
# ============================================================

@register_snippet
class Topic(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@register_snippet
class Audience(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@register_snippet
class Region(models.Model):
    name = models.CharField(max_length=120, unique=True)
    iso = models.CharField(
        max_length=12, blank=True,
        help_text="Optional short code (e.g., KE, EAC, SSA)"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


@register_snippet
class Language(models.Model):
    code = models.CharField(max_length=10, unique=True, help_text="e.g., en, fr, pt")
    name = models.CharField(max_length=60, unique=True, help_text="e.g., English")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


@register_snippet
class GlossaryEntry(models.Model):
    term = models.CharField(max_length=150, unique=True)
    definition = RichTextField()

    class Meta:
        ordering = ["term"]

    def __str__(self):
        return self.term


# ============================================================
#  TAGGING SUPPORT (ad-hoc tags)
# ============================================================

class ResourceTag(TaggedItemBase):
    content_object = ParentalKey(
        "ResourcePage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )




import urllib.parse
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock

import urllib.parse

from django.conf import settings
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock


class OfficeEmbedBlock(blocks.StructBlock):
    document = DocumentChooserBlock(required=True)

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)

        doc = value.get("document")
        request = (parent_context or {}).get("request")

        embed_url = None

        if doc:
            # 1) Try to build an absolute URL from the request (if available)
            if request is not None:
                absolute_url = request.build_absolute_uri(doc.url)
            # 2) Fallback: use WAGTAILADMIN_BASE_URL or similar setting
            elif hasattr(settings, "WAGTAILADMIN_BASE_URL"):
                absolute_url = settings.WAGTAILADMIN_BASE_URL.rstrip("/") + doc.url
            # 3) Last resort: use the relative URL (will still work for the iframe HTML,
            #    but Office Online may not be able to fetch it if it's not public)
            else:
                absolute_url = doc.url

            encoded = urllib.parse.quote(absolute_url, safe="")
            embed_url = (
                f"https://view.officeapps.live.com/op/embed.aspx?src={encoded}"
            )

        context["embed_url"] = embed_url
        context["document"] = doc
        return context

    class Meta:
        template = "blocks/office_embed.html"
        icon = "doc-full"
        label = "Office Document Viewer"



# ============================================================
#  HOME PAGE
# ============================================================

class HomePage(Page):
    template = "portal/home_page.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    def get_context(self, request):
        from .models import (
            RepositoryIndexPage, ExpertIndexPage,
            WebinarIndexPage, TestimonialIndexPage, ResourcePage,
            WebinarPage, ExpertPage, TestimonialPage
        )
        context = super().get_context(request)

        repo_index = RepositoryIndexPage.objects.live().first()
        experts_index = ExpertIndexPage.objects.live().first()
        webinars_index = WebinarIndexPage.objects.live().first()
        testimonials_index = TestimonialIndexPage.objects.live().first()

        featured_resources = []
        if repo_index:
            featured_resources = (
                ResourcePage.objects.descendant_of(repo_index)
                .live()
                .filter(featured=True)  
                .order_by("-date", "-last_published_at")[:6]
            )

        context.update({
            "repo_index": repo_index,
            "experts_index": experts_index,
            "webinars_index": webinars_index,
            "testimonials_index": testimonials_index,

            "featured_resources": featured_resources,

            "upcoming_webinars": WebinarPage.objects.live()
                .filter(start_datetime__gte=models.functions.Now())
                .order_by("start_datetime")[:3],

            "experts": ExpertPage.objects.live()[:8],
            "testimonials": TestimonialPage.objects.live()[:4],
        })
        return context


# ============================================================
#  REPOSITORY
# ============================================================

class RepositoryIndexPage(Page):
    template = "portal/repository_index_page.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro")
    ]

    def get_context(self, request):
        context = super().get_context(request)

        qs = ResourcePage.objects.descendant_of(self).live().order_by(
            F("learning_order").asc(nulls_last=True),
            "-date",
            "-last_published_at",
        )
        q = request.GET.get("q")
        kind = request.GET.get("kind")
        topic = request.GET.get("topic")
        audience = request.GET.get("audience")
        region = request.GET.get("region")
        language = request.GET.get("language")

        if q:
            qs = qs.search(q)
        if kind:
            qs = qs.filter(kind=kind)
        if topic:
            qs = qs.filter(topics__name=topic)
        if audience:
            qs = qs.filter(audiences__name=audience)
        if region:
            qs = qs.filter(regions__name=region)
        if language:
            qs = qs.filter(languages__code=language)

        context.update({
            "resources": qs,
            "topics": Topic.objects.all(),
            "audiences": Audience.objects.all(),
            "regions": Region.objects.all(),
            "languages": Language.objects.all(),
        })
        return context


class ResourcePage(Page, index.Indexed):
    """
    Robust resource model:
    - kind: document/video/tool/template/link/dataset
    - date: when it was created/published (for ordering)
    - featured: show on home
    - thumbnail: card image
    - attachments: multiple Wagtail Documents (orderable)
    - links: multiple external links (orderable)
    - body: stream (embed, notes, doc, media)
    - taxonomies: topics, audiences, regions, languages
    - tags: ad-hoc
    - validation in `clean()`
    """
    template = "portal/resource_page.html"

    class Kind(models.TextChoices):
        DOCUMENT = "document", _("Document")
        VIDEO = "video", _("Video")
        TOOL = "tool", _("Tool / App")
        TEMPLATE = "template", _("Template")
        LINK = "link", _("External Link")
        DATASET = "dataset", _("Dataset")

    kind = models.CharField(max_length=20, choices=Kind.choices)
    date = models.DateField(help_text="Resource date (publish/issue).")
    featured = models.BooleanField(default=False)
    learning_order = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Optional sequence number for learning journey (1 = first).")
    )

    abstract = RichTextField(blank=True)

    thumbnail = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Card image / preview thumbnail."
    )

    topics    = ParentalManyToManyField(Topic, blank=True, related_name="resources")
    audiences = ParentalManyToManyField(Audience, blank=True, related_name="resources")
    regions   = ParentalManyToManyField(Region, blank=True, related_name="resources")
    languages = ParentalManyToManyField(Language, blank=True, related_name="resources")

    tags = ClusterTaggableManager(through=ResourceTag, blank=True)

    body = StreamField(
    [
        ("notes", blocks.RichTextBlock(features=["h2","h3","bold","italic","ol","ul","link","hr"])),
        ("document", DocumentChooserBlock(help_text="Inline extra document (optional)")),
        ("external_link", blocks.URLBlock(help_text="Inline extra URL (optional)")),
        ("embed", EmbedBlock(help_text="Embed video or webpage")),
        ("office_viewer", OfficeEmbedBlock(help_text="Preview Word, PowerPoint, Excel inline")),
    ] + (
        [("video", VideoChooserBlock(help_text="Inline video (optional)"))] if HAS_MEDIA else []
    ),
    use_json_field=True,
    blank=True,
    )
    # ---- Search ----
    search_fields = Page.search_fields + [
        index.SearchField("title", partial_match=True, boost=3.0),
        index.SearchField("abstract", boost=2.0),
        index.FilterField("kind"),
        index.FilterField("date"),
        index.RelatedFields("topics", [index.SearchField("name")]),
        index.RelatedFields("audiences", [index.SearchField("name")]),
        index.RelatedFields("regions", [index.SearchField("name")]),
        index.RelatedFields("languages", [index.SearchField("name"), index.SearchField("code")]),
        index.SearchField("tags"),
    ]

    # ---- Panels ----
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel("kind"),
            FieldPanel("date"),
            FieldPanel("featured"),
            FieldPanel("learning_order"),
            FieldPanel("thumbnail"),
        ], heading="Basics"),
        FieldPanel("abstract"),
        MultiFieldPanel([
            InlinePanel("files", label="Attachment"),
            InlinePanel("links", label="External link"),
        ], heading="Attachments & Links"),
        MultiFieldPanel([
            FieldPanel("topics"),
            FieldPanel("audiences"),
            FieldPanel("regions"),
            FieldPanel("languages"),
            FieldPanel("tags"),
        ], heading="Classification"),
        FieldPanel("body"),
        HelpPanel(content="<p><strong>Tip:</strong> For <em>Document/Template</em>, add at least one file. For <em>Tool/Link</em>, add at least one URL. For <em>Video</em>, embed or add media.</p>"),
    ]

    

    # Convenience accessors
    @property
    def primary_file(self):
        return self.files.first().document if self.files.exists() else None

    @property
    def primary_link(self):
        return self.links.first().url if self.links.exists() else None
    

    def _learning_sequence_qs(self):
        """
        All resources in the same repository (if any),
        ordered by learning_order (NULLs last), then date & id for stability.
        """
        # We are already in models.py, so we can refer to RepositoryIndexPage directly
        repo_root = self.get_ancestors().type(RepositoryIndexPage).last()

        qs = ResourcePage.objects.live()

        if repo_root:
            qs = qs.descendant_of(repo_root)

        return qs.order_by(
            F("learning_order").asc(nulls_last=True),
            "-date",
            "-last_published_at",
            "id",
        )

    def _learning_sequence_list(self):
        """
        Materialise the queryset into a list so we can use index-based previous/next.
        """
        return list(self._learning_sequence_qs())

    @property
    def previous_in_sequence(self):
        """
        Previous resource in the ordered learning sequence, or None.
        """
        seq = self._learning_sequence_list()
        try:
            idx = seq.index(self)
        except ValueError:
            # This page isn’t in the sequence list (should be rare)
            return None

        if idx == 0:
            return None
        return seq[idx - 1]

    @property
    def next_in_sequence(self):
        """
        Next resource in the ordered learning sequence, or None.
        """
        seq = self._learning_sequence_list()
        try:
            idx = seq.index(self)
        except ValueError:
            return None

        if idx >= len(seq) - 1:
            return None
        return seq[idx + 1]



class ResourceFile(Orderable):
    page = ParentalKey(ResourcePage, related_name="files", on_delete=models.CASCADE)
    label = models.CharField(max_length=200, blank=True, help_text="Optional display name")
    document = models.ForeignKey(
        "wagtaildocs.Document", on_delete=models.CASCADE, related_name="+"
    )

    panels = [
        FieldPanel("document"),
        FieldPanel("label"),
    ]

    def __str__(self):
        return self.label or (self.document and self.document.title) or "File"


class ResourceLink(Orderable):
    page = ParentalKey(ResourcePage, related_name="links", on_delete=models.CASCADE)
    label = models.CharField(max_length=200, blank=True, help_text="Optional display name")
    url = models.URLField()

    panels = [
        FieldPanel("url"),
        FieldPanel("label"),
    ]

    def __str__(self):
        return self.label or self.url


# ============================================================
#  EXPERTS
# ============================================================

class ExpertIndexPage(Page):
    template = "portal/expert_index_page.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro")
    ]

    def get_context(self, request):
        ctx = super().get_context(request)

        qs = ExpertPage.objects.descendant_of(self).live()

        q = request.GET.get("q")
        topic = request.GET.get("topic")
        region = request.GET.get("region")
        language = request.GET.get("language")

        if q:
            qs = qs.search(q)
        if topic:
            qs = qs.filter(expertise__name=topic)
        if region:
            qs = qs.filter(regions__name=region)
        if language:
            qs = qs.filter(languages__code=language)

        ctx.update({
            "experts": qs,
            "topics": Topic.objects.all(),
            "regions": Region.objects.all(),
            "languages": Language.objects.all(),
        })
        return ctx


class ExpertPage(Page, index.Indexed):
    template = "portal/expert_page.html"

    organization = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=150, blank=True)
    photo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    bio = RichTextField(blank=True)

    # Replace free-text languages with snippet relation:
    languages = ParentalManyToManyField(Language, blank=True, related_name="experts")

    expertise = ParentalManyToManyField(Topic, blank=True, related_name="experts")
    regions   = ParentalManyToManyField(Region, blank=True, related_name="experts")

    search_fields = Page.search_fields + [
        index.SearchField("title", partial_match=True, boost=3.0),
        index.SearchField("organization"),
        index.SearchField("role"),
        index.SearchField("bio"),
        index.RelatedFields("languages", [index.SearchField("name"), index.SearchField("code")]),
        index.RelatedFields("expertise", [index.SearchField("name")]),
        index.RelatedFields("regions", [index.SearchField("name")]),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("organization"),
        FieldPanel("role"),
        FieldPanel("photo"),
        FieldPanel("bio"),
        FieldPanel("languages"),
        FieldPanel("expertise"),
        FieldPanel("regions"),
    ]


# ============================================================
#  WEBINARS
# ============================================================

class WebinarIndexPage(Page):
    template = "portal/webinar_index_page.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro")
    ]

    def get_context(self, request):
        ctx = super().get_context(request)

        qs = WebinarPage.objects.descendant_of(self).live()

        q = request.GET.get("q")
        topic = request.GET.get("topic")
        when = request.GET.get("when")

        if q:
            qs = qs.search(q)
        if topic:
            qs = qs.filter(topics__name=topic)

        now = models.functions.Now()

        if when == "past":
            qs = qs.filter(start_datetime__lt=now).order_by("-start_datetime")
        else:
            qs = qs.filter(start_datetime__gte=now).order_by("start_datetime")

        ctx.update({
            "webinars": qs,
            "topics": Topic.objects.all(),
        })
        return ctx


class WebinarPage(Page, index.Indexed):
    template = "portal/webinar_page.html"

    start_datetime = models.DateTimeField()
    platform = models.CharField(max_length=80, blank=True)
    registration_url = models.URLField(blank=True)

    topics   = ParentalManyToManyField(Topic, blank=True, related_name="webinars")
    speakers = ParentalManyToManyField("ExpertPage", blank=True, related_name="talks")
    languages = ParentalManyToManyField(Language, blank=True, related_name="webinars")

    recording = StreamField(
        [("video", VideoChooserBlock())] if HAS_MEDIA else [],
        use_json_field=True,
        blank=True,
    )

    materials = StreamField(
        [("slides", DocumentChooserBlock())],
        use_json_field=True,
        blank=True,
    )

    search_fields = Page.search_fields + [
        index.SearchField("title", partial_match=True, boost=3.0),
        index.SearchField("platform"),
        index.FilterField("start_datetime"),
        index.RelatedFields("topics", [index.SearchField("name")]),
        index.RelatedFields("languages", [index.SearchField("name"), index.SearchField("code")]),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("start_datetime"),
        FieldPanel("platform"),
        FieldPanel("registration_url"),
        FieldPanel("topics"),
        FieldPanel("languages"),
        FieldPanel("speakers"),
        FieldPanel("recording"),
        FieldPanel("materials"),
    ]


# ============================================================
#  TESTIMONIALS
# ============================================================

class TestimonialIndexPage(Page):
    template = "portal/testimonial_index_page.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro")
    ]

    def get_context(self, request):
        ctx = super().get_context(request)

        qs = TestimonialPage.objects.descendant_of(self).live().order_by(
            "-first_published_at"
        )

        topic = request.GET.get("topic")
        if topic:
            qs = qs.filter(topics__name=topic)

        ctx.update({
            "testimonials": qs,
            "topics": Topic.objects.all(),
        })
        return ctx


class TestimonialPage(Page, index.Indexed):
    template = "portal/testimonial_page.html"

    author = models.CharField(max_length=150)
    org = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=150, blank=True)
    quote = models.TextField()

    video = (
        models.ForeignKey(
            "wagtailmedia.Media",
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            related_name="+",
        )
        if HAS_MEDIA
        else None
    )

    topics = ParentalManyToManyField(Topic, blank=True, related_name="testimonials")

    about_resource = models.ForeignKey(
        "ResourcePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="testimonials",
    )

    about_webinar = models.ForeignKey(
        "WebinarPage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="testimonials",
    )

    search_fields = Page.search_fields + [
        index.SearchField("author", partial_match=True, boost=3.0),
        index.SearchField("org"),
        index.SearchField("role"),
        index.SearchField("quote"),
        index.RelatedFields("topics", [index.SearchField("name")]),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("author"),
        FieldPanel("org"),
        FieldPanel("role"),
        FieldPanel("quote"),
        FieldPanel("topics"),
        FieldPanel("about_resource"),
        FieldPanel("about_webinar"),
    ] + ([FieldPanel("video")] if HAS_MEDIA else [])
