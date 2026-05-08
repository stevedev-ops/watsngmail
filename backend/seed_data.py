import os
import sys
import django

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from messaging.models import Message, Contact
from django.utils import timezone

def seed():
    # Clear existing data for a fresh look
    Message.objects.all().delete()
    Contact.objects.all().delete()

    print("Seeding Contacts...")
    # WhatsApp Contacts
    wa_contacts = [
        ("Mama", "+254700000001"),
        ("John Boss", "+254700000002"),
        ("Delivery Guy", "+254700000003"),
        ("Sarah (New Lead)", "+254700000004"),
    ]
    for name, identifier in wa_contacts:
        Contact.objects.create(name=name, identifier=identifier, channel='whatsapp')

    # Gmail Contacts
    email_contacts = [
        ("HR Department", "hr@company.com"),
        ("Client Alpha", "alpha@client.com"),
        ("Support Team", "support@service.com"),
        ("Marketing Hub", "marketing@news.com"),
    ]
    for name, identifier in email_contacts:
        Contact.objects.create(name=name, identifier=identifier, channel='email')

    print("Seeding Initial Messages...")
    # WhatsApp Messages
    Message.objects.create(
        channel='whatsapp', direction='inbound', contact_identifier='+254700000001',
        contact_name='Mama', body='Are you coming home for dinner?', status='delivered'
    )
    Message.objects.create(
        channel='whatsapp', direction='inbound', contact_identifier='+254700000002',
        contact_name='John Boss', body='Send the report by 5 PM.', status='delivered'
    )
    
    # Gmail Messages
    Message.objects.create(
        channel='email', direction='inbound', contact_identifier='hr@company.com',
        subject='Job Interview Update', body='We are pleased to inform you...', status='delivered'
    )
    Message.objects.create(
        channel='email', direction='inbound', contact_identifier='alpha@client.com',
        subject='New Project Proposal', body='Let us discuss the next steps for Alpha project.', status='delivered'
    )

    print("Seeding Complete! Your Two Worlds are now populated.")

if __name__ == "__main__":
    seed()
