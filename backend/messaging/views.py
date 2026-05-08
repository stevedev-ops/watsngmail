import json
import base64
import os
import logging
import requests as http_requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.db.models import Max, Count, Q, Subquery, OuterRef
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, permissions
from twilio.rest import Client
from .models import Message, Contact
from .serializers import MessageSerializer, ContactSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Google Auth & Email imports
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Path for credentials storage
TOKEN_FILE = str(settings.GMAIL_TOKEN_FILE)

class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        queryset = Message.objects.all()
        contact_id = self.request.query_params.get('contact_identifier')
        channel = self.request.query_params.get('channel')
        if contact_id:
            queryset = queryset.filter(contact_identifier=contact_id)
        if channel:
            queryset = queryset.filter(channel=channel)
        return queryset.order_by('timestamp')

class ConversationListView(APIView):
    def get(self, request):
        conversations = Message.objects.values('contact_identifier', 'channel').annotate(
            last_message=Max('timestamp'),
            unread_count=Count('id', filter=Q(status='delivered', direction='inbound')),
            current_name=Subquery(
                Message.objects.filter(contact_identifier=OuterRef('contact_identifier'), channel=OuterRef('channel')).order_by('-timestamp').values('contact_name')[:1]
            ),
            last_body=Subquery(
                Message.objects.filter(contact_identifier=OuterRef('contact_identifier'), channel=OuterRef('channel')).order_by('-timestamp').values('body')[:1]
            ),
            last_subject=Subquery(
                Message.objects.filter(contact_identifier=OuterRef('contact_identifier'), channel='email').order_by('-timestamp').values('subject')[:1]
            ),
            last_media=Subquery(
                Message.objects.filter(contact_identifier=OuterRef('contact_identifier')).order_by('-timestamp').values('media_url')[:1]
            )
        ).order_by('-last_message')
        
        data = []
        for c in conversations:
            data.append({
                'contact_identifier': c['contact_identifier'],
                'contact_name': c['current_name'] or c['contact_identifier'],
                'channel': c['channel'],
                'timestamp': c['last_message'],
                'body': c['last_body'],
                'subject': c['last_subject'],
                'media_url': c['last_media'],
                'unread_count': c['unread_count']
            })
        return Response(data)

