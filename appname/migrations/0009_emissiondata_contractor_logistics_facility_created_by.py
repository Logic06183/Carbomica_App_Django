from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appname', '0008_add_facility_country_type_intervention_sdg'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='emissiondata',
            name='contractor_logistics',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text='Scope 3 — km travelled by contracted vehicles (supply deliveries, waste collection, etc.)',
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0.0)],
            ),
        ),
        migrations.AddField(
            model_name='facility',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who registered this facility (set automatically on login).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='facilities',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
