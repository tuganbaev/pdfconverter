from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Document, PremiumFeature, ConversionPricing, Transaction


class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'balance', 'free_conversions', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Balance Information', {'fields': ('balance', 'free_conversions')}),
    )


class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'document_type', 'status', 'created_at', 'file_size']
    list_filter = ['status', 'document_type', 'created_at', 'is_premium']
    search_fields = ['user__username', 'user__email', 'original_file']
    readonly_fields = ['id', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'


class PremiumFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_use', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['order']


class ConversionPricingAdmin(admin.ModelAdmin):
    list_display = ['operation_type', 'pricing_type', 'base_price', 'price_per_page', 'minimum_charge', 'max_price_per_file', 'is_free_operation', 'is_active']
    list_filter = ['pricing_type', 'is_free_operation', 'is_active']
    search_fields = ['operation_type', 'description']
    list_editable = ['pricing_type', 'base_price', 'price_per_page', 'minimum_charge', 'is_active']
    ordering = ['operation_type']
    
    fieldsets = (
        ('Operation Info', {
            'fields': ('operation_type', 'description', 'is_active')
        }),
        ('Pricing Structure', {
            'fields': ('pricing_type', 'base_price', 'price_per_page', 'free_pages', 'minimum_charge', 'max_price_per_file')
        }),
        ('Free Usage', {
            'fields': ('is_free_operation', 'free_limit')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        # Make operation_type readonly when editing existing objects
        if obj:  # editing an existing object
            return ['operation_type']
        return []


class TransactionAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'transaction_type', 'operation_type', 'formatted_amount', 'payment_method', 'is_successful']
    list_filter = ['transaction_type', 'operation_type', 'payment_method', 'is_successful', 'created_at']
    search_fields = ['user__username', 'user__email', 'description', 'document__original_file']
    readonly_fields = ['id', 'created_at', 'balance_before', 'balance_after', 'free_conversions_before', 'free_conversions_after']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('id', 'user', 'document', 'transaction_type', 'operation_type')
        }),
        ('Payment Details', {
            'fields': ('amount', 'payment_method', 'description')
        }),
        ('Balance Tracking', {
            'fields': ('balance_before', 'balance_after', 'free_conversions_before', 'free_conversions_after')
        }),
        ('Status & Metadata', {
            'fields': ('is_successful', 'error_message', 'ip_address', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'document')
    
    def formatted_amount(self, obj):
        return obj.formatted_amount
    formatted_amount.short_description = 'Amount'
    formatted_amount.admin_order_field = 'amount'


admin.site.register(User, UserAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(PremiumFeature, PremiumFeatureAdmin)
admin.site.register(ConversionPricing, ConversionPricingAdmin)
admin.site.register(Transaction, TransactionAdmin)

admin.site.site_header = 'PDF Converter Pro Admin'
admin.site.site_title = 'PDF Converter Pro'
admin.site.index_title = 'Welcome to PDF Converter Pro Administration'