from django.db import migrations

def forwards(apps, schema_editor):
    Department = apps.get_model('tickets', 'Department')
    for d in Department.objects.all().only('id', 'name'):
        if not d.name:
            d.name = f"Department {d.id}"
            d.save(update_fields=['name'])

def backwards(apps, schema_editor):
    # ไม่ย้อนกลับ (ปล่อยว่าง)
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0002_delete_place_alter_assignmentrule_options_and_more'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
