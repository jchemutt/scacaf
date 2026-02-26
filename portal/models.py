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
from modelcluster.models import ClusterableModel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from django.utils import timezone
from wagtail.models import Site 
import urllib.parse
from wagtail import blocks
from django.conf import settings
from django import forms
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils.html import strip_tags



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
#  PARTNERS (Reusable snippets)
# ============================================================

@register_snippet
class Partner(models.Model):
    """
    Single partner record (logo + link). Reusable across multiple rows/pages.
    """
    name = models.CharField(max_length=150, unique=True)
    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Preferred: transparent PNG/WebP logo"
    )
    website_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    # Optional metadata (for future filtering/grouping)
    partner_type = models.CharField(
        max_length=60,
        blank=True,
        help_text="e.g. Donor, Implementing Partner, Knowledge Partner"
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("logo"),
        FieldPanel("website_url"),
        FieldPanel("partner_type"),
        FieldPanel("is_active"),
        FieldPanel("sort_order"),
    ]

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


@register_snippet
class PartnerRow(ClusterableModel):
    """
    Reusable curated partner strip/row.
    Example rows:
      - Core Partners
      - Training Delivery Partners
      - Knowledge Partners
    """
    class StyleVariant(models.TextChoices):
        DEFAULT = "default", "Default"
        SOFT = "soft", "Soft"
        COMPACT = "compact", "Compact"

    title = models.CharField(max_length=120, default="Partners")
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="Unique key for reuse (e.g. core-partners, training-partners)"
    )
    subtitle = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional helper text shown below title"
    )
    style_variant = models.CharField(
        max_length=20,
        choices=StyleVariant.choices,
        default=StyleVariant.DEFAULT,
    )
    is_active = models.BooleanField(default=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("slug"),
        FieldPanel("subtitle"),
        FieldPanel("style_variant"),
        FieldPanel("is_active"),
        InlinePanel("items", label="Partners in this row"),
    ]

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def visible_items(self):
        return (
            self.items.select_related("partner", "partner__logo")
            .filter(partner__is_active=True)
        )


class PartnerRowItem(Orderable):
    """
    Partner membership inside a PartnerRow, with per-row ordering
    and optional label/link overrides.
    """
    row = ParentalKey("PartnerRow", related_name="items", on_delete=models.CASCADE)
    partner = models.ForeignKey("Partner", on_delete=models.CASCADE, related_name="+")
    custom_label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional display label (defaults to partner name)"
    )
    link_override = models.URLField(
        blank=True,
        help_text="Optional custom URL (defaults to partner.website_url)"
    )

    panels = [
        FieldPanel("partner"),
        FieldPanel("custom_label"),
        FieldPanel("link_override"),
    ]

    def __str__(self):
        return self.custom_label or str(self.partner)


# ============================================================
#  PORTAL SETTINGS (Site-wide defaults)
# ============================================================

@register_setting
class PortalSiteSettings(BaseSiteSetting):
    """
    Site-level defaults for reusable partner rows.
    """
    default_partner_row = models.ForeignKey(
        "PartnerRow",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        limit_choices_to={"is_active": True},
        help_text="Default partner row used on pages that don't choose one explicitly.",
    )
    footer_partner_row = models.ForeignKey(
        "PartnerRow",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        limit_choices_to={"is_active": True},
        help_text="Optional compact partner row for near-footer placement.",
    )

    panels = [
        FieldPanel("default_partner_row"),
        FieldPanel("footer_partner_row"),
    ]

@register_snippet
class NewsletterSubscriber(index.Indexed, models.Model):
    class Status(models.TextChoices):
        SUBSCRIBED = "subscribed", "Subscribed"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120, blank=True)
    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="newsletter_subscribers",
        help_text="Site where this signup was captured."
    )
    source = models.CharField(
        max_length=50,
        blank=True,
        default="footer",
        help_text="Where signup came from (e.g. footer, popup, page)."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBSCRIBED
    )
    subscribed_at = models.DateTimeField(default=timezone.now)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    panels = [
        FieldPanel("email"),
        FieldPanel("full_name"),
        FieldPanel("site"),
        FieldPanel("source"),
        FieldPanel("status"),
        FieldPanel("notes"),
    ]

    search_fields = [
        index.SearchField("email", partial_match=True),
        index.SearchField("full_name", partial_match=True),
        index.FilterField("status"),
        index.FilterField("source"),
    ]

    class Meta:
        ordering = ["-subscribed_at"]
        verbose_name = "Newsletter subscriber"
        verbose_name_plural = "Newsletter subscribers"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)
# ============================================================
#  TAGGING SUPPORT (ad-hoc tags)
# ============================================================

class ResourceTag(TaggedItemBase):
    content_object = ParentalKey(
        "ResourcePage",
        related_name="tagged_items",
        on_delete=models.CASCADE,
    )






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


class PDFEmbedBlock(blocks.StructBlock):
    document = DocumentChooserBlock(required=True, help_text="Upload a PDF document")

    class Meta:
        template = "blocks/pdf_embed.html"
        icon = "doc-full"
        label = "PDF Viewer"

# ============================================================
#  HOME PAGE
# ============================================================

class HomePage(Page):
    template = "portal/home_page.html"

    intro = RichTextField(blank=True)
    partner_row = models.ForeignKey(
        "PartnerRow",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        limit_choices_to={"is_active": True},
        help_text="Optional page-specific partners row. If empty, site default is used."
    )   

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("partner_row"),
    ]

    def get_context(self, request):
        from .models import (
            RepositoryIndexPage, ExpertIndexPage,
            WebinarIndexPage, TestimonialIndexPage, ResourcePage,
            WebinarPage, ExpertPage, TestimonialPage
        )
        context = super().get_context(request)
        site_settings = PortalSiteSettings.for_request(request)
        resolved_partner_row = self.partner_row or site_settings.default_partner_row

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

        # ------------------------------------------------------------
        # Home page summary counts (for the stat cards section)
        # ------------------------------------------------------------
        resource_count = (
            ResourcePage.objects.descendant_of(repo_index).live().count()
            if repo_index else ResourcePage.objects.live().count()
        )
        webinar_count = (
            WebinarPage.objects.descendant_of(webinars_index).live().count()
            if webinars_index else WebinarPage.objects.live().count()
        )
        expert_count = (
            ExpertPage.objects.descendant_of(experts_index).live().count()
            if experts_index else ExpertPage.objects.live().count()
        )
        testimonial_count = (
            TestimonialPage.objects.descendant_of(testimonials_index).live().count()
            if testimonials_index else TestimonialPage.objects.live().count()
        )

        context.update({
            "repo_index": repo_index,
            "experts_index": experts_index,
            "webinars_index": webinars_index,
            "testimonials_index": testimonials_index,
            "partner_row": resolved_partner_row,
            

            # Summary counts
            "resource_count": resource_count,
            "webinar_count": webinar_count,
            "expert_count": expert_count,
            "testimonial_count": testimonial_count,

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
        ("pdf_viewer", PDFEmbedBlock(help_text="Preview pdf")),
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
#  TRAININGS
# ============================================================

class TrainingIndexPage(Page):
    template = "portal/training_index_page.html"

    intro = RichTextField(blank=True)

    # Optional page type constraints (uncomment if you want stricter structure)
    # parent_page_types = ["portal.HomePage"]
    # subpage_types = ["portal.TrainingPage"]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    def get_context(self, request):
        ctx = super().get_context(request)

        base_qs = (
            TrainingPage.objects.descendant_of(self)
            .live()
            .order_by(
                F("featured").desc(),
                F("start_date").asc(nulls_last=True),
                "-last_published_at",
            )
        )

        qs = base_qs

        q = request.GET.get("q")
        topic = request.GET.get("topic")
        audience = request.GET.get("audience")
        region = request.GET.get("region")
        language = request.GET.get("language")
        delivery_format = request.GET.get("format")
        status = request.GET.get("status")
        level = request.GET.get("level")
        sort = request.GET.get("sort", "soonest")

        if q:
            qs = qs.search(q)
        if topic:
            qs = qs.filter(topics__name=topic)
        if audience:
            qs = qs.filter(audiences__name=audience)
        if region:
            qs = qs.filter(regions__name=region)
        if language:
            qs = qs.filter(languages__code=language)
        if delivery_format:
            qs = qs.filter(delivery_format=delivery_format)
        if status:
            qs = qs.filter(status=status)
        if level:
            qs = qs.filter(level=level)

        # Sorting
        if sort == "recent":
            qs = qs.order_by("-first_published_at")
        elif sort == "oldest":
            qs = qs.order_by("first_published_at")
        elif sort == "title_asc":
            qs = qs.order_by("title")
        elif sort == "title_desc":
            qs = qs.order_by("-title")
        else:
            # Default: soonest start first, then featured/newer
            qs = qs.order_by(
                F("featured").desc(),
                F("start_date").asc(nulls_last=True),
                "-last_published_at",
            )

        qs = qs.distinct()

        featured_trainings = (
            base_qs.filter(featured=True)
            .order_by(
                F("start_date").asc(nulls_last=True),
                "-last_published_at",
            )[:8]
        )

        ctx.update({
            "trainings": qs,
            "featured_trainings": featured_trainings,
            "topics": Topic.objects.all(),
            "audiences": Audience.objects.all(),
            "regions": Region.objects.all(),
            "languages": Language.objects.all(),
            "training_formats": TrainingPage.DeliveryFormat.choices,
            "training_statuses": TrainingPage.Status.choices,
            "training_levels": TrainingPage.Level.choices,
        })
        return ctx


class TrainingPage(Page, index.Indexed):
    template = "portal/training_page.html"

    # Optional page type constraints (uncomment if you want stricter structure)
    # parent_page_types = ["portal.TrainingIndexPage"]
    # subpage_types = []

    class Status(models.TextChoices):
        OPEN = "open", _("Open for registration")
        UPCOMING = "upcoming", _("Upcoming")
        ONGOING = "ongoing", _("Ongoing")
        COMPLETED = "completed", _("Completed")
        SELF_PACED = "self_paced", _("Self-paced")

    class DeliveryFormat(models.TextChoices):
        ONLINE = "online", _("Online")
        IN_PERSON = "in_person", _("In-person")
        HYBRID = "hybrid", _("Hybrid")
        SELF_PACED = "self_paced", _("Self-paced")
        COHORT = "cohort", _("Cohort-based")

    class Level(models.TextChoices):
        BEGINNER = "beginner", _("Beginner")
        INTERMEDIATE = "intermediate", _("Intermediate")
        ADVANCED = "advanced", _("Advanced")

    summary = models.TextField(blank=True, help_text="Short summary shown on cards and hero sections.")
    featured = models.BooleanField(default=False)

    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional cover image for cards and page header."
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    delivery_format = models.CharField(max_length=20, choices=DeliveryFormat.choices, default=DeliveryFormat.ONLINE)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    registration_deadline = models.DateField(null=True, blank=True)

    duration_text = models.CharField(
        max_length=80,
        blank=True,
        help_text="e.g. 2 hours, 3 days, 6 weeks"
    )

    venue = models.CharField(max_length=255, blank=True, help_text="Physical venue or city (for in-person/hybrid).")
    platform = models.CharField(max_length=120, blank=True, help_text="Zoom, Teams, Moodle, etc.")
    application_url = models.URLField(blank=True, help_text="Registration / application link.")
    contact_email = models.EmailField(blank=True)
    certificate_available = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    topics = ParentalManyToManyField(Topic, blank=True, related_name="trainings")
    audiences = ParentalManyToManyField(Audience, blank=True, related_name="trainings")
    regions = ParentalManyToManyField(Region, blank=True, related_name="trainings")
    languages = ParentalManyToManyField(Language, blank=True, related_name="trainings")

    overview = RichTextField(blank=True)
    learning_outcomes = RichTextField(blank=True, help_text="What participants will learn.")
    who_should_join = RichTextField(blank=True, help_text="Intended audience / participant profile.")
    curriculum_notes = RichTextField(blank=True, help_text="Optional extra curriculum description.")
    faq = RichTextField(blank=True)

    body = StreamField(
        [
            ("notes", blocks.RichTextBlock(features=["h2", "h3", "bold", "italic", "ol", "ul", "link", "hr"])),
            ("document", DocumentChooserBlock(help_text="Inline training document (optional)")),
            ("external_link", blocks.URLBlock(help_text="Inline external URL (optional)")),
            ("embed", EmbedBlock(help_text="Embed video or webpage")),
            ("office_viewer", OfficeEmbedBlock(help_text="Preview Word, PowerPoint, Excel inline")),
            ("pdf_viewer", PDFEmbedBlock(help_text="Preview PDF inline")),
        ] + (
            [("video", VideoChooserBlock(help_text="Inline video (optional)"))] if HAS_MEDIA else []
        ),
        use_json_field=True,
        blank=True,
    )

    search_fields = Page.search_fields + [
        index.SearchField("title", partial_match=True, boost=3.0),
        index.SearchField("summary", boost=2.0),
        index.SearchField("overview"),
        index.SearchField("learning_outcomes"),
        index.SearchField("who_should_join"),
        index.SearchField("curriculum_notes"),
        index.FilterField("status"),
        index.FilterField("delivery_format"),
        index.FilterField("level"),
        index.FilterField("start_date"),
        index.RelatedFields("topics", [index.SearchField("name")]),
        index.RelatedFields("audiences", [index.SearchField("name")]),
        index.RelatedFields("regions", [index.SearchField("name")]),
        index.RelatedFields("languages", [index.SearchField("name"), index.SearchField("code")]),
    ]

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel("summary"),
            FieldPanel("featured"),
            FieldPanel("cover_image"),
        ], heading="Card & Hero"),

        MultiFieldPanel([
            FieldPanel("status"),
            FieldPanel("delivery_format"),
            FieldPanel("level"),
            FieldPanel("duration_text"),
        ], heading="Training setup"),

        MultiFieldPanel([
            FieldPanel("start_date"),
            FieldPanel("end_date"),
            FieldPanel("registration_deadline"),
            FieldPanel("venue"),
            FieldPanel("platform"),
            FieldPanel("application_url"),
            FieldPanel("contact_email"),
            FieldPanel("certificate_available"),
            FieldPanel("max_participants"),
        ], heading="Schedule & logistics"),

        MultiFieldPanel([
            FieldPanel("topics"),
            FieldPanel("audiences"),
            FieldPanel("regions"),
            FieldPanel("languages"),
        ], heading="Classification"),

        MultiFieldPanel([
            InlinePanel("trainers", label="Trainer"),
        ], heading="Facilitators / Trainers"),

        MultiFieldPanel([
            FieldPanel("overview"),
            FieldPanel("learning_outcomes"),
            FieldPanel("who_should_join"),
            FieldPanel("curriculum_notes"),
            FieldPanel("faq"),
            FieldPanel("body"),
        ], heading="Content"),

        MultiFieldPanel([
            InlinePanel("modules", label="Module"),
        ], heading="Curriculum modules"),

        MultiFieldPanel([
            InlinePanel("related_resources", label="Related resource"),
            InlinePanel("related_webinars", label="Related webinar"),
        ], heading="Links to repository & webinars"),
    ]

    def clean(self):
        super().clean()

        errors = {}

        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = _("End date cannot be earlier than start date.")

        if self.registration_deadline and self.start_date and self.registration_deadline > self.start_date:
            errors["registration_deadline"] = _("Registration deadline should be on or before the start date.")

        if errors:
            raise ValidationError(errors)

    @property
    def schedule_label(self):
        """
        Friendly date label for cards/templates.
        """
        if self.status == self.Status.SELF_PACED or self.delivery_format == self.DeliveryFormat.SELF_PACED:
            return "Self-paced"
        if self.start_date and self.end_date:
            if self.start_date == self.end_date:
                return self.start_date.strftime("%b %d, %Y")
            return f"{self.start_date.strftime('%b %d, %Y')} – {self.end_date.strftime('%b %d, %Y')}"
        if self.start_date:
            return self.start_date.strftime("%b %d, %Y")
        return ""


