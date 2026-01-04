# views/reports.py
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
import csv
from .reports import InventoryReports


@login_required
def reports_dashboard(request):
    """Reports dashboard view"""
    from app.models import Product, StoreLocation
    
    # Get basic stats for the dashboard
    total_products = Product.objects.filter(is_active=True).count()
    active_stores = StoreLocation.objects.filter(is_active=True).count()
    
    # Get low stock count (you might need to implement this)
    low_stock_count = 0  # Placeholder
    
    # Get total inventory value
    total_value = 0
    products = Product.objects.filter(is_active=True)
    for product in products:
        total_value += product.available_stock * product.default_price
    
    context = {
        'total_products': total_products,
        'active_stores': active_stores,
        'low_stock_items': low_stock_count,
        'total_value': total_value,
        'stores': StoreLocation.objects.filter(is_active=True),
        'products': Product.objects.filter(is_active=True),
    }
    
    return render(request, 'reports/dashboard.html', context)


@login_required
def reports_view(request, report_type):
    """Handle inventory reports with dynamic templates"""
    
    # Get filters from request
    store_id = request.GET.get('store_id')
    product_id = request.GET.get('product_id')
    days = int(request.GET.get('days', 30))
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    
    # Map report types to methods
    report_methods = {
        'stock_summary': {
            'method': InventoryReports.generate_stock_summary_report,
            'title': 'Stock Summary Report',
            'subtitle': 'Complete inventory overview with stock values',
            'show_filters': False,
            'show_date_filters': False,
        },
        'low_stock': {
            'method': InventoryReports.generate_low_stock_alert_report,
            'title': 'Low Stock Alert Report',
            'subtitle': 'Products below reorder level requiring attention',
            'show_filters': False,
            'show_date_filters': False,
        },
        'store_performance': {
            'method': lambda: InventoryReports.generate_store_performance_report(store_id),
            'title': 'Store Performance Report',
            'subtitle': 'Store-wise inventory metrics and performance',
            'show_filters': True,
            'show_date_filters': False,
        },
        'category_analysis': {
            'method': InventoryReports.generate_category_analysis_report,
            'title': 'Category Analysis Report',
            'subtitle': 'Inventory performance by product category',
            'show_filters': False,
            'show_date_filters': False,
        },
        'product_movement': {
            'method': lambda: InventoryReports.generate_product_movement_report(product_id, days),
            'title': f'Product Movement Report ({days} days)',
            'subtitle': 'Sales velocity and stock movement analysis',
            'show_filters': True,
            'show_date_filters': False,
        },
        'abc_analysis': {
            'method': InventoryReports.generate_abc_analysis_report,
            'title': 'ABC Analysis Report',
            'subtitle': 'Inventory classification by value importance',
            'show_filters': False,
            'show_date_filters': False,
        },
        'inventory_valuation': {
            'method': InventoryReports.generate_inventory_valuation_report,
            'title': 'Inventory Valuation Report',
            'subtitle': 'Complete inventory valuation with cost analysis',
            'show_filters': False,
            'show_date_filters': False,
        },
        'stock_transfer': {
            'method': lambda: InventoryReports.generate_stock_transfer_report(store_id),
            'title': 'Stock Transfer Report',
            'subtitle': 'Transfer status and movement tracking',
            'show_filters': True,
            'show_date_filters': False,
        },
        'product_availability': {
            'method': lambda: InventoryReports.generate_product_availability_report(product_id),
            'title': 'Product Availability Report',
            'subtitle': 'Product availability across all stores',
            'show_filters': True,
            'show_date_filters': False,
        },
    }
    
    if report_type not in report_methods:
        return render(request, 'reports/error.html', {
            'error': 'Invalid report type',
            'report_type': report_type
        })
    
    # Get report configuration
    config = report_methods[report_type]
    
    try:
        # Generate report data
        report_data = config['method']()
        
        # Process report data for template
        processed_data = process_report_data(report_data, report_type)
        
        # Add pagination if needed
        if 'data' in processed_data and len(processed_data['data']) > per_page:
            paginator = Paginator(processed_data['data'], per_page)
            page_obj = paginator.get_page(page)
            processed_data['data'] = page_obj
        
        # Prepare context
        context = {
            'report_type': report_type,
            'report_title': config['title'],
            'report_subtitle': config['subtitle'],
            'report_data': processed_data,
            'show_filters': config['show_filters'],
            'show_date_filters': config.get('show_date_filters', False),
            'filters': {
                'store_id': store_id,
                'product_id': product_id,
                'days': days,
                'date_from': request.GET.get('date_from'),
                'date_to': request.GET.get('date_to'),
            },
            'currency_symbol': 'UGX',
        }
        
        # Add filter options
        from app.models import StoreLocation, Product
        if config['show_filters']:
            context['stores'] = StoreLocation.objects.filter(is_active=True)
            context['products'] = Product.objects.filter(is_active=True)
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'data': report_data})
        
        # Regular request - render template
        return render(request, 'reports/report_view.html', context)
        
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
        
        return render(request, 'reports/report_view.html', {
            'error': str(e),
            'report_type': report_type,
            'report_title': config['title']
        })


