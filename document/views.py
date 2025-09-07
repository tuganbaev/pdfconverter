from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse, JsonResponse
from django.core.files.base import ContentFile
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import models
from .models import Document, User, PremiumFeature, ConversionPricing, Transaction
from .forms import UserRegistrationForm
import io
import os
import tempfile
import json
from pathlib import Path


def home(request):
    """Landing page view"""
    # Get pricing for all operations
    pricing_data = {}
    operation_mapping = {
        'docx': 'docx_to_pdf',
        'xlsx': 'xlsx', 
        'pptx': 'pptx',
        'image': 'image',
        'merge': 'merge',
        'compress': 'compress'
    }
    
    for display_key, operation_type in operation_mapping.items():
        try:
            pricing = ConversionPricing.objects.get(operation_type=operation_type)
            pricing_data[display_key] = pricing
        except ConversionPricing.DoesNotExist:
            # Create default if doesn't exist
            pricing_data[display_key] = None
    
    return render(request, 'home.html', {'pricing': pricing_data})


def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f'Welcome {username}! You have 3 free conversions to start. Add balance for additional conversions.')
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def convert_view(request):
    """Main conversion view for DOCX to PDF"""
    recent_documents = Document.objects.filter(
        user=request.user,
        document_type='docx'
    )[:5]
    
    # Get pricing info for DOCX conversion
    try:
        docx_pricing = ConversionPricing.objects.get(operation_type='docx_to_pdf')
    except ConversionPricing.DoesNotExist:
        # Create default pricing if not exists
        docx_pricing = ConversionPricing.objects.create(
            operation_type='docx_to_pdf',
            base_price=0.50,
            price_per_page=0.10,
            pricing_type='file_plus_pages',
            minimum_charge=0.10,
            is_free_operation=False,
            free_limit=3,
            description='Convert DOCX files to PDF'
        )
    
    if request.method == 'POST':
        if not request.user.can_convert():
            messages.error(request, 'You have no conversions left. Please add balance.')
            return redirect('add_balance')
        
        docx_file = request.FILES.get('docx_file')
        if not docx_file:
            messages.error(request, 'Please select a file to convert.')
            return redirect('convert')
        
        if not docx_file.name.endswith('.docx'):
            messages.error(request, 'Please upload a valid DOCX file.')
            return redirect('convert')
        
        if docx_file.size > 10 * 1024 * 1024:  # 10MB limit
            messages.error(request, 'File size must be less than 10MB.')
            return redirect('convert')
        
        try:
            # Create document record
            document = Document.objects.create(
                user=request.user,
                original_file=docx_file,
                document_type='docx',
                file_size=docx_file.size,
                status='processing'
            )
            
            # Store document ID in session for JS polling
            request.session['current_conversion_id'] = str(document.id)
            
            # Perform conversion in background-like manner
            # (In a real app, this would be a Celery task)
            try:
                pdf_content = convert_docx_to_pdf(document.original_file.path)
                
                if pdf_content:
                    # Save converted file
                    pdf_filename = f"{Path(docx_file.name).stem}.pdf"
                    document.converted_file.save(
                        pdf_filename,
                        ContentFile(pdf_content),
                        save=False
                    )
                    document.status = 'completed'
                    document.completed_at = timezone.now()
                    document.save()
                    
                    # Deduct conversion and record transaction
                    success, transaction = request.user.use_conversion(
                        operation_type='docx_to_pdf',
                        request=request,
                        document=document,
                        page_count=1  # For now, assume 1 page - in real app, extract from DOCX
                    )
                    
                    messages.success(request, 'Document converted successfully!')
                    return redirect('download', document_id=document.id)
                else:
                    document.status = 'failed'
                    document.save()
                    messages.error(request, 'Conversion failed. Please try again.')
            except Exception as conv_error:
                document.status = 'failed'
                document.save()
                messages.error(request, f'Conversion error: {str(conv_error)}')
                
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            if 'document' in locals():
                document.status = 'failed'
                document.save()
    
    # Get current conversion ID from session if exists
    current_conversion_id = request.session.get('current_conversion_id')
    
    return render(request, 'document/convert.html', {
        'recent_documents': recent_documents,
        'current_conversion_id': current_conversion_id,
        'docx_pricing': docx_pricing
    })


@login_required
def check_conversion_status(request, document_id):
    """Check conversion status via AJAX"""
    try:
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        response_data = {
            'status': document.status,
            'created_at': document.created_at.strftime('%b %d, %H:%M'),
            'filename': document.original_file.name.split('/')[-1] if document.original_file else 'Unknown'
        }
        
        if document.status == 'completed' and document.converted_file:
            response_data['download_url'] = f'/download/{document.id}/'
            response_data['user_balance'] = str(request.user.balance)
            response_data['free_conversions'] = request.user.free_conversions
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


def convert_docx_to_pdf(docx_path):
    """Convert DOCX to PDF with proper Cyrillic support"""
    from .utils import convert_docx_to_pdf_with_cyrillic
    
    try:
        # Try the improved Cyrillic conversion first
        pdf_content = convert_docx_to_pdf_with_cyrillic(docx_path)
        if pdf_content:
            return pdf_content
        
        print("Primary conversion failed, trying fallback...")
        return convert_docx_to_pdf_simple(docx_path)
        
    except Exception as e:
        print(f"Conversion error: {e}")
        return convert_docx_to_pdf_simple(docx_path)