class TrainingTrainer(Orderable):
    page = ParentalKey("TrainingPage", related_name="trainers", on_delete=models.CASCADE)
    expert = models.ForeignKey(
        "ExpertPage",
        on_delete=models.CASCADE,
        related_name="training_roles",
    )
    label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional role label (e.g., Lead facilitator, Guest speaker)."
    )

    panels = [
        FieldPanel("expert"),
        FieldPanel("label"),
    ]

    def __str__(self):
        return f"{self.expert.title} ({self.label})" if self.label else self.expert.title


class TrainingModule(Orderable):
    page = ParentalKey("TrainingPage", related_name="modules", on_delete=models.CASCADE)

    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    duration_text = models.CharField(max_length=60, blank=True, help_text="e.g. 45 min, 1 week")

    resource = models.ForeignKey(
        "ResourcePage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="training_modules",
        help_text="Optional linked resource from the repository."
    )
    webinar = models.ForeignKey(
        "WebinarPage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="training_modules",
        help_text="Optional linked webinar/recording."
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("summary"),
        FieldPanel("duration_text"),
        FieldPanel("resource"),
        FieldPanel("webinar"),
    ]

    def clean(self):
        super().clean()
        if not self.resource and not self.webinar and not self.summary:
            raise ValidationError(_("Add a summary or link a resource/webinar for the module."))

    def __str__(self):
        return self.title


