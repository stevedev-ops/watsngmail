from rest_framework import permissions
from django.conf import settings

class HasAPIKey(permissions.BasePermission):
    """
    Custom permission to only allow requests with a valid X-API-KEY header.
    """
    def has_permission(self, request, view):
        # Webhooks from Twilio/Google might not have the API Key
        # We can bypass check for specific views if needed, but for now we enforce it
        api_key = request.headers.get('X-API-KEY')
        return api_key == settings.API_KEY