def convert_docx_to_pdf_simple(docx_path):
    """Simple fallback conversion method"""
    try:
        from docx import Document as DocxDocument
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.utils import ImageReader
        
        # Read DOCX
        doc = DocxDocument(docx_path)
        
        # Create PDF
        buffer = io.BytesIO()
        pdf = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Add title
        story.append(Paragraph("Converted Document", styles['Title']))
        story.append(Spacer(1, 20))
        
        # Extract text and try to handle encoding
        for para in doc.paragraphs:
            if para.text.strip():
                try:
                    # Try to handle Russian text by transliterating if needed
                    text = para.text.strip()
                    
                    # Basic transliteration for display (fallback)
                    replacements = {
                        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
                        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
                        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'YO',
                        'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
                        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
                        'Ф': 'F', 'Х': 'H', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH',
                        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA'
                    }
                    
                    # Only transliterate if we detect Cyrillic
                    if any(ord(char) >= 1040 and ord(char) <= 1103 for char in text):
                        transliterated = text
                        for cyrillic, latin in replacements.items():
                            transliterated = transliterated.replace(cyrillic, latin)
                        text = f"[RU] {transliterated}"
                    
                    story.append(Paragraph(text, styles['Normal']))
                    story.append(Spacer(1, 12))
                    
                except Exception as e:
                    print(f"Error in simple conversion: {e}")
                    # Last resort: just add placeholder
                    story.append(Paragraph("[Content could not be converted]", styles['Normal']))
                    story.append(Spacer(1, 12))
        
        if len(story) <= 2:  # Only title and spacer
            story.append(Paragraph("Document processed but no readable content found.", styles['Normal']))
        
        # Build PDF
        pdf.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
        
    except Exception as e:
        print(f"Simple conversion error: {e}")
        return None


@login_required
def download_view(request, document_id):
    """Download converted PDF file"""
    document = get_object_or_404(Document, id=document_id, user=request.user)
    
    if document.status != 'completed' or not document.converted_file:
        messages.error(request, 'Document is not ready for download.')
        return redirect('convert')
    
    return FileResponse(
        document.converted_file.open('rb'),
        as_attachment=True,
        filename=os.path.basename(document.converted_file.name)
    )


@login_required
def dashboard_view(request):
    """User dashboard"""
    documents = Document.objects.filter(user=request.user)[:20]
    all_documents = Document.objects.filter(user=request.user)
    transactions = Transaction.objects.filter(user=request.user)[:10]
    
    # Calculate total spending
    total_spent = Transaction.objects.filter(
        user=request.user,
        transaction_type='conversion',
        is_successful=True
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    stats = {
        'total_conversions': all_documents.count(),
        'successful': all_documents.filter(status='completed').count(),
        'failed': all_documents.filter(status='failed').count(),
        'total_spent': total_spent,
    }
    
    return render(request, 'document/dashboard.html', {
        'documents': documents,
        'transactions': transactions,
        'stats': stats
    })


@login_required
def add_balance_view(request):
    """Add balance to user account (placeholder)"""
    if request.method == 'POST':
        # This would integrate with a payment gateway
        from decimal import Decimal
        amount = Decimal(str(request.POST.get('amount', 10)))
        balance_before = request.user.balance
        
        request.user.balance += amount
        request.user.save()
        
        # Record transaction
        Transaction.objects.create(
            user=request.user,
            transaction_type='balance_add',
            amount=amount,
            payment_method='credit_card',  # In real app, this would be dynamic
            balance_before=balance_before,
            balance_after=request.user.balance,
            free_conversions_before=request.user.free_conversions,
            free_conversions_after=request.user.free_conversions,
            description=f'Balance top-up of €{amount}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, f'€{amount} added to your balance!')
        return redirect('convert')
    
    return render(request, 'document/add_balance.html')


@login_required
def transactions_view(request):
    """User transaction history"""
    transactions = Transaction.objects.filter(user=request.user)
    
    # Calculate spending stats
    conversion_stats = Transaction.objects.filter(
        user=request.user,
        transaction_type='conversion',
        is_successful=True
    ).aggregate(
        total_spent=models.Sum('amount'),
        total_conversions=models.Count('id')
    )
    
    balance_stats = Transaction.objects.filter(
        user=request.user,
        transaction_type='balance_add',
        is_successful=True
    ).aggregate(
        total_added=models.Sum('amount')
    )
    
    stats = {
        'total_spent': conversion_stats['total_spent'] or 0,
        'total_conversions': conversion_stats['total_conversions'] or 0,
        'total_added': balance_stats['total_added'] or 0,
        'free_conversions_used': Transaction.objects.filter(
            user=request.user,
            transaction_type='conversion',
            payment_method='free_conversion',
            is_successful=True
        ).count()
    }
    
    return render(request, 'document/transactions.html', {
        'transactions': transactions,
        'stats': stats
    })