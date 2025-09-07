from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class User(AbstractUser):
    """Custom user model with balance tracking"""
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_conversions = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def can_convert(self):
        """Check if user can perform conversion"""
        return self.free_conversions > 0 or self.balance > 0
    
    def use_conversion(self, operation_type='docx_to_pdf', request=None, document=None, page_count=1):
        """Deduct conversion cost from user account and record transaction"""
        from .models import ConversionPricing, Transaction
        
        # Get pricing info
        try:
            pricing = ConversionPricing.objects.get(operation_type=operation_type)
        except ConversionPricing.DoesNotExist:
            pricing = ConversionPricing.objects.create(
                operation_type=operation_type,
                base_price=0.50,
                price_per_page=0.10,
                pricing_type='file_plus_pages',
                minimum_charge=0.10,
                description=f'{operation_type.upper()} conversion'
            )
        
        # Store current state
        balance_before = self.balance
        free_conversions_before = self.free_conversions
        
        # Calculate actual cost based on page count
        calculated_cost = pricing.calculate_cost(page_count)
        
        # Determine payment method and cost
        if self.free_conversions > 0:
            # Use free conversion
            self.free_conversions -= 1
            payment_method = 'free_conversion'
            amount = 0.00
            success = True
        elif self.balance >= calculated_cost:
            # Use balance
            self.balance -= calculated_cost
            payment_method = 'balance'
            amount = calculated_cost
            success = True
        else:
            # Insufficient funds
            success = False
            payment_method = 'balance'
            amount = calculated_cost
        
        if success:
            self.save()
        
        # Record transaction
        transaction = Transaction.objects.create(
            user=self,
            document=document,
            transaction_type='conversion',
            operation_type=operation_type,
            amount=amount,
            payment_method=payment_method,
            balance_before=balance_before,
            balance_after=self.balance,
            free_conversions_before=free_conversions_before,
            free_conversions_after=self.free_conversions,
            description=f'{pricing.get_operation_type_display()} conversion',
            is_successful=success,
            ip_address=request.META.get('REMOTE_ADDR') if request else None
        )
        
        return success, transaction


