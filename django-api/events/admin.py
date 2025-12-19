from django.contrib import admin

from events.models import Event, Session, TicketType


class SessionInline(admin.TabularInline):
    model = Session
    extra = 1


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "created_at"]
    search_fields = ["name", "location"]
    inlines = [SessionInline]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["event", "starts_at", "ends_at", "total_capacity"]
    list_filter = ["event"]
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "session", "price", "quantity"]
    list_filter = ["session__event"]