class SendMessageView(APIView):
    def post(self, request):
        channel = request.data.get('channel')
        to_input = request.data.get('to', '')
        body = request.data.get('body')
        subject = request.data.get('subject', '')
        cc = request.data.get('cc', '')
        media_url = request.data.get('media_url')
        reply_to_id = request.data.get('reply_to')

        provider = request.data.get('provider', 'twilio')
        recipients = [r.strip() for r in to_input.split(',')] if isinstance(to_input, str) else [to_input]

        responses = []
        for to in recipients:
            if channel == 'whatsapp':
                res = self.send_whatsapp(to, body, media_url=media_url, reply_to_id=reply_to_id, provider=provider)
            elif channel == 'email':
                res = self.send_email(to, subject, body, cc=cc, media_url=media_url, reply_to_id=reply_to_id)
            else:
                return Response({'error': f"Unknown channel: {channel}"}, status=400)
            responses.append(res.data if hasattr(res, 'data') else res)

        return Response(responses[0] if len(responses) == 1 else responses)

    def send_whatsapp(self, to, body, media_url=None, reply_to_id=None, provider='twilio'):
        if provider == 'cloud':
            return self._send_via_cloud(to, body, media_url=media_url, reply_to_id=reply_to_id)
        return self._send_via_twilio(to, body, media_url=media_url, reply_to_id=reply_to_id)

    def _send_via_twilio(self, to, body, media_url=None, reply_to_id=None):
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message_args = {
                'from_': settings.TWILIO_WHATSAPP_NUMBER,
                'to': f'whatsapp:{to}',
                'body': body or ''
            }
            if media_url:
                message_args['media_url'] = [media_url]

            message = client.messages.create(**message_args)

            msg_obj = Message.objects.create(
                channel='whatsapp',
                direction='outbound',
                contact_identifier=to,
                body=body,
                media_url=media_url,
                status='sent',
                message_id=message.sid,
                reply_to_id=reply_to_id
            )
            Contact.objects.get_or_create(identifier=to, defaults={'name': to, 'channel': 'whatsapp'})
            self.notify_clients(msg_obj)
            return Response(MessageSerializer(msg_obj).data)
        except Exception as e:
            logger.error(f"Twilio Error: {str(e)}")
            return Response({'error': f"Twilio Error: {str(e)}"}, status=500)

    def _send_via_cloud(self, to, body, media_url=None, reply_to_id=None):
        try:
            resp = http_requests.post(
                f"https://graph.facebook.com/v19.0/{settings.WA_PHONE_NUMBER_ID}/messages",
                headers={
                    "Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": body or ''}
                }
            )
            if resp.status_code != 200:
                return Response({'error': resp.text}, status=resp.status_code)

            msg_obj = Message.objects.create(
                channel='whatsapp',
                direction='outbound',
                contact_identifier=to,
                body=body,
                media_url=media_url,
                status='sent',
                reply_to_id=reply_to_id
            )
            Contact.objects.get_or_create(identifier=to, defaults={'name': to, 'channel': 'whatsapp'})
            self.notify_clients(msg_obj)
            return Response(MessageSerializer(msg_obj).data)
        except Exception as e:
            logger.error(f"WhatsApp Cloud Error: {str(e)}")
            return Response({'error': f"WhatsApp Cloud Error: {str(e)}"}, status=500)

    def get_gmail_service(self):
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, ['https://www.googleapis.com/auth/gmail.modify'])
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, 'w') as f:
                    f.write(creds.to_json())
            return build('gmail', 'v1', credentials=creds)
        return None

    def send_email(self, to, subject, body, cc=None, media_url=None, reply_to_id=None):
        try:
            service = self.get_gmail_service()
            if not service:
                # FIX: Fail if no Gmail auth
                return Response({'error': 'Gmail not authenticated. Please login.'}, status=401)

            message = MIMEMultipart()
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc
            message.attach(MIMEText(body or ''))

            if media_url:
                # Actual file handling logic would go here
                pass

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            
            msg_obj = Message.objects.create(
                channel='email',
                direction='outbound',
                contact_identifier=to,
                subject=subject,
                body=body,
                cc=cc,
                media_url=media_url,
                status='sent',
                reply_to_id=reply_to_id
            )
            Contact.objects.get_or_create(identifier=to, defaults={'name': to, 'channel': 'email'})
            self.notify_clients(msg_obj)
            return Response(MessageSerializer(msg_obj).data)
        except Exception as e:
            logger.error(f"Gmail Send Error: {str(e)}")
            return Response({'error': f"Gmail API Error: {str(e)}"}, status=500)

    def notify_clients(self, msg_obj):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "chat_updates",
            {
                "type": "chat_message",
                "message": MessageSerializer(msg_obj).data
            }
        )

class ToggleStarView(APIView):
    def post(self, request):
        msg_id = request.data.get('message_id')
        try:
            msg = Message.objects.get(id=msg_id)
            msg.is_starred = not msg.is_starred
            msg.save()
            return Response({'is_starred': msg.is_starred})
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

class MarkAsReadView(APIView):
    def post(self, request):
        identifier = request.data.get('contact_identifier')
        Message.objects.filter(contact_identifier=identifier, direction='inbound', status='delivered').update(status='read')
        return Response({'status': 'ok'})

class UploadView(APIView):
    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file'}, status=400)
        path = default_storage.save(f'uploads/{file_obj.name}', file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + path)
        return Response({'url': url})

