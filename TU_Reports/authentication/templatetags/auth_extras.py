from django import template
from django.urls import reverse

register = template.Library()

@register.simple_tag(takes_context=True)
def post_login_url_for(context):
    """
    ใช้ตัดสินปลายทางลิงก์ 'งานของฉัน' ตามบทบาทผู้ใช้
      - technician  -> technician:job_list
      - อื่น ๆ       -> tickets:my_tickets
    """
    request = context.get("request")
    user = getattr(request, "user", None)

    if user and user.is_authenticated and getattr(user, "role", "") == "technician":
        return reverse("technician:job_list")
    return reverse("tickets:my_tickets")
