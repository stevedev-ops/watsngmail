from django.db import models

class Message(models.Model):
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
    ]
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    contact_name = models.CharField(max_length=255, blank=True, null=True)
    contact_identifier = models.CharField(max_length=255)  # Phone number or Email address
    subject = models.CharField(max_length=255, blank=True, null=True)  # For emails
    body = models.TextField(blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)  # WhatsApp media or Email attachment
    attachment_name = models.CharField(max_length=255, blank=True, null=True)
    attachment_type = models.CharField(max_length=50, blank=True, null=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    is_starred = models.BooleanField(default=False)
    cc = models.TextField(blank=True, null=True)
    bcc = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='sent') # sent, delivered, read, failed
    thread_id = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=255, unique=True, blank=True, null=True) # External ID from Twilio/Gmail
    
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.channel} - {self.direction} - {self.contact_identifier}"

class Contact(models.Model):
    name = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, unique=True) # Phone or Email
    channel = models.CharField(max_length=20, choices=[('whatsapp', 'WhatsApp'), ('email', 'Email')])
    
    def __str__(self):
        return f"{self.name} ({self.identifier})"
