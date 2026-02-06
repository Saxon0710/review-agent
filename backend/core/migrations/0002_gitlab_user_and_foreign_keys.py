# Create GitLabUser model and convert user_id fields to foreign keys

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='GitLabUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('gitlab_user_id', models.PositiveIntegerField(db_index=True, unique=True)),
                ('gitlab_username', models.CharField(db_index=True, max_length=255)),
                ('gitlab_email', models.EmailField(blank=True, null=True)),
                ('avatar_url', models.URLField(blank=True, max_length=500, null=True)),
                ('access_token', models.CharField(blank=True, max_length=500, null=True)),
                ('refresh_token', models.CharField(blank=True, max_length=500, null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('last_login_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='gitlab_profile', to='auth.user')),
            ],
            options={
                'db_table': 'gitlab_users',
                'ordering': ['gitlab_username'],
                'indexes': [
                    models.Index(fields=['gitlab_user_id'], name='core_gitlab__gitlab_use_idx'),
                    models.Index(fields=['gitlab_username'], name='core_gitlab__gitlab_us_idx'),
                ],
            },
        ),
        # Convert PullRequest user_id fields to foreign keys
        migrations.RemoveField(
            model_name='pullrequest',
            name='assignee_id',
        ),
        migrations.AddField(
            model_name='pullrequest',
            name='assignee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_mrs', to='core.gitlabuser'),
        ),
        migrations.RemoveField(
            model_name='pullrequest',
            name='author_id',
        ),
        migrations.AddField(
            model_name='pullrequest',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='authored_mrs', to='core.gitlabuser'),
        ),
        # Convert ReviewTask trigger_user_id field to foreign key
        migrations.RemoveField(
            model_name='reviewtask',
            name='trigger_user_id',
        ),
        migrations.AddField(
            model_name='reviewtask',
            name='trigger_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='triggered_tasks', to='core.gitlabuser'),
        ),
        # Convert AuditLog user_id field to foreign key
        migrations.RemoveField(
            model_name='auditlog',
            name='user_id',
        ),
        migrations.AddField(
            model_name='auditlog',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='core.gitlabuser'),
        ),
        # Fix the index that referenced user_id instead of user
        migrations.RemoveIndex(
            model_name='auditlog',
            name='core_audit__user_id_idx',
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', '-created_at'], name='core_audit__user_id_idx'),
        ),
    ]
