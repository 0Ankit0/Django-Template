from django import template
from django.urls import reverse

register = template.Library()

@register.simple_tag(takes_context=True)
def is_active(context, url_name=None, namespace=None, part_match=None):
    """
    Return 'active' if the current URL matches the criteria.
    - url_name: Exact match on url_name (e.g. 'dashboard')
    - namespace: Exact match on namespace (e.g. 'multitenancy')
    - part_match: True if any part of the path matches (simplified check)
    """
    request = context.get('request')
    if not request:
        return ''
    
    resolver_match = request.resolver_match
    if not resolver_match:
        return ''

    if url_name and resolver_match.url_name == url_name:
        return 'active'
        
    if namespace and resolver_match.namespace == namespace:
        return 'active'
        
    if part_match:
        # Check if part_match string is in the current namespaces or url name
        if (resolver_match.url_name and part_match in resolver_match.url_name) or \
           (resolver_match.namespaces and any(part_match in ns for ns in resolver_match.namespaces)):
            return 'active'

    return ''
