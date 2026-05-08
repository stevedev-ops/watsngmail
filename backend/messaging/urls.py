from django.urls import path
from . import views

urlpatterns = [
    path('contacts/', views.ContactListView.as_view(), name='contact-list'),
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('messages/mark_read/', views.MarkAsReadView.as_view(), name='mark-read'),
    path('messages/', views.MessageListView.as_view(), name='message-list'),
    path('messages/toggle_star/', views.ToggleStarView.as_view(), name='toggle-star'),
    path('messages/send/', views.SendMessageView.as_view(), name='send-message'),
    path('upload/', views.UploadView.as_view(), name='file-upload'),
    path('webhooks/twilio/', views.TwilioWebhookView.as_view(), name='twilio-webhook'),
    path('webhooks/gmail/', views.GmailWebhookView.as_view(), name='gmail-webhook'),
    path('gmail/auth/', views.GmailAuthView.as_view(), name='gmail-auth'),
    path('gmail/callback/', views.GmailCallbackView.as_view(), name='gmail-callback'),
]
