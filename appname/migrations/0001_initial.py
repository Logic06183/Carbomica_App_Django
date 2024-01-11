# Generated by Django 5.0.1 on 2024-01-11 11:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EmissionSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code_name", models.CharField(max_length=100)),
                ("display_name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Facility",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code_name", models.CharField(max_length=100)),
                ("display_name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Intervention",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code_name", models.CharField(max_length=100)),
                ("display_name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="EmissionData",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("grid_electricity", models.FloatField()),
                ("grid_gas", models.FloatField()),
                ("bottled_gas", models.FloatField()),
                (
                    "facility",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.facility",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EffectSize",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("recycling_waste_segregation", models.FloatField()),
                ("solar_system_installation", models.FloatField()),
                (
                    "facility",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.facility",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ImplementationCost",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("recycling_waste_segregation", models.FloatField()),
                ("solar_system_installation", models.FloatField()),
                (
                    "facility",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.facility",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FacilityIntervention",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "facility",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.facility",
                    ),
                ),
                (
                    "intervention",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.intervention",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MaintenanceCost",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("recycling_waste_segregation", models.FloatField()),
                ("solar_system_installation", models.FloatField()),
                (
                    "facility",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="appname.facility",
                    ),
                ),
            ],
        ),
    ]
