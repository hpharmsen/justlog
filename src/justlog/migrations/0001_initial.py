# Generated migration for justlog

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='LogEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('level', models.IntegerField(choices=[(10, 'DEBUG'), (20, 'INFO'), (30, 'WARNING'), (40, 'ERROR'), (50, 'CRITICAL')], db_index=True)),
                ('message', models.TextField()),
                ('extra_args', models.JSONField(blank=True, null=True)),
                ('extra_kwargs', models.JSONField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Log Entry',
                'verbose_name_plural': 'Log Entries',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='logentry',
            index=models.Index(fields=['-timestamp', 'level'], name='justlog_log_timesta_idx'),
        ),
    ]