def process_report_data(report_data, report_type):
    """Process raw report data for template display"""
    processed = {
        'generated_at': report_data.get('generated_at', datetime.now()),
        'report_type': report_data.get('report_type', report_type),
        'data': [],
        'headers': [],
        'summary_stats': [],
        'chart_data': None,
    }
    
    # Extract summary statistics
    summary_stats = extract_summary_stats(report_data, report_type)
    if summary_stats:
        processed['summary_stats'] = summary_stats
    
    # Process main data
    if 'data' in report_data and report_data['data']:
        if isinstance(report_data['data'], list) and len(report_data['data']) > 0:
            # Get headers from first item
            first_item = report_data['data'][0]
            if isinstance(first_item, dict):
                processed['headers'] = list(first_item.keys())
                processed['data'] = report_data['data']
    
    # Add category summary if available
    if 'category_summary' in report_data:
        processed['category_summary'] = report_data['category_summary']
    
    # Add insights if available
    if report_data.get('total_products'):
        processed['insights'] = generate_insights(report_data, report_type)
    
    # Generate chart data if needed
    if len(processed['data']) > 0:
        processed['chart_data'] = generate_chart_data(processed['data'], report_type)
    
    return processed


def extract_summary_stats(report_data, report_type):
    """Extract summary statistics from report data"""
    stats = []
    
    if report_type == 'stock_summary':
        stats.extend([
            {
                'label': 'Total Products',
                'value': report_data.get('total_products', 0),
                'icon': 'package',
                'color': 'primary'
            },
            {
                'label': 'Total Stock Value',
                'value': f"{report_data.get('total_stock_value', 0):,.0f}",
                'icon': 'dollar-sign',
                'color': 'success'
            },
            {
                'label': 'Low Stock Items',
                'value': report_data.get('total_low_stock', 0),
                'icon': 'alert-triangle',
                'color': 'warning'
            },
        ])
    
    elif report_type == 'low_stock':
        stats.extend([
            {
                'label': 'Total Alerts',
                'value': report_data.get('total_alerts', 0),
                'icon': 'alert-circle',
                'color': 'danger'
            },
            {
                'label': 'Critical Alerts',
                'value': report_data.get('critical_alerts', 0),
                'icon': 'alert-triangle',
                'color': 'warning'
            },
        ])
    
    elif report_type == 'store_performance':
        if report_data.get('total_stores'):
            stats.append({
                'label': 'Stores',
                'value': report_data.get('total_stores', 0),
                'icon': 'store',
                'color': 'info'
            })
    
    return stats


