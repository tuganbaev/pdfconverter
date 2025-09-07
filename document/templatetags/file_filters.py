from django import template
import os

register = template.Library()

@register.filter
def filename_only(value):
    """Extract just the filename from a full path"""
    if not value:
        return ''
    # Get the base name (removes path)
    return os.path.basename(str(value))

@register.filter
def truncate_filename(value, max_length=30):
    """
    Truncate filename while preserving the extension
    Example: "very_long_document_name_here.docx" -> "very_long_docum...here.docx"
    """
    if not value:
        return ''
    
    filename = os.path.basename(str(value))
    
    if len(filename) <= max_length:
        return filename
    
    # Split name and extension
    name, ext = os.path.splitext(filename)
    
    # Calculate how much we can show
    # Reserve space for extension and ellipsis (3 chars)
    available = max_length - len(ext) - 3
    
    if available <= 0:
        # If extension is too long, just truncate the whole thing
        return filename[:max_length-3] + '...'
    
    # Show start and end of filename
    if available > 6:  # Show both start and end
        start_chars = (available * 2) // 3
        end_chars = available - start_chars
        return f"{name[:start_chars]}...{name[-end_chars:]}{ext}"
    else:  # Just show start
        return f"{name[:available]}...{ext}"

@register.filter
def smart_truncate(value, max_length=25):
    """
    Smart truncate that keeps the extension visible
    Example: "very_long_document_name.docx" -> "very_long_doc....docx"
    """
    if not value:
        return ''
    
    filename = os.path.basename(str(value))
    
    if len(filename) <= max_length:
        return filename
    
    # Split name and extension
    name, ext = os.path.splitext(filename)
    
    # Reserve space for extension and ellipsis
    max_name_length = max_length - len(ext) - 3
    
    if max_name_length <= 0:
        return filename[:max_length-3] + '...'
    
    return f"{name[:max_name_length]}...{ext}"