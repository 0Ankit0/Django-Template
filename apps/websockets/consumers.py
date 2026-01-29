import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Works alongside REST API for bidirectional communication.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope.get("user")

        if self.user and self.user.is_authenticated:
            # Create a unique room name for this user
            self.room_name = f"user_{self.user.id}"
            self.room_group_name = f"notifications_{self.room_name}"

            # Join room group
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)

            await self.accept()

            # Send connection success message
            await self.send(
                text_data=json.dumps({"type": "connection_established", "message": "Connected to notification service"})
            )
        else:
            # Reject connection if user is not authenticated
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, "room_group_name"):
            # Leave room group
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages received from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                # Respond to ping with pong
                await self.send(text_data=json.dumps({"type": "pong", "timestamp": data.get("timestamp")}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON"}))

    async def notification_message(self, event):
        """
        Handle notification messages sent to the group.
        Called when a notification is sent via channel layer.
        """
        await self.send(text_data=json.dumps({"type": "notification", "data": event["data"]}))

    async def order_update(self, event):
        """Handle order update notifications"""
        await self.send(text_data=json.dumps({"type": "order_update", "data": event["data"]}))

    async def payment_update(self, event):
        """Handle payment update notifications"""
        await self.send(text_data=json.dumps({"type": "payment_update", "data": event["data"]}))


class TenantConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for tenant-specific real-time updates.
    Useful for multi-tenant applications.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope.get("user")
        self.tenant_id = self.scope["url_route"]["kwargs"].get("tenant_id")

        if self.user and self.user.is_authenticated and self.tenant_id:
            # Verify user has access to this tenant
            has_access = await self.verify_tenant_access()

            if has_access:
                self.room_group_name = f"tenant_{self.tenant_id}"

                # Join tenant room group
                await self.channel_layer.group_add(self.room_group_name, self.channel_name)

                await self.accept()

                await self.send(text_data=json.dumps({"type": "connection_established", "tenant_id": self.tenant_id}))
            else:
                await self.close()
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages received from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong", "timestamp": data.get("timestamp")}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON"}))

    async def tenant_update(self, event):
        """Handle tenant update notifications"""
        await self.send(text_data=json.dumps({"type": "tenant_update", "data": event["data"]}))

    @database_sync_to_async
    def verify_tenant_access(self):
        """Verify if user has access to the tenant"""
        from multitenancy.models import TenantMembership

        try:
            return TenantMembership.objects.filter(user=self.user, tenant_id=self.tenant_id, is_accepted=True).exists()
        except Exception:
            return False