class Document(models.Model):
    """Document model for file uploads and conversions"""
    CONVERSION_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    DOCUMENT_TYPES = [
        ('docx', 'DOCX to PDF'),
        ('xlsx', 'Excel to PDF'),
        ('pptx', 'PowerPoint to PDF'),
        ('image', 'Image to PDF'),
        ('merge', 'Merge PDFs'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    original_file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    converted_file = models.FileField(upload_to='converted/%Y/%m/%d/', null=True, blank=True)
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES)
    status = models.CharField(max_length=20, choices=CONVERSION_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    file_size = models.IntegerField(default=0)  # in bytes
    is_premium = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.original_file.name}"


class PremiumFeature(models.Model):
    """Track premium features for display"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # Font Awesome class
    price_per_use = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name


class ConversionPricing(models.Model):
    """Pricing for different conversion operations"""
    OPERATION_CHOICES = [
        ('docx_to_pdf', 'DOCX to PDF'),
        ('pdf_to_docx', 'PDF to DOCX'),
        ('xlsx', 'Excel to PDF'),
        ('pptx', 'PowerPoint to PDF'),
        ('image', 'Image to PDF'),
        ('merge', 'Merge PDFs'),
        ('compress', 'Compress PDF'),
        ('split', 'Split PDF'),
        ('rotate', 'Rotate PDF'),
        ('watermark', 'Add Watermark'),
        ('encrypt', 'Encrypt PDF'),
        ('extract', 'Extract Pages'),
        ('ocr', 'OCR Recognition'),
    ]
    
    PRICING_TYPE_CHOICES = [
        ('fixed', 'Fixed Price per File'),
        ('per_page', 'Per Page'),
        ('file_plus_pages', 'Base Price + Per Page'),
    ]
    
    operation_type = models.CharField(max_length=20, choices=OPERATION_CHOICES, unique=True)
    
    # Basic pricing
    base_price = models.DecimalField(max_digits=5, decimal_places=2, default=0.10, help_text="Base price per file")
    pricing_type = models.CharField(max_length=20, choices=PRICING_TYPE_CHOICES, default='fixed')
    
    # Page-based pricing
    price_per_page = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Additional cost per page")
    free_pages = models.IntegerField(default=0, help_text="Number of pages included in base price")
    max_price_per_file = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Maximum price cap per file (0 = no cap)")
    
    # Free usage
    is_free_operation = models.BooleanField(default=False)
    free_limit = models.IntegerField(default=0, help_text="Number of free conversions for new users")
    
    # Metadata
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    minimum_charge = models.DecimalField(max_digits=5, decimal_places=2, default=0.10, help_text="Minimum charge per operation")
    
    class Meta:
        ordering = ['operation_type']
        verbose_name = 'Conversion Pricing'
        verbose_name_plural = 'Conversion Pricing'
    
    def calculate_cost(self, page_count=1):
        """Calculate cost based on pricing model and page count"""
        if self.pricing_type == 'fixed':
            cost = self.base_price
        elif self.pricing_type == 'per_page':
            cost = self.price_per_page * page_count
        elif self.pricing_type == 'file_plus_pages':
            # Base price + additional pages beyond free_pages
            additional_pages = max(0, page_count - self.free_pages)
            cost = self.base_price + (additional_pages * self.price_per_page)
        else:
            cost = self.base_price
        
        # Apply minimum charge
        cost = max(cost, self.minimum_charge)
        
        # Apply maximum price cap if set
        if self.max_price_per_file > 0:
            cost = min(cost, self.max_price_per_file)
        
        return cost
    
    def get_pricing_description(self, page_count=1):
        """Get human-readable pricing description"""
        cost = self.calculate_cost(page_count)
        
        if self.pricing_type == 'fixed':
            return f"€{cost} per file"
        elif self.pricing_type == 'per_page':
            return f"€{self.price_per_page} per page (€{cost} for {page_count} pages)"
        elif self.pricing_type == 'file_plus_pages':
            if page_count <= self.free_pages:
                return f"€{cost} (base price for up to {self.free_pages} pages)"
            else:
                additional = page_count - self.free_pages
                return f"€{cost} (€{self.base_price} base + €{self.price_per_page} × {additional} additional pages)"
        
        return f"€{cost}"

    def __str__(self):
        if self.is_free_operation:
            return f"{self.get_operation_type_display()} - Free (limit: {self.free_limit})"
        
        if self.pricing_type == 'fixed':
            return f"{self.get_operation_type_display()} - €{self.base_price}/file"
        elif self.pricing_type == 'per_page':
            return f"{self.get_operation_type_display()} - €{self.price_per_page}/page"
        elif self.pricing_type == 'file_plus_pages':
            return f"{self.get_operation_type_display()} - €{self.base_price} + €{self.price_per_page}/page"
        
        return f"{self.get_operation_type_display()} - €{self.base_price}"


class Transaction(models.Model):
    """Track user spending and conversion transactions"""
    TRANSACTION_TYPES = [
        ('conversion', 'Conversion'),
        ('balance_add', 'Balance Added'),
        ('refund', 'Refund'),
    ]
    
    PAYMENT_METHODS = [
        ('free_conversion', 'Free Conversion'),
        ('balance', 'Balance Deduction'),
        ('credit_card', 'Credit Card'),
        ('paypal', 'PayPal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    operation_type = models.CharField(max_length=20, choices=ConversionPricing.OPERATION_CHOICES, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Amount in EUR")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Balance tracking
    balance_before = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_conversions_before = models.IntegerField(default=0)
    free_conversions_after = models.IntegerField(default=0)
    
    # Metadata
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Status and processing
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        if self.transaction_type == 'conversion':
            if self.amount > 0:
                return f"{self.user.username} - {self.get_operation_type_display()} - €{self.amount}"
            else:
                return f"{self.user.username} - {self.get_operation_type_display()} - Free"
        return f"{self.user.username} - {self.get_transaction_type_display()} - €{self.amount}"
    
    @property
    def formatted_amount(self):
        """Format amount with euro symbol"""
        if self.amount == 0:
            return "Free"
        return f"€{self.amount}"