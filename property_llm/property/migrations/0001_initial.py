# Generated by Django 5.1.4 on 2024-12-30 06:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Property',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hotel_id', models.CharField(max_length=100, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('summary', models.TextField(blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255, null=True)),
                ('latitude', models.FloatField(blank=True, null=True)),
                ('longitude', models.FloatField(blank=True, null=True)),
                ('price', models.CharField(blank=True, max_length=50, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='PropertyRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.FloatField()),
                ('review', models.TextField()),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='property.property')),
            ],
        ),
        migrations.CreateModel(
            name='Summary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary', models.TextField()),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='summaries', to='property.property')),
            ],
        ),
    ]
