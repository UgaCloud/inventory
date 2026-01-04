# reports.py - Fixed version
from django.db.models import Count, Sum, Avg, F, Q, Case, When, Value, IntegerField
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from datetime import datetime, timedelta
from decimal import Decimal

class InventoryReports:
    
    @staticmethod
    def generate_stock_summary_report():
        """Generate comprehensive stock summary report"""
        from app.models import Product
        
        products = Product.objects.filter(is_active=True)
        
        report_data = []
        for product in products:
            report_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else 'Uncategorized',
                'brand': product.brand or 'N/A',
                'total_stock': product.total_stock,
                'available_stock': product.available_stock,
                'committed_stock': product.committed_stock,
                'total_sales': product.total_sales_quantity,
                'total_purchases': product.total_purchase_quantity,
                'default_price': product.default_price,
                'stock_value': product.available_stock * product.default_price,
                'low_stock_stores': len(product.low_stock_stores),
                'out_of_stock_stores': len(product.out_of_stock_stores),
                'stock_status': 'CRITICAL' if len(product.low_stock_stores) > 0 else 'OK',
            })
        
        return {
            'report_type': 'Stock Summary Report',
            'generated_at': datetime.now(),
            'total_products': len(report_data),
            'total_stock_value': sum(item['stock_value'] for item in report_data),
            'data': sorted(report_data, key=lambda x: x['stock_value'], reverse=True)
        }
    
    @staticmethod
    def generate_low_stock_alert_report():
        """Generate low stock alert report with reordering recommendations"""
        from app.models import Product
        
        products = Product.objects.filter(is_active=True)
        
        low_stock_items = []
        for product in products:
            low_stock_data = product.low_stock_stores
            if low_stock_data:
                for store_data in low_stock_data:
                    # Calculate recommended reorder quantity
                    reorder_qty = max(
                        store_data['reorder_level'] * 2 - store_data['available_stock'],
                        store_data['reorder_level']
                    )
                    
                    low_stock_items.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'sku': product.sku,
                        'store': store_data['store'],
                        'available_stock': store_data['available_stock'],
                        'reorder_level': store_data['reorder_level'],
                        'recommended_order_qty': reorder_qty,
                        'urgency': 'HIGH' if store_data['available_stock'] == 0 else 'MEDIUM',
                        'last_updated': store_data['last_updated'],
                    })
        
        return {
            'report_type': 'Low Stock Alert Report',
            'generated_at': datetime.now(),
            'total_alerts': len(low_stock_items),
            'critical_alerts': len([i for i in low_stock_items if i['urgency'] == 'HIGH']),
            'data': sorted(low_stock_items, key=lambda x: (x['urgency'], -x['available_stock']))
        }
    
    @staticmethod
    def generate_store_performance_report(store_id=None):
        """Generate store-wise inventory performance report"""
        from app.models import StoreLocation
        
        stores = StoreLocation.objects.filter(is_active=True)
        if store_id:
            stores = stores.filter(id=store_id)
        
        report_data = []
        for store in stores:
            inventories = store.inventory_set.select_related('product')
            
            # Calculate metrics
            total_products = store.total_products
            total_stock_items = store.total_stock_items
            low_stock_items = inventories.filter(quantity_in_stock__lte=F('reorder_level')).count()
            out_of_stock_items = inventories.filter(quantity_in_stock=0).count()
            
            # Calculate inventory value (if prices are available)
            total_value = 0
            for inv in inventories:
                total_value += inv.quantity_in_stock * inv.product.default_price
            
            # Stock turnover rate (if sales data available)
            total_sales = 0
            for inv in inventories:
                total_sales += inv.product.total_sales_quantity
            
            turnover_rate = (total_sales / total_stock_items) * 100 if total_stock_items > 0 else 0
            
            report_data.append({
                'store_id': store.id,
                'store_name': store.name,
                'branch': store.branch.name if store.branch else 'N/A',
                'total_products': total_products,
                'total_stock_items': total_stock_items,
                'inventory_value': total_value,
                'low_stock_items': low_stock_items,
                'out_of_stock_items': out_of_stock_items,
                'stock_turnover_rate': round(turnover_rate, 2),
                'utilization_rate': round((total_products / 100) * 100, 2) if total_products > 0 else 0,  # Example calculation
                'performance_score': InventoryReports._calculate_performance_score(low_stock_items, out_of_stock_items, turnover_rate),
            })
        
        return {
            'report_type': 'Store Performance Report',
            'generated_at': datetime.now(),
            'total_stores': len(report_data),
            'data': sorted(report_data, key=lambda x: x['performance_score'], reverse=True)
        }
    
    @staticmethod
    def generate_category_analysis_report():
        """Generate category-wise inventory analysis"""
        from app.models import Category
        
        categories = Category.objects.all()
        
        # First pass: calculate total value for all categories
        total_value_all_categories = 0
        categories_data = []
        
        for category in categories:
            products = category.products.filter(is_active=True)
            
            total_products = products.count()
            total_stock = sum(p.total_stock for p in products)
            total_value = sum(p.total_stock * p.default_price for p in products)
            
            # Store data for second pass
            categories_data.append({
                'category': category,
                'products': products,
                'total_products': total_products,
                'total_stock': total_stock,
                'total_value': total_value,
            })
            
            total_value_all_categories += total_value
        
        # Second pass: calculate percentages
        report_data = []
        for cat_data in categories_data:
            category = cat_data['category']
            products = cat_data['products']
            total_products = cat_data['total_products']
            total_stock = cat_data['total_stock']
            total_value = cat_data['total_value']
            
            avg_stock_per_product = total_stock / total_products if total_products > 0 else 0
            
            # Category performance metrics
            category_sales = sum(p.total_sales_quantity for p in products)
            category_purchases = sum(p.total_purchase_quantity for p in products)
            
            report_data.append({
                'category_id': category.id,
                'category_name': category.name,
                'total_products': total_products,
                'total_stock': total_stock,
                'inventory_value': total_value,
                'avg_stock_per_product': round(avg_stock_per_product, 2),
                'total_sales': category_sales,
                'total_purchases': category_purchases,
                'turnover_ratio': round((category_sales / total_stock) * 100, 2) if total_stock > 0 else 0,
                'contribution_percentage': round((total_value / total_value_all_categories) * 100, 2) if total_value_all_categories > 0 else 0,
            })
        
        return {
            'report_type': 'Category Analysis Report',
            'generated_at': datetime.now(),
            'total_categories': len(report_data),
            'total_value_all_categories': total_value_all_categories,
            'data': sorted(report_data, key=lambda x: x['inventory_value'], reverse=True)
        }
    
    @staticmethod
    def generate_product_movement_report(product_id=None, days=30):
        """Generate product movement/sales velocity report"""
        from app.models import Product
        from app.models.transactions import SalesOrderItem, PurchaseOrderItem
        
        products = Product.objects.filter(is_active=True)
        if product_id:
            products = products.filter(id=product_id)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        report_data = []
        for product in products:
            # Get recent sales and purchases
            recent_sales = SalesOrderItem.objects.filter(
                product=product,
                sales_order__created_at__range=[start_date, end_date]
            ).aggregate(total_sales=Sum('quantity'))['total_sales'] or 0
            
            recent_purchases = PurchaseOrderItem.objects.filter(
                product=product,
                purchase_order__created_at__range=[start_date, end_date]
            ).aggregate(total_purchases=Sum('quantity'))['total_purchases'] or 0
            
            # Calculate daily averages
            daily_sales_avg = recent_sales / days
            daily_purchase_avg = recent_purchases / days
            
            # Stock cover/days of supply
            days_of_supply = product.available_stock / daily_sales_avg if daily_sales_avg > 0 else 999
            
            # Velocity classification
            if daily_sales_avg > 10:
                velocity = 'FAST'
            elif daily_sales_avg > 2:
                velocity = 'MEDIUM'
            else:
                velocity = 'SLOW'
            
            report_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'available_stock': product.available_stock,
                'days_of_supply': round(days_of_supply, 1),
                'daily_sales_avg': round(daily_sales_avg, 2),
                'daily_purchase_avg': round(daily_purchase_avg, 2),
                'sales_velocity': velocity,
                'reorder_recommendation': 'URGENT' if days_of_supply < 7 else 'MONITOR',
                'suggested_order_qty': InventoryReports._calculate_suggested_order(daily_sales_avg, product.available_stock, days),
            })
        
        return {
            'report_type': f'Product Movement Report ({days} days)',
            'generated_at': datetime.now(),
            'period': f'{start_date.date()} to {end_date.date()}',
            'data': sorted(report_data, key=lambda x: x['daily_sales_avg'], reverse=True)
        }
    
    @staticmethod
    def generate_abc_analysis_report():
        """Generate ABC analysis based on inventory value"""
        from app.models import Product
        
        products = Product.objects.filter(is_active=True)
        
        # Calculate value for each product
        product_values = []
        for product in products:
            value = product.available_stock * product.default_price
            product_values.append({
                'product': product,
                'value': value,
                'percentage': 0  # Will calculate later
            })
        
        # Sort by value
        product_values.sort(key=lambda x: x['value'], reverse=True)
        total_value = sum(item['value'] for item in product_values)
        
        # Calculate cumulative percentages and assign ABC classes
        cumulative_value = 0
        for item in product_values:
            cumulative_value += item['value']
            percentage = (item['value'] / total_value) * 100 if total_value > 0 else 0
            cumulative_percentage = (cumulative_value / total_value) * 100 if total_value > 0 else 0
            
            # Assign ABC class
            if cumulative_percentage <= 80:
                abc_class = 'A'
            elif cumulative_percentage <= 95:
                abc_class = 'B'
            else:
                abc_class = 'C'
            
            item['percentage'] = round(percentage, 2)
            item['cumulative_percentage'] = round(cumulative_percentage, 2)
            item['abc_class'] = abc_class
            item['product_id'] = item['product'].id
            item['product_name'] = item['product'].name
            item['sku'] = item['product'].sku
            item['available_stock'] = item['product'].available_stock
        
        # Remove product object from final data
        final_data = []
        for item in product_values:
            final_data.append({
                'product_id': item['product_id'],
                'product_name': item['product_name'],
                'sku': item['sku'],
                'available_stock': item['available_stock'],
                'inventory_value': item['value'],
                'percentage': item['percentage'],
                'cumulative_percentage': item['cumulative_percentage'],
                'abc_class': item['abc_class'],
            })
        
        return {
            'report_type': 'ABC Analysis Report',
            'generated_at': datetime.now(),
            'total_value': total_value,
            'class_summary': {
                'A': len([p for p in final_data if p['abc_class'] == 'A']),
                'B': len([p for p in final_data if p['abc_class'] == 'B']),
                'C': len([p for p in final_data if p['abc_class'] == 'C']),
            },
            'data': final_data
        }
    
    # Helper methods
    @staticmethod
    def _calculate_performance_score(low_stock, out_of_stock, turnover):
        """Calculate store performance score (0-100)"""
        # Weighted scoring
        low_stock_score = max(0, 100 - (low_stock * 5))
        out_of_stock_score = max(0, 100 - (out_of_stock * 10))
        turnover_score = min(100, turnover * 2)
        
        return round((low_stock_score * 0.3) + (out_of_stock_score * 0.4) + (turnover_score * 0.3))
    
    @staticmethod
    def _calculate_suggested_order(daily_sales, current_stock, lead_time_days=7, safety_stock_days=3):
        """Calculate suggested order quantity"""
        lead_time_demand = daily_sales * lead_time_days
        safety_stock = daily_sales * safety_stock_days
        target_stock = lead_time_demand + safety_stock
        
        suggested = max(0, target_stock - current_stock)
        return round(suggested)
    
    


    @staticmethod
    def generate_stock_transfer_report(store_id=None):
        """Generate stock transfer status report"""
        from app.models.transactions import StockTransfer, StockTransferItem
        from django.db.models import Sum, Q
        
        transfers = StockTransfer.objects.all()
        if store_id:
            transfers = transfers.filter(Q(from_store_id=store_id) | Q(to_store_id=store_id))
        
        report_data = []
        for transfer in transfers:
            # Calculate total items and quantity
            items_summary = StockTransferItem.objects.filter(
                stock_transfer=transfer
            ).aggregate(
                total_items=Count('id'),
                total_quantity=Sum('quantity')
            )
            
            report_data.append({
                'transfer_id': transfer.id,
                'reference': transfer.reference if hasattr(transfer, 'reference') else f'TRF-{transfer.id}',
                'from_store': transfer.from_store.name if transfer.from_store else 'N/A',
                'to_store': transfer.to_store.name if transfer.to_store else 'N/A',
                'status': transfer.get_status_display() if hasattr(transfer, 'get_status_display') else str(transfer.status),
                'total_items': items_summary['total_items'] or 0,
                'total_quantity': items_summary['total_quantity'] or 0,
                'created_at': transfer.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(transfer, 'created_at') else 'N/A',
                'completed_at': transfer.completed_at.strftime('%Y-%m-%d %H:%M') if hasattr(transfer, 'completed_at') and transfer.completed_at else 'Pending',
                'created_by': transfer.created_by.get_full_name() if hasattr(transfer, 'created_by') and transfer.created_by else 'System',
            })
        
        # Summary statistics
        total_transfers = len(report_data)
        pending_transfers = len([t for t in report_data if t['status'].lower() in ['pending', 'in_transit']])
        completed_transfers = len([t for t in report_data if t['status'].lower() in ['completed', 'delivered']])
        
        return {
            'report_type': 'Stock Transfer Report',
            'generated_at': datetime.now(),
            'total_transfers': total_transfers,
            'pending_transfers': pending_transfers,
            'completed_transfers': completed_transfers,
            'completion_rate': round((completed_transfers / total_transfers * 100), 2) if total_transfers > 0 else 0,
            'data': sorted(report_data, key=lambda x: x.get('created_at', ''), reverse=True)
        }

    @staticmethod
    def generate_product_availability_report(product_id=None):
        """Generate product availability across all stores"""
        from app.models import Product, StoreLocation
        
        products = Product.objects.filter(is_active=True)
        if product_id:
            products = products.filter(id=product_id)
        
        all_stores = StoreLocation.objects.filter(is_active=True)
        total_stores = all_stores.count()
        
        report_data = []
        for product in products:
            stock_by_store = product.stock_by_store
            
            # Calculate availability metrics
            total_available = sum(store['available_stock'] for store in stock_by_store)
            stores_with_stock = len([store for store in stock_by_store if store['available_stock'] > 0])
            stores_low_stock = len([store for store in stock_by_store if 0 < store['available_stock'] <= store['reorder_level']])
            stores_out_of_stock = len([store for store in stock_by_store if store['available_stock'] == 0])
            
            # Detailed store breakdown
            store_details = []
            for store_data in stock_by_store:
                store_details.append({
                    'store_name': store_data['store'],
                    'physical_stock': store_data['physical_stock'],
                    'available_stock': store_data['available_stock'],
                    'reorder_level': store_data['reorder_level'],
                    'status': 'OUT_OF_STOCK' if store_data['available_stock'] == 0 else 
                            'LOW_STOCK' if store_data['available_stock'] <= store_data['reorder_level'] else 
                            'IN_STOCK'
                })
            
            # Overall status
            if stores_out_of_stock == total_stores:
                overall_status = 'OUT_OF_STOCK'
            elif stores_low_stock > 0 or stores_out_of_stock > 0:
                overall_status = 'PARTIAL_AVAILABILITY'
            else:
                overall_status = 'FULLY_AVAILABLE'
            
            report_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else 'Uncategorized',
                'total_available': total_available,
                'stores_with_stock': stores_with_stock,
                'stores_low_stock': stores_low_stock,
                'stores_out_of_stock': stores_out_of_stock,
                'total_stores': total_stores,
                'availability_rate': round((stores_with_stock / total_stores) * 100, 2) if total_stores > 0 else 0,
                'overall_status': overall_status,
                'store_details': store_details,
            })
        
        # Generate summary statistics
        total_products = len(report_data)
        fully_available = len([p for p in report_data if p['overall_status'] == 'FULLY_AVAILABLE'])
        partial_available = len([p for p in report_data if p['overall_status'] == 'PARTIAL_AVAILABILITY'])
        out_of_stock = len([p for p in report_data if p['overall_status'] == 'OUT_OF_STOCK'])
        
        return {
            'report_type': 'Product Availability Report',
            'generated_at': datetime.now(),
            'total_products': total_products,
            'fully_available': fully_available,
            'partial_available': partial_available,
            'out_of_stock': out_of_stock,
            'summary': {
                'fully_available_percentage': round((fully_available / total_products * 100), 2) if total_products > 0 else 0,
                'overall_availability_rate': round((sum(p['availability_rate'] for p in report_data) / total_products), 2) if total_products > 0 else 0,
            },
            'data': sorted(report_data, key=lambda x: x['availability_rate'], reverse=True)
        }

    @staticmethod
    def generate_inventory_valuation_report():
        """Generate detailed inventory valuation report with cost analysis"""
        from app.models import Product
        
        products = Product.objects.filter(is_active=True)
        
        report_data = []
        total_valuation = 0
        total_cost = 0  # If you have cost field
        
        for product in products:
            stock_value = product.available_stock * product.default_price
            
            # If you have cost price in your model
            # cost_value = product.available_stock * product.cost_price
            # profit_margin = ((product.default_price - product.cost_price) / product.cost_price * 100) if product.cost_price > 0 else 0
            
            # For now, using default price as both cost and selling (adjust based on your actual model)
            cost_value = stock_value  # Assuming cost equals selling price for now
            profit_margin = 0
            
            report_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else 'Uncategorized',
                'available_stock': product.available_stock,
                'unit_price': product.default_price,
                'stock_value': stock_value,
                'cost_value': cost_value,
                'profit_margin': round(profit_margin, 2),
                'turnover_rate': round((product.total_sales_quantity / product.total_stock * 100), 2) if product.total_stock > 0 else 0,
                'valuation_percentage': 0,  # Will be calculated below
            })
            
            total_valuation += stock_value
            total_cost += cost_value
        
        # Calculate percentages
        for item in report_data:
            if total_valuation > 0:
                item['valuation_percentage'] = round((item['stock_value'] / total_valuation * 100), 2)
        
        # Summary by category
        category_summary = {}
        for item in report_data:
            category = item['category']
            if category not in category_summary:
                category_summary[category] = {
                    'total_value': 0,
                    'product_count': 0,
                    'avg_profit_margin': 0,
                }
            category_summary[category]['total_value'] += item['stock_value']
            category_summary[category]['product_count'] += 1
        
        # Convert to list
        category_data = []
        for category, summary in category_summary.items():
            category_data.append({
                'category': category,
                'total_value': summary['total_value'],
                'product_count': summary['product_count'],
                'percentage_of_total': round((summary['total_value'] / total_valuation * 100), 2) if total_valuation > 0 else 0,
                'avg_value_per_product': round((summary['total_value'] / summary['product_count']), 2) if summary['product_count'] > 0 else 0,
            })
        
        return {
            'report_type': 'Inventory Valuation Report',
            'generated_at': datetime.now(),
            'total_valuation': total_valuation,
            'total_cost': total_cost,
            'estimated_profit': total_valuation - total_cost,
            'profit_margin_percentage': round(((total_valuation - total_cost) / total_cost * 100), 2) if total_cost > 0 else 0,
            'total_products': len(report_data),
            'category_summary': sorted(category_data, key=lambda x: x['total_value'], reverse=True),
            'data': sorted(report_data, key=lambda x: x['stock_value'], reverse=True)
        }
        

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    