class TrainingRelatedResource(Orderable):
    page = ParentalKey("TrainingPage", related_name="related_resources", on_delete=models.CASCADE)
    resource = models.ForeignKey(
        "ResourcePage",
        on_delete=models.CASCADE,
        related_name="linked_trainings",
    )
    label = models.CharField(max_length=160, blank=True)

    panels = [
        FieldPanel("resource"),
        FieldPanel("label"),
    ]

    def __str__(self):
        return self.label or self.resource.title


class TrainingRelatedWebinar(Orderable):
    page = ParentalKey("TrainingPage", related_name="related_webinars", on_delete=models.CASCADE)
    webinar = models.ForeignKey(
        "WebinarPage",
        on_delete=models.CASCADE,
        related_name="linked_trainings",
    )
    label = models.CharField(max_length=160, blank=True)

    panels = [
        FieldPanel("webinar"),
        FieldPanel("label"),
    ]

    def __str__(self):
        return self.label or self.webinar.title
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


# =========================
# ABOUT PAGE
# =========================

class AboutPage(Page):
    template = "portal/about_page.html"

    page_description = (
        "Use this page to manage the About the Hub content "
        "(vision, mission, objectives, audiences, workflow, and CTA)."
    )

    # Optional: keep it only under Home and prevent child pages under it
    parent_page_types = ["portal.HomePage"]  # adjust app label if different
    subpage_types = []

    # --- Hero ---
    hero_kicker = models.CharField(
        max_length=80,
        default="About the hub",
        blank=True,
        help_text="Small label above the hero title (e.g. About the hub).",
    )
    hero_title = models.CharField(
        max_length=180,
        default="SCACAF e-Hub for climate adaptation finance learning and collaboration",
        help_text="Main heading shown in the hero section.",
    )
    hero_intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link", "ul", "ol"],
        help_text="Intro paragraph below the hero title.",
    )

    # --- Vision & Mission ---
    vision_title = models.CharField(max_length=120, default="Vision")
    vision_text = RichTextField(
        blank=True,
        features=["bold", "italic", "link", "ul", "ol"],
        help_text="Vision statement.",
    )

    mission_title = models.CharField(max_length=120, default="Mission")
    mission_text = RichTextField(
        blank=True,
        features=["bold", "italic", "link", "ul", "ol"],
        help_text="Mission statement.",
    )

    # --- Section headings / intros ---
    objectives_title = models.CharField(max_length=120, default="Objectives", blank=True)
    objectives_intro = RichTextField(blank=True, features=["bold", "italic", "link"])

    audiences_title = models.CharField(max_length=120, default="Who this hub is for", blank=True)
    audiences_intro = RichTextField(blank=True, features=["bold", "italic", "link"])

    features_title = models.CharField(max_length=120, default="What you can find in the hub", blank=True)
    features_intro = RichTextField(blank=True, features=["bold", "italic", "link"])

    workflow_title = models.CharField(max_length=120, default="How to use the hub", blank=True)
    workflow_intro = RichTextField(blank=True, features=["bold", "italic", "link"])

    principles_title = models.CharField(max_length=120, default="How we work", blank=True)
    principles_intro = RichTextField(blank=True, features=["bold", "italic", "link"])

    # --- CTA section ---
    cta_kicker = models.CharField(max_length=80, default="Get involved", blank=True)
    cta_title = models.CharField(
        max_length=160,
        default="Contribute, learn, and collaborate through the SCACAF e-Hub",
        blank=True,
    )
    cta_text = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
        help_text="CTA supporting text.",
    )

    cta_button_label = models.CharField(max_length=60, default="Contact us", blank=True)
    cta_button_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional internal page link for CTA button (preferred over URL).",
    )
    cta_button_url = models.URLField(
        blank=True,
        help_text="Optional external CTA button URL (used if no internal page is selected).",
    )

    cta_secondary_label = models.CharField(max_length=60, blank=True, default="")
    cta_secondary_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional internal secondary CTA link.",
    )
    cta_secondary_url = models.URLField(blank=True)

    # --- Optional live stats toggle (template can use this) ---
    show_live_stats = models.BooleanField(
        default=True,
        help_text="If enabled, the template can show live counts (resources, webinars, experts, etc.).",
    )

    content_panels = Page.content_panels + [
        # Hero
        FieldPanel("hero_kicker"),
        FieldPanel("hero_title"),
        FieldPanel("hero_intro"),

        # Vision / Mission
        FieldPanel("vision_title"),
        FieldPanel("vision_text"),
        FieldPanel("mission_title"),
        FieldPanel("mission_text"),

        # Objectives
        FieldPanel("objectives_title"),
        FieldPanel("objectives_intro"),
        InlinePanel("about_objectives", label="Objectives"),

        # Audiences
        FieldPanel("audiences_title"),
        FieldPanel("audiences_intro"),
        InlinePanel("about_audiences", label="Audience cards"),

        # Features / What the hub offers
        FieldPanel("features_title"),
        FieldPanel("features_intro"),
        InlinePanel("about_features", label="Feature cards"),

        # Workflow / How to use
        FieldPanel("workflow_title"),
        FieldPanel("workflow_intro"),
        InlinePanel("about_workflow_steps", label="Workflow steps"),

        # Principles
        FieldPanel("principles_title"),
        FieldPanel("principles_intro"),
        InlinePanel("about_principles", label="Principles"),

        # CTA
        FieldPanel("cta_kicker"),
        FieldPanel("cta_title"),
        FieldPanel("cta_text"),
        FieldPanel("cta_button_label"),
        FieldPanel("cta_button_page"),
        FieldPanel("cta_button_url"),
        FieldPanel("cta_secondary_label"),
        FieldPanel("cta_secondary_page"),
        FieldPanel("cta_secondary_url"),

        FieldPanel("show_live_stats"),
    ]

    search_fields = Page.search_fields + [
    index.SearchField("hero_title"),
    index.SearchField("hero_intro"),
    index.SearchField("vision_text"),
    index.SearchField("mission_text"),
    index.SearchField("objectives_intro"),
    index.SearchField("audiences_intro"),
    index.SearchField("features_intro"),
    index.SearchField("workflow_intro"),
    index.SearchField("principles_intro"),
    index.SearchField("cta_text"),
]

    @property
    def cta_primary_href(self):
        if self.cta_button_page:
            return self.cta_button_page.url
        return self.cta_button_url or "#"

    @property
    def cta_secondary_href(self):
        if self.cta_secondary_page:
            return self.cta_secondary_page.url
        return self.cta_secondary_url or "#"

    class Meta:
        verbose_name = "About page"


