@login_required
@permission_required('scan.view_scanordermodel', raise_exception=True)
def scan_dashboard(request):
    """Main scan dashboard with comprehensive statistics"""

    # Get current date and time ranges
    today = timezone.now().date()
    this_week_start = today - timedelta(days=today.weekday())
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)

    # === BASIC STATISTICS ===

    # Total counts
    total_orders = ScanOrderModel.objects.count()
    total_templates = ScanTemplateModel.objects.filter(is_active=True).count()
    total_categories = ScanCategoryModel.objects.count()
    completed_tests = ScanOrderModel.objects.filter(status='completed').count()

    # Today's statistics
    orders_today = ScanOrderModel.objects.filter(ordered_at__date=today).count()
    completed_today = ScanOrderModel.objects.filter(
        status='completed',
        processed_at__date=today
    ).count()
    pending_today = ScanOrderModel.objects.filter(
        ordered_at__date=today,
        status__in=['pending', 'paid', 'collected', 'processing']
    ).count()

    # This week's statistics
    orders_week = ScanOrderModel.objects.filter(ordered_at__date__gte=this_week_start).count()
    completed_week = ScanOrderModel.objects.filter(
        status='completed',
        processed_at__date__gte=this_week_start
    ).count()

    # This month's statistics
    orders_month = ScanOrderModel.objects.filter(ordered_at__date__gte=this_month_start).count()
    completed_month = ScanOrderModel.objects.filter(
        status='completed',
        processed_at__date__gte=this_month_start
    ).count()

    # Last month's statistics for growth calculation
    orders_last_month = ScanOrderModel.objects.filter(
        ordered_at__date__gte=last_month_start,
        ordered_at__date__lte=last_month_end
    ).count()
    completed_last_month = ScanOrderModel.objects.filter(
        status='completed',
        processed_at__date__gte=last_month_start,
        processed_at__date__lte=last_month_end
    ).count()

    # Calculate growth percentages
    orders_growth = 0
    completed_growth = 0
    if orders_last_month > 0:
        orders_growth = round(((orders_month - orders_last_month) / orders_last_month) * 100, 1)
    if completed_last_month > 0:
        completed_growth = round(((completed_month - completed_last_month) / completed_last_month) * 100, 1)

    # === STATUS DISTRIBUTION ===
    status_distribution = ScanOrderModel.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Convert to format suitable for charts
    status_chart_data = [
        {'name': status['status'].title(), 'value': status['count']}
        for status in status_distribution
    ]

    # === REVENUE STATISTICS ===

    # Total revenue
    total_revenue = ScanOrderModel.objects.filter(
        payment_status=True
    ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

    # Today's revenue
    revenue_today = ScanOrderModel.objects.filter(
        payment_status=True,
        payment_date__date=today
    ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

    # This week's revenue
    revenue_week = ScanOrderModel.objects.filter(
        payment_status=True,
        payment_date__date__gte=this_week_start
    ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

    # This month's revenue
    revenue_month = ScanOrderModel.objects.filter(
        payment_status=True,
        payment_date__date__gte=this_month_start
    ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

    # === CATEGORY WISE STATISTICS ===
    category_stats = ScanCategoryModel.objects.annotate(
        total_orders=Count('templates__orders'),
        completed_orders=Count('templates__orders', filter=Q(templates__orders__status='completed')),
        revenue=Sum('templates__orders__amount_charged', filter=Q(templates__orders__payment_status=True))
    ).order_by('-total_orders')

    # Format for chart
    category_chart_data = [
        {
            'name': cat.name,
            'value': cat.total_orders,
            'revenue': float(cat.revenue or 0)
        }
        for cat in category_stats[:10]  # Top 10 categories
    ]

    # === POPULAR TESTS ===
    popular_tests = ScanTemplateModel.objects.annotate(
        order_count=Count('orders')
    ).filter(order_count__gt=0).order_by('-order_count')[:10]

    popular_tests_data = [
        {
            'name': test.name,
            'orders': test.order_count,
            'revenue': float(
                ScanOrderModel.objects.filter(
                    template=test,
                    payment_status=True
                ).aggregate(total=Sum('amount_charged'))['total'] or 0
            )
        }
        for test in popular_tests
    ]

    # === DAILY TRENDS (LAST 7 DAYS) ===
    daily_trends = []
    for i in range(7):
        date = today - timedelta(days=6 - i)
        orders_count = ScanOrderModel.objects.filter(ordered_at__date=date).count()
        completed_count = ScanOrderModel.objects.filter(
            status='completed',
            processed_at__date=date
        ).count()
        revenue = ScanOrderModel.objects.filter(
            payment_status=True,
            payment_date__date=date
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

        daily_trends.append({
            'date': date.strftime('%Y-%m-%d'),
            'orders': orders_count,
            'completed': completed_count,
            'revenue': float(revenue)
        })

    # === MONTHLY TRENDS (LAST 12 MONTHS) ===
    monthly_trends = []
    for i in range(12):
        month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        for _ in range(i):
            month_start = (month_start - timedelta(days=1)).replace(day=1)

        month_end = (month_start.replace(month=month_start.month + 1)
                     if month_start.month < 12
                     else month_start.replace(year=month_start.year + 1, month=1)) - timedelta(days=1)

        orders_count = ScanOrderModel.objects.filter(
            ordered_at__date__gte=month_start,
            ordered_at__date__lte=month_end
        ).count()

        completed_count = ScanOrderModel.objects.filter(
            status='completed',
            processed_at__date__gte=month_start,
            processed_at__date__lte=month_end
        ).count()

        revenue = ScanOrderModel.objects.filter(
            payment_status=True,
            payment_date__date__gte=month_start,
            payment_date__date__lte=month_end
        ).aggregate(total=Sum('amount_charged'))['total'] or Decimal('0.00')

        monthly_trends.insert(0, {
            'month': month_start.strftime('%b %Y'),
            'orders': orders_count,
            'completed': completed_count,
            'revenue': float(revenue)
        })

    # === SOURCE DISTRIBUTION ===
    source_distribution = ScanOrderModel.objects.values('source').annotate(
        count=Count('id')
    )

    source_chart_data = [
        {
            'name': 'Doctor Prescribed' if source['source'] == 'doctor' else 'Scan Direct',
            'value': source['count']
        }
        for source in source_distribution
    ]

    # === RECENT ACTIVITY ===
    recent_orders = ScanOrderModel.objects.select_related(
        'patient', 'template', 'ordered_by'
    ).order_by('-ordered_at')[:10]

    # === AVERAGE PROCESSING TIME ===
    completed_orders = ScanOrderModel.objects.filter(
        status='completed',
        processed_at__isnull=False
    )

    avg_processing_hours = 0
    if completed_orders.exists():
        total_processing_time = sum([
            (order.processed_at - order.ordered_at).total_seconds() / 3600
            for order in completed_orders
            if order.processed_at and order.ordered_at
        ])
        avg_processing_hours = round(total_processing_time / completed_orders.count(), 1)

    # === PENDING TASKS ===
    pending_collection = ScanOrderModel.objects.filter(status='paid').count()
    pending_processing = ScanOrderModel.objects.filter(status='collected').count()
    pending_verification = ScanResultModel.objects.filter(is_verified=False).count()

    context = {
        # Basic stats
        'total_orders': total_orders,
        'total_templates': total_templates,
        'total_categories': total_categories,
        'completed_tests': completed_tests,

        # Daily stats
        'orders_today': orders_today,
        'completed_today': completed_today,
        'pending_today': pending_today,

        # Weekly stats
        'orders_week': orders_week,
        'completed_week': completed_week,

        # Monthly stats
        'orders_month': orders_month,
        'completed_month': completed_month,
        'orders_growth': orders_growth,
        'completed_growth': completed_growth,

        # Revenue
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,

        # Charts data
        'status_distribution': json.dumps(status_chart_data),
        'category_distribution': json.dumps(category_chart_data),
        'popular_tests': popular_tests_data,
        'daily_trends': json.dumps(daily_trends),
        'monthly_trends': json.dumps(monthly_trends),
        'source_distribution': json.dumps(source_chart_data),

        # Other stats
        'avg_processing_hours': avg_processing_hours,
        'recent_orders': recent_orders,

        # Pending tasks
        'pending_collection': pending_collection,
        'pending_processing': pending_processing,
        'pending_verification': pending_verification,
    }

    return render(request, 'scan/dashboard.html', context)

