# portal/templatetags/portal_extras.py
from django import template

register = template.Library()

# Map resource kind → Tailwind badge classes
_BADGES = {
    "video": "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200",
    "pdf": "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200",
    "handbook": "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
    "template": "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-200",
    "tool": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200",
    "link": "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100",
}

@register.filter
def kind_badge(kind: str) -> str:
    """Return CSS classes for resource type badge."""
    if not kind:
        return "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100"
    return _BADGES.get(kind, "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100")