class AboutObjective(Orderable):
    page = ParentalKey(
        "portal.AboutPage",
        on_delete=models.CASCADE,
        related_name="about_objectives",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
    ]

    def __str__(self):
        return self.title


class AboutAudienceCard(Orderable):
    ICON_CHOICES = [
        ("users", "Users / community"),
        ("briefcase", "Practitioners / implementers"),
        ("bank", "Funders / institutions"),
        ("graduation-cap", "Learners / training"),
        ("globe", "Regional / global"),
        ("leaf", "Climate / agriculture"),
    ]

    page = ParentalKey(
        "portal.AboutPage",
        on_delete=models.CASCADE,
        related_name="about_audiences",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default="users")

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
        FieldPanel("icon"),
    ]

    def __str__(self):
        return self.title


class AboutFeatureCard(Orderable):
    ICON_CHOICES = [
        ("book", "Resources"),
        ("video", "Webinars"),
        ("users", "Expert directory"),
        ("message-square", "Impact stories"),
        ("graduation-cap", "Trainings"),
        ("search", "Search / discovery"),
        ("layers", "Collections"),
        ("sparkles", "Featured content"),
    ]

    page = ParentalKey(
        "portal.AboutPage",
        on_delete=models.CASCADE,
        related_name="about_features",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default="book")

    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional internal link for this feature card.",
    )
    link_url = models.URLField(blank=True, help_text="Optional external URL.")
    link_label = models.CharField(max_length=50, blank=True, default="Explore")

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
        FieldPanel("icon"),
        FieldPanel("link_label"),
        FieldPanel("link_page"),
        FieldPanel("link_url"),
    ]

    @property
    def href(self):
        if self.link_page:
            return self.link_page.url
        return self.link_url or ""

    def __str__(self):
        return self.title