@method_decorator(csrf_exempt, name='dispatch')
class GmailWebhookView(APIView):
    permission_classes = [permissions.AllowAny] # External push from Google
    def post(self, request):
        try:
            envelope = request.data
            if 'message' in envelope:
                data = json.loads(base64.urlsafe_b64decode(envelope['message']['data'] + '=='))
                email_address = data.get('emailAddress')
                history_id = data.get('historyId')
                
                service = SendMessageView().get_gmail_service()
                if service:
                    # PROPER FIX: Use historyId to fetch only what changed
                    if history_id:
                        history = service.users().history().list(userId='me', startHistoryId=history_id).execute()
                        messages_to_fetch = []
                        if 'history' in history:
                            for h in history['history']:
                                if 'messagesAdded' in h:
                                    for m in h['messagesAdded']:
                                        messages_to_fetch.append(m['message']['id'])
                        
                        # Fallback if history is too old or empty
                        if not messages_to_fetch:
                            results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
                            messages_to_fetch = [m['id'] for m in results.get('messages', [])]
                    else:
                        results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
                        messages_to_fetch = [m['id'] for m in results.get('messages', [])]

                    for msg_id in messages_to_fetch:
                        if not Message.objects.filter(message_id=msg_id).exists():
                            g_msg = service.users().messages().get(userId='me', id=msg_id).execute()
                            headers = g_msg['payload']['headers']
                            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(No Subject)')
                            from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), email_address)
                            body = g_msg['snippet']
                            
                            msg = Message.objects.create(
                                channel='email',
                                direction='inbound',
                                contact_identifier=from_email,
                                subject=subject,
                                body=body,
                                status='delivered',
                                message_id=msg_id
                            )
                            Contact.objects.get_or_create(identifier=from_email, defaults={'name': from_email, 'channel': 'email'})
                            channel_layer = get_channel_layer()
                            async_to_sync(channel_layer.group_send)("chat_updates", {"type": "chat_message", "message": MessageSerializer(msg).data})
            return Response({'status': 'processed'})
        except Exception as e:
            logger.error(f"Gmail Webhook Error: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class TwilioWebhookView(APIView):
    permission_classes = [permissions.AllowAny] # External push from Twilio
    def post(self, request):
        from_number = request.data.get('From', '').replace('whatsapp:', '')
        profile_name = request.data.get('ProfileName', from_number)
        message_sid = request.data.get('MessageSid', '')
        body = request.data.get('Body', '')
        media_url = request.data.get('MediaUrl0', None)
        
        if not Message.objects.filter(message_id=message_sid).exists():
            msg = Message.objects.create(
                channel='whatsapp',
                direction='inbound',
                contact_identifier=from_number,
                contact_name=profile_name,
                body=body,
                media_url=media_url,
                status='delivered',
                message_id=message_sid
            )
            Contact.objects.update_or_create(identifier=from_number, defaults={'name': profile_name, 'channel': 'whatsapp'})
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)("chat_updates", {"type": "chat_message", "message": MessageSerializer(msg).data})
        
        return Response({'status': 'received'})

class ContactListView(generics.ListAPIView):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

class GmailAuthView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        client_config = {
            "web": {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/gmail.modify'],
            redirect_uri=settings.GMAIL_REDIRECT_URI
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        return Response({"auth_url": auth_url})

class GmailCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        client_config = {
            "web": {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/gmail.modify'],
            redirect_uri=settings.GMAIL_REDIRECT_URI
        )
        code = request.GET.get('code')
        if not code:
            return HttpResponse("Authentication cancelled or failed. You can close this tab.", status=400)
        flow.fetch_token(code=code)
        creds = flow.credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        return HttpResponse("Authentication Successful! You can close this tab.")

@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppCloudWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if request.GET.get('hub.verify_token') == settings.WA_VERIFY_TOKEN:
            return HttpResponse(request.GET.get('hub.challenge'))
        return HttpResponse('Forbidden', status=403)

    def post(self, request):
        try:
            entry = request.data.get('entry', [])[0]
            change = entry.get('changes', [])[0]['value']
            for wa_msg in change.get('messages', []):
                from_number = wa_msg['from']
                body = wa_msg.get('text', {}).get('body', '')
                msg_id = wa_msg['id']
                if not Message.objects.filter(message_id=msg_id).exists():
                    msg_obj = Message.objects.create(
                        channel='whatsapp',
                        direction='inbound',
                        contact_identifier=from_number,
                        body=body,
                        status='delivered',
                        message_id=msg_id
                    )
                    Contact.objects.get_or_create(identifier=from_number, defaults={'name': from_number, 'channel': 'whatsapp'})
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)("chat_updates", {"type": "chat_message", "message": MessageSerializer(msg_obj).data})
        except Exception as e:
            logger.error(f"WhatsApp Cloud Webhook Error: {str(e)}")
        return Response({'status': 'ok'})