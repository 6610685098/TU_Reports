from django import forms
from .models import Ticket, Category

class TicketForm(forms.ModelForm):
    """Form สำหรับสร้าง Ticket"""
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'urgency_level', 'address_description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500',
                'placeholder': 'หัวข้อปัญหา เช่น หลอดไฟเสีย'
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500',
                'rows': 4,
                'placeholder': 'อธิบายรายละเอียดปัญหา...'
            }),
            'category': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500'
            }),
            'urgency_level': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500'
            }),
            'address_description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500',
                'rows': 2,
                'placeholder': 'อาคาร ชั้น ห้อง'
            }),
        }