class AboutWorkflowStep(Orderable):
    page = ParentalKey(
        "portal.AboutPage",
        on_delete=models.CASCADE,
        related_name="about_workflow_steps",
    )
    step_title = models.CharField(max_length=140)
    step_text = models.TextField(blank=True)

    panels = [
        FieldPanel("step_title"),
        FieldPanel("step_text"),
    ]

    def __str__(self):
        return self.step_title


class AboutPrinciple(Orderable):
    page = ParentalKey(
        "portal.AboutPage",
        on_delete=models.CASCADE,
        related_name="about_principles",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
    ]

    def __str__(self):
        return self.title
    
# ============================================================
#  CONTACT
# ============================================================

class ContactSubmission(models.Model):
    """
    Stores contact form submissions for review in Django admin.
    """
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        SPAM = "spam", "Spam"

    page = models.ForeignKey(
        "ContactPage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions",
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    organization = models.CharField(max_length=160, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.subject}"


class ContactPage(Page, index.Indexed):
    template = "portal/contact_page.html"
    max_count = 1

    # Hero / intro
    hero_kicker = models.CharField(
        max_length=80,
        default="Contact",
        help_text="Small label above the page title",
    )
    hero_title = models.CharField(
        max_length=220,
        default="Get in touch with the SCACAF e-Hub team",
    )
    hero_intro = RichTextField(
        blank=True,
        help_text="Short intro text shown below the title",
    )

    # Contact details card
    office_title = models.CharField(
        max_length=120,
        default="Contact information",
    )
    office_intro = RichTextField(
        blank=True,
        help_text="Optional short text above contact details",
    )
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=60, blank=True)
    office_address = RichTextField(blank=True)
    office_hours = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Monday–Friday, 8:00 AM – 5:00 PM (EAT)",
    )
    map_embed_url = models.URLField(
        blank=True,
        help_text="Optional Google Maps embed URL",
    )

    # Form card
    form_title = models.CharField(
        max_length=120,
        default="Send us a message",
    )
    form_intro = RichTextField(
        blank=True,
        help_text="Optional text above the form",
    )
    submit_button_text = models.CharField(
        max_length=60,
        default="Send message",
    )
    privacy_note = models.CharField(
        max_length=255,
        blank=True,
        default="We’ll use your details only to respond to your message.",
    )

    # Success state
    success_title = models.CharField(
        max_length=120,
        default="Message sent",
    )
    success_message = RichTextField(
        blank=True,
        default="<p>Thank you for contacting us. We’ll get back to you as soon as possible.</p>",
    )

    # Notification settings
    notification_emails = models.TextField(
        blank=True,
        help_text="Comma-separated emails to notify (e.g. hub@org.org, support@org.org)",
    )
    send_auto_reply = models.BooleanField(
        default=True,
        help_text="Send a confirmation email to the person who submitted the form",
    )
    auto_reply_subject = models.CharField(
        max_length=200,
        blank=True,
        default="We received your message",
    )
    auto_reply_body = models.TextField(
        blank=True,
        default=(
            "Hello {name},\n\n"
            "Thank you for contacting the SCACAF e-Hub team. We have received your message "
            "and will respond as soon as possible.\n\n"
            "Best regards,\n"
            "SCACAF e-Hub Team"
        ),
        help_text="You can use {name} in the message.",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_kicker"),
                FieldPanel("hero_title"),
                FieldPanel("hero_intro"),
            ],
            heading="Hero",
        ),
        MultiFieldPanel(
            [
                FieldPanel("office_title"),
                FieldPanel("office_intro"),
                FieldPanel("contact_email"),
                FieldPanel("contact_phone"),
                FieldPanel("office_address"),
                FieldPanel("office_hours"),
                FieldPanel("map_embed_url"),
            ],
            heading="Contact details",
        ),
        MultiFieldPanel(
            [
                FieldPanel("form_title"),
                FieldPanel("form_intro"),
                FieldPanel("submit_button_text"),
                FieldPanel("privacy_note"),
            ],
            heading="Contact form",
        ),
        MultiFieldPanel(
            [
                FieldPanel("success_title"),
                FieldPanel("success_message"),
            ],
            heading="Success message",
        ),
        MultiFieldPanel(
            [
                FieldPanel("notification_emails"),
                FieldPanel("send_auto_reply"),
                FieldPanel("auto_reply_subject"),
                FieldPanel("auto_reply_body"),
            ],
            heading="Email notifications",
        ),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("hero_title", partial_match=True, boost=3.0),
        index.SearchField("hero_intro"),
        index.SearchField("office_intro"),
        index.SearchField("office_address"),
    ]

    parent_page_types = ["portal.HomePage"]
    subpage_types = []
    max_count = 1

    def _notification_recipient_list(self):
        return [
            e.strip()
            for e in (self.notification_emails or "").split(",")
            if e.strip()
        ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Lazy import to avoid circular imports
        from .forms import ContactUsForm

        context.setdefault("form", ContactUsForm())
        context["sent"] = request.GET.get("sent") == "1"
        return context

    def serve(self, request, *args, **kwargs):
        from .forms import ContactUsForm  # lazy import

        if request.method == "POST":
            form = ContactUsForm(request.POST)

            if form.is_valid():
                # Honeypot (spam trap)
                if form.cleaned_data.get("website"):
                    return redirect(f"{request.path}?sent=1")

                submission = ContactSubmission.objects.create(
                    page=self,
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    organization=form.cleaned_data.get("organization", ""),
                    subject=form.cleaned_data["subject"],
                    message=form.cleaned_data["message"],
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
                )

                # Notify admins/team
                recipients = self._notification_recipient_list()
                if recipients:
                    try:
                        admin_subject = f"[SCACAF e-Hub Contact] {submission.subject}"
                        admin_body = (
                            f"New contact form submission\n\n"
                            f"Name: {submission.name}\n"
                            f"Email: {submission.email}\n"
                            f"Organization: {submission.organization or '-'}\n"
                            f"Subject: {submission.subject}\n\n"
                            f"Message:\n{submission.message}\n\n"
                            f"Submitted at: {submission.created_at}\n"
                            f"IP: {submission.ip_address or '-'}\n"
                        )
                        send_mail(
                            subject=admin_subject,
                            message=admin_body,
                            from_email=None,  # uses DEFAULT_FROM_EMAIL
                            recipient_list=recipients,
                            fail_silently=True,
                        )
                    except Exception:
                        pass

                # Auto reply to sender
                if self.send_auto_reply and submission.email:
                    try:
                        reply_subject = self.auto_reply_subject or "We received your message"
                        reply_body = (self.auto_reply_body or "").format(name=submission.name)
                        send_mail(
                            subject=reply_subject,
                            message=reply_body,
                            from_email=None,
                            recipient_list=[submission.email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass

                messages.success(request, "Your message has been sent successfully.")
                return redirect(f"{request.path}?sent=1")

            # Form errors -> render same page with errors
            context = self.get_context(request, *args, **kwargs)
            context["form"] = form
            context["sent"] = False
            return render(request, self.template, context)

        return super().serve(request, *args, **kwargs)

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
