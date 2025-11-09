#!/usr/bin/env bash

# หยุดสคริปต์ทันทีถ้ามีคำสั่งไหนล้มเหลว
set -o errexit

# 1. ติดตั้ง Dependencies
pip install -r requirements.txt

# 2. รวบรวม Static Files
python manage.py collectstatic --noinput

# 3. รัน Database Migrations
python manage.py migrate
# 4. สร้าง Superuser 
python manage.py createsuperuser --username admin --email "cn331@email.com" --noinput || true