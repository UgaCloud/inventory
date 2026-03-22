from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, F, Q, Avg
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import datetime, timedelta
import json
from decimal import Decimal
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from app.models.transactions import Sales, SalesItem
from app.models.products import StoreLocation, Product
from django.core.paginator import Paginator

@login_required
def branch_sales_report(request):
    """
    Main branch sales report view with filters and pagination
    """
    # Get filter parameters
    branch_id = request.GET.get('branch')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    period = request.GET.get('period', 'daily')  # daily, weekly, monthly
    product_id = request.GET.get('product')
    salesperson_id = request.GET.get('salesperson')
    
    # Base queryset
    sales = Sales.objects.select_related('store', 'customer', 'recorded_by').prefetch_related('items__product')

    # Apply filters
    if branch_id:
        sales = sales.filter(store_id=branch_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__gte=date_from_obj)
        except ValueError:
            date_from = None
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__lte=date_to_obj)
        except ValueError:
            date_to = None
    
    if product_id:
        sales = sales.filter(items__product_id=product_id)
    
    if salesperson_id:
        sales = sales.filter(recorded_by_id=salesperson_id)

    # Default date range if not provided
    if not date_from and not date_to:
        date_to_obj = timezone.now().date()
        date_from_obj = date_to_obj - timedelta(days=30)
        sales = sales.filter(sale_date__gte=date_from_obj, sale_date__lte=date_to_obj)
        date_from = date_from_obj.strftime('%Y-%m-%d')
        date_to = date_to_obj.strftime('%Y-%m-%d')
    
    # Calculate summary statistics
    summary_stats = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id'),
        total_items_sold=Sum('items__quantity'),
        average_transaction=Avg('total_amount'),
    )
    
    # Handle None values
    for key, value in summary_stats.items():
        if value is None:
            summary_stats[key] = 0
    
    # Get sales by period for chart
    if period == 'daily':
        sales_by_period = sales.values('sale_date').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('sale_date')
    elif period == 'weekly':
        sales_by_period = sales.annotate(
            period=TruncWeek('sale_date')
        ).values('period').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('period')
    else:  # monthly
        sales_by_period = sales.annotate(
            period=TruncMonth('sale_date')
        ).values('period').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('period')
    
    # Top products
    top_products = SalesItem.objects.filter(
        order__in=sales
    ).values(
        'product__name', 'product__sku'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('sale_price')),
        total_transactions=Count('order', distinct=True)
    ).order_by('-total_revenue')[:10]
    
    # Top branches if not filtered by specific branch
    top_branches = None
    if not branch_id:
        top_branches = sales.values(
            'store__name', 'store__id'
        ).annotate(
            total_sales=Sum('total_amount'),
            total_transactions=Count('id'),
            total_items=Sum('items__quantity')
        ).order_by('-total_sales')[:10]
    
    # Top salespersons
    top_salespersons = sales.values(
        'recorded_by__first_name', 'recorded_by__last_name', 'recorded_by__username'
    ).annotate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id'),
        average_sale=Avg('total_amount')
    ).order_by('-total_sales')[:10]
    
    # Recent transactions for the table
    recent_sales = sales.order_by('-sale_date')
    
    # Pagination
    paginator = Paginator(recent_sales, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available filters
    branches = StoreLocation.objects.filter(is_active=True).order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')
    salespersons = Sales.objects.values('recorded_by__id', 'recorded_by__first_name', 'recorded_by__last_name', 'recorded_by__username').distinct()

    context = {
        'sales': page_obj,
        'summary_stats': summary_stats,
        'sales_by_period': list(sales_by_period),
        'top_products': top_products,
        'top_branches': top_branches,
        'top_salespersons': top_salespersons,
        'branches': branches,
        'products': products,
        'salespersons': salespersons,
        'filters': {
            'branch_id': branch_id,
            'date_from': date_from,
            'date_to': date_to,
            'period': period,
            'product_id': product_id,
            'salesperson_id': salesperson_id,
        }
    }
    
    return render(request, 'reports/branch_sales_report.html', context)


@login_required
def branch_sales_report_api(request):
    """
    API endpoint for AJAX requests to update charts and data
    """
    # Similar filtering logic as above
    branch_id = request.GET.get('branch')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    period = request.GET.get('period', 'daily')
    
    # Base queryset
    sales = Sales.objects.select_related('store')
    
    # Apply filters
    if branch_id:
        sales = sales.filter(store_id=branch_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Get chart data based on period
    if period == 'daily':
        chart_data = sales.values('sale_date').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('sale_date')
        
        chart_labels = [item['sale_date'].strftime('%Y-%m-%d') for item in chart_data]
        
    elif period == 'weekly':
        chart_data = sales.annotate(
            week=TruncWeek('sale_date')
        ).values('week').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('week')
        
        chart_labels = [item['week'].strftime('Week of %Y-%m-%d') for item in chart_data]
        
    else:  # monthly
        chart_data = sales.annotate(
            month=TruncMonth('sale_date')
        ).values('month').annotate(
            total=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('month')
        
        chart_labels = [item['month'].strftime('%B %Y') for item in chart_data]
    
    # Prepare data for charts
    sales_data = [float(item['total'] or 0) for item in chart_data]
    transaction_data = [item['transactions'] for item in chart_data]
    
    # Summary statistics
    summary = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id'),
        total_items_sold=Sum('items__quantity'),
        average_transaction=Avg('total_amount')
    )
    
    # Handle None values
    for key, value in summary.items():
        if value is None:
            summary[key] = 0
        elif isinstance(value, Decimal):
            summary[key] = float(value)
    
    return JsonResponse({
        'success': True,
        'chart_labels': chart_labels,
        'sales_data': sales_data,
        'transaction_data': transaction_data,
        'summary': summary
    })


@login_required
def export_branch_sales_csv(request):
    """
    Export branch sales report to CSV
    """
    # Get the same filtered data
    branch_id = request.GET.get('branch')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    sales = Sales.objects.select_related('store', 'customer', 'recorded_by').prefetch_related('items__product')

    # Apply filters (same as main view)
    if branch_id:
        sales = sales.filter(store_id=branch_id)
        branch_name = StoreLocation.objects.get(id=branch_id).name
    else:
        branch_name = "All Branches"
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__gte=date_from_obj)
        except ValueError:
            date_from = "N/A"
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__lte=date_to_obj)
        except ValueError:
            date_to = "N/A"
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="branch_sales_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write headers
    writer.writerow(['Branch Sales Report'])
    writer.writerow([f'Branch: {branch_name}'])
    writer.writerow([f'Period: {date_from} to {date_to}'])
    writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])  # Empty row
    
    # Write column headers
    writer.writerow([
        'Date',
        'Receipt No',
        'Branch',
        'Customer',
        'Salesperson',
        'Items Count',
        'Subtotal',
        'Discount',
        'Tax',
        'Total Amount',
        'Payment Method'
    ])
    
    # Write data rows
    for sale in sales:
        writer.writerow([
            sale.date.strftime('%Y-%m-%d'),
            sale.receipt_number or f'SALE-{sale.id}',
            sale.store.name if sale.store else 'N/A',
            sale.customer.name if sale.customer else 'Walk-in Customer',
            f'{sale.recorded_by.first_name} {sale.recorded_by.last_name}' if sale.recorded_by.first_name else sale.recorded_by.username,
            sale.items.count(),
            f'{sale.subtotal:.2f}',
            # f'{sale.discount_amount:.2f}' if sale.discount_amount else '0.00',
            # f'{sale.tax_amount:.2f}' if sale.tax_amount else '0.00',
            f'{sale.total_amount:.2f}',
            sale.payment_method or 'Cash'
        ])
    
    return response


