from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0022_profile_role_moderator'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlacklistWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('word', models.CharField(help_text='Слово или фраза, которая будет фильтроваться', max_length=100, unique=True, verbose_name='Запрещённое слово')),
                ('replacement', models.CharField(default='****', help_text='На что заменять слово (по умолчанию: ****)', max_length=50, verbose_name='Замена')),
                ('is_active', models.BooleanField(default=True, help_text='Если снять галочку, слово не будет фильтроваться', verbose_name='Активно')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')),
                ('case_sensitive', models.BooleanField(default=False, help_text="Если включено, 'Bad' и 'bad' — разные слова", verbose_name='Учитывать регистр')),
            ],
            options={
                'verbose_name': 'Слово блэк-листа',
                'verbose_name_plural': 'Words black list',
                'ordering': ['word'],
            },
        ),
    ]