def generate_insights(report_data, report_type):
    """Generate insights based on report data"""
    insights = []
    
    if report_type == 'low_stock' and report_data.get('critical_alerts', 0) > 0:
        insights.append({
            'title': 'Immediate Action Required',
            'message': f'{report_data["critical_alerts"]} products are critically low on stock.',
            'type': 'danger',
            'icon': 'alert-triangle',
            'action': 'View Details',
            'action_url': '#low-stock-section'
        })
    
    if report_type == 'stock_summary':
        low_stock_count = report_data.get('total_low_stock', 0)
        if low_stock_count > 0:
            insights.append({
                'title': 'Reordering Required',
                'message': f'{low_stock_count} products need reordering.',
                'type': 'warning',
                'icon': 'shopping-cart'
            })
    
    return insights


def generate_chart_data(data, report_type):
    """Generate chart data from report data"""
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    
    try:
        if report_type in ['stock_summary', 'inventory_valuation']:
            # Bar chart for top items by value
            sorted_data = sorted(data, key=lambda x: x.get('stock_value', 0), reverse=True)[:10]
            labels = [item.get('product_name', f'Item {i}')[:20] for i, item in enumerate(sorted_data)]
            values = [item.get('stock_value', 0) for item in sorted_data]
            
            return {
                'labels': labels,
                'datasets': [{
                    'label': 'Stock Value',
                    'data': values,
                    'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                    'borderColor': 'rgba(54, 162, 235, 1)',
                    'borderWidth': 1
                }]
            }
        
        elif report_type == 'abc_analysis':
            # Pie chart for ABC classification
            abc_counts = {'A': 0, 'B': 0, 'C': 0}
            for item in data:
                abc_class = item.get('abc_class', 'C')
                if abc_class in abc_counts:
                    abc_counts[abc_class] += 1
            
            return {
                'labels': ['A Items (High Value)', 'B Items (Medium Value)', 'C Items (Low Value)'],
                'datasets': [{
                    'label': 'ABC Classification',
                    'data': [abc_counts['A'], abc_counts['B'], abc_counts['C']],
                    'backgroundColor': [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(54, 162, 235, 0.5)',
                        'rgba(255, 205, 86, 0.5)'
                    ],
                    'borderColor': [
                        'rgb(255, 99, 132)',
                        'rgb(54, 162, 235)',
                        'rgb(255, 205, 86)'
                    ],
                    'borderWidth': 1
                }]
            }
    
    except Exception as e:
        print(f"Error generating chart data: {e}")
        return None


@login_required
def export_report(request, report_type, format):
    """Export report to various formats"""
    
    # Generate report data
    report_methods = {
        'stock_summary': InventoryReports.generate_stock_summary_report,
        'low_stock': InventoryReports.generate_low_stock_alert_report,
        'store_performance': lambda: InventoryReports.generate_store_performance_report(None),
        'category_analysis': InventoryReports.generate_category_analysis_report,
        'product_movement': lambda: InventoryReports.generate_product_movement_report(None, 30),
        'abc_analysis': InventoryReports.generate_abc_analysis_report,
        'inventory_valuation': InventoryReports.generate_inventory_valuation_report,
        'stock_transfer': InventoryReports.generate_stock_transfer_report(None),
        'product_availability': InventoryReports.generate_product_availability_report(None),
    }
    
    if report_type not in report_methods:
        return HttpResponse('Invalid report type', status=400)
    
    try:
        report_data = report_methods[report_type]()
        
        if format == 'csv':
            response = HttpResponse(content_type='text/csv')
            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            writer = csv.writer(response)
            
            # Write headers
            if report_data.get('data') and len(report_data['data']) > 0:
                headers = list(report_data['data'][0].keys())
                writer.writerow(headers)
                
                # Write data rows
                for row in report_data['data']:
                    writer.writerow([row.get(header, '') for header in headers])
            
            return response
        
        elif format == 'json':
            return JsonResponse(report_data, safe=False)
        
        else:
            return HttpResponse('Format not supported', status=400)
            
    except Exception as e:
        return HttpResponse(f'Error generating export: {str(e)}', status=500)