@login_required
def export_branch_sales_pdf(request):
    """
    Export branch sales report to PDF
    """
    from io import BytesIO
    
    # Get filtered data (same logic as CSV export)
    branch_id = request.GET.get('branch')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    sales = Sales.objects.select_related('store', 'customer', 'recorded_by').prefetch_related('items__product')

    if branch_id:
        sales = sales.filter(store_id=branch_id)
        branch_name = StoreLocation.objects.get(id=branch_id).name
    else:
        branch_name = "All Branches"
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__gte=date_from_obj)
        except ValueError:
            date_from = "N/A"
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            sales = sales.filter(sale_date__lte=date_to_obj)
        except ValueError:
            date_to = "N/A"
    
    # Calculate summary
    summary = sales.aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id'),
        total_items_sold=Sum('items__quantity'),
        total_discount=Sum('discount_amount'),
        total_tax=Sum('tax_amount')
    )
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph(f"<b>Branch Sales Report</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Report info
    report_info = [
        ['Branch:', branch_name],
        ['Period:', f'{date_from} to {date_to}'],
        ['Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]
    
    info_table = Table(report_info, colWidths=[2*72, 4*72])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))
    
    # Summary table
    summary_data = [
        ['Summary', ''],
        ['Total Sales:', f'UGX {summary["total_sales"] or 0:,.2f}'],
        ['Total Transactions:', f'{summary["total_transactions"] or 0:,}'],
        ['Total Items Sold:', f'{summary["total_items_sold"] or 0:,}'],
        ['Total Discount:', f'UGX {summary["total_discount"] or 0:,.2f}'],
        ['Total Tax:', f'UGX {summary["total_tax"] or 0:,.2f}'],
    ]
    
    summary_table = Table(summary_data, colWidths=[2*72, 2*72])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Transactions table
    story.append(Paragraph("<b>Recent Transactions</b>", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    # Table headers
    table_data = [['Date', 'Receipt', 'Customer', 'Items', 'Total']]
    
    # Add transaction data (limit to first 50 for PDF)
    for sale in sales[:50]:
        table_data.append([
            sale.date.strftime('%Y-%m-%d'),
            sale.receipt_number or f'SALE-{sale.id}',
            (sale.customer.name if sale.customer else 'Walk-in')[:20],  # Truncate long names
            str(sale.items.count()),
            f'UGX {sale.total_amount:,.2f}'
        ])
    
    # Create table
    transactions_table = Table(table_data, colWidths=[1.2*72, 1.5*72, 2*72, 0.8*72, 1.5*72])
    transactions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(transactions_table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Create response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="branch_sales_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    return response


@login_required
def branch_comparison_report(request):
    """
    Compare sales performance across different branches
    """
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Default date range
    if not date_from and not date_to:
        date_to_obj = timezone.now().date()
        date_from_obj = date_to_obj - timedelta(days=30)
    else:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else timezone.now().date() - timedelta(days=30)
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else timezone.now().date()
        except ValueError:
            date_to_obj = timezone.now().date()
            date_from_obj = date_to_obj - timedelta(days=30)
    
    # Get branch performance data
    branch_performance = StoreLocation.objects.filter(
        is_active=True
    ).annotate(
        total_sales=Sum('sales__total_amount', filter=Q(sales__sale_date__gte=date_from_obj, sales__sale_date__lte=date_to_obj)),
        total_transactions=Count('sales', filter=Q(sales__sale_date__gte=date_from_obj, sales__sale_date__lte=date_to_obj)),
        average_transaction=Avg('sales__total_amount', filter=Q(sales__sale_date__gte=date_from_obj, sales__sale_date__lte=date_to_obj))
    ).order_by('-total_sales')
    
    # Handle None values
    for branch in branch_performance:
        branch.total_sales = branch.total_sales or 0
        branch.total_transactions = branch.total_transactions or 0
        branch.total_items_sold = branch.total_items_sold or 0
        branch.average_transaction = branch.average_transaction or 0
    
    context = {
        'branch_performance': branch_performance,
        'date_from': date_from_obj.strftime('%Y-%m-%d'),
        'date_to': date_to_obj.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'reports/branch_comparison_report.html', context)

@login_required
def sales_item_unit_report(request):
    """
    General sales item report with breakdown of quantities sold unit wise.
    """
    # Optional filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    product_id = request.GET.get('product')

    sales_items = SalesItem.objects.select_related('product', 'order', 'unit')

    # Filter by date range if provided
    if date_from:
        sales_items = sales_items.filter(order__sale_date__gte=date_from)
    if date_to:
        sales_items = sales_items.filter(order__sale_date__lte=date_to)
    if product_id:
        sales_items = sales_items.filter(product_id=product_id)

    # Group by product and unit, sum quantities
    report_data = sales_items.values(
        'product__id',
        'product__name',
        'product__sku',
        'unit__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum(F('quantity') * F('sale_price'))
    ).order_by('product__name', 'unit__name')

    # Get products for filter dropdown
    products = Product.objects.filter(is_active=True).order_by('name')

    context = {
        'report_data': report_data,
        'products': products,
        'filters': {
            'date_from': date_from,
            'date_to': date_to,
            'product_id': product_id,
        }
    }
    return render(request, 'reports/sales_item_unit_report.html', context)

@login_required
def export_sales_item_unit_csv(request):
    """
    Export general sales item unit report to CSV.
    """
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    product_id = request.GET.get('product')

    sales_items = SalesItem.objects.select_related('product', 'order', 'unit')
    if date_from:
        sales_items = sales_items.filter(order__sale_date__gte=date_from)
    if date_to:
        sales_items = sales_items.filter(order__sale_date__lte=date_to)
    if product_id:
        sales_items = sales_items.filter(product_id=product_id)

    report_data = sales_items.values(
        'product__name',
        'product__sku',
        'unit__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum(F('quantity') * F('sale_price'))
    ).order_by('product__name', 'unit__name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_item_unit_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Product', 'SKU', 'Unit', 'Quantity Sold', 'Total Sales (UGX)'])
    for row in report_data:
        writer.writerow([
            row['product__name'],
            row['product__sku'],
            row['unit__name'],
            row['total_quantity'],
            f"{row['total_sales']:.2f}" if row['total_sales'] else "0.00"
        ])
    return response

@login_required
def export_sales_item_unit_pdf(request):
    """
    Export general sales item unit report to PDF.
    """
    from io import BytesIO

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    product_id = request.GET.get('product')

    sales_items = SalesItem.objects.select_related('product', 'order', 'unit')
    if date_from:
        sales_items = sales_items.filter(order__sale_date__gte=date_from)
    if date_to:
        sales_items = sales_items.filter(order__sale_date__lte=date_to)
    if product_id:
        sales_items = sales_items.filter(product_id=product_id)

    report_data = sales_items.values(
        'product__name',
        'product__sku',
        'unit__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum(F('quantity') * F('sale_price'))
    ).order_by('product__name', 'unit__name')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("<b>Sales Item Unit Report</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Report info
    info = [
        ['Date From:', date_from or 'N/A'],
        ['Date To:', date_to or 'N/A'],
        ['Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]
    info_table = Table(info, colWidths=[2*72, 4*72])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # Table headers
    table_data = [['Product', 'SKU', 'Unit', 'Quantity Sold', 'Total Sales (UGX)']]
    for row in report_data:
        table_data.append([
            row['product__name'],
            row['product__sku'],
            row['unit__name'],
            str(row['total_quantity']),
            f"UGX {row['total_sales']:,.2f}" if row['total_sales'] else "UGX 0.00"
        ])

    data_table = Table(table_data, colWidths=[2*72, 1.2*72, 1.2*72, 1.2*72, 2*72])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(data_table)

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_item_unit_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    return response

