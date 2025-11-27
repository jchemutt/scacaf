from django.db import migrations

def seed(apps, schema_editor):
    Topic = apps.get_model("portal", "Topic")
    Audience = apps.get_model("portal", "Audience")
    Region = apps.get_model("portal", "Region")
    Language = apps.get_model("portal", "Language")

    for t in [
        "Climate finance landscape", "Donor research", "Climate rationale",
        "Theory of Change", "Budget & VfM", "Feasibility & Gender",
        "Stakeholder engagement", "MEL"
    ]:
        Topic.objects.get_or_create(name=t)

    for a in ["Government", "NGO/CSO", "Private sector", "Academia/Research", "Multilateral/Donor"]:
        Audience.objects.get_or_create(name=a)

    african_countries = [
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cabo Verde", "Cameroon", "Central African Republic", "Chad",
        "Comoros", "Congo (Republic)", "Congo (Democratic Republic)",
        "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini",
        "Ethiopia", "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau",
        "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi",
        "Mali", "Mauritania", "Mauritius", "Morocco", "Mozambique",
        "Namibia", "Niger", "Nigeria", "Rwanda", "Sao Tome and Principe",
        "Senegal", "Seychelles", "Sierra Leone", "Somalia", "South Africa",
        "South Sudan", "Sudan", "Tanzania", "Togo", "Tunisia", "Uganda",
        "Zambia", "Zimbabwe",
        # Regions (keep these too)
        "IGAD Region", "East Africa", "Africa"
    ]

    for country in african_countries:
        Region.objects.get_or_create(name=country)

    for code, name in [("en","English"), ("fr","French"), ("pt","Portuguese")]:
        Language.objects.get_or_create(code=code, name=name)

def unseed(apps, schema_editor):
    # optional: leave no-op to keep data
    pass

class Migration(migrations.Migration):
    dependencies = [("portal", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
