import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Set page config
st.set_page_config(page_title="OGC Analytics Dashboard", layout="wide")

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Initialize session state for filter tracking
if 'filters_active' not in st.session_state:
    st.session_state.filters_active = False

def check_password():
    if st.session_state.authenticated:
        return True
    
    password = st.sidebar.text_input("Enter Password", type="password")
    if password == "OGC2025AI":
        st.session_state.authenticated = True
        return True
    elif password:
        st.sidebar.error("Incorrect password")
    return False

# Function to determine the actual company revenue band
def get_company_revenue_band(revenue_text):
    """Map company revenue text to standardized bands"""
    try:
        if pd.isna(revenue_text) or not revenue_text:
            return "Unknown"
            
        # Convert to lowercase for case-insensitive matching
        text = str(revenue_text).lower()
        
        if "< $10m" in text or "under $10m" in text:
            return "< $10M"
        elif "$10m - $30m" in text:
            return "$10M - $30M"
        elif "$30m - $100m" in text:
            return "$30M - $100M"
        elif "$100m - $500m" in text:
            return "$100M - $500M"
        elif "$500m - $1b" in text:
            return "$500M - $1B"
        elif "$1b - $3b" in text:
            return "$1B - $3B"
        elif "$3b - $10b" in text:
            return "$3B - $10B"
        elif "> $10 billion" in text or "> $10b" in text:
            return "> $10B"
        else:
            return "Unknown"
    except Exception as e:
        print(f"Error processing company revenue band {revenue_text}: {str(e)}")
        return "Unknown"

# Function to calculate fee band (based on fees paid to the firm)
def get_fee_band(six_month_revenue):
    try:
        if pd.isna(six_month_revenue) or six_month_revenue == 0:
            return "Under $50K"
            
        # Annualize the revenue (multiply by 2 since we have 6 months of data)
        annual_fees = float(six_month_revenue) * 2
        
        if annual_fees <= 50000:
            return "Under $50K"
        elif annual_fees <= 100000:
            return "$50K-$100K"
        elif annual_fees <= 250000:
            return "$100K-$250K"
        elif annual_fees <= 500000:
            return "$250K-$500K"
        elif annual_fees <= 1000000:
            return "$500K-$1M"
        elif annual_fees <= 2000000:
            return "$1M-$2M"
        elif annual_fees <= 5000000:
            return "$2M-$5M"
        elif annual_fees <= 10000000:
            return "$5M-$10M"
        else:
            return "Over $10M"
    except Exception as e:
        print(f"Error processing fee band {six_month_revenue}: {str(e)}")
        return "Under $50K"

# Function to load data
@st.cache_data
def load_data():
    try:
        # Load main data files
        six_months = pd.read_csv('SIX_FULL_MOS.csv')
        attorneys = pd.read_csv('ATTORNEY_PG_AND_HRS.csv')
        attorney_clients = pd.read_csv('ATTORNEY_CLIENTS.csv', skiprows=1)
        utilization = pd.read_csv('UTILIZATION.csv', skiprows=2)
        pivot_source = pd.read_csv('PIVOT_SOURCE_1.csv', skiprows=1)
        
        # Convert date columns
        for date_col in ['Service Date', 'Invoice Date']:
            if date_col in six_months.columns:
                six_months[date_col] = pd.to_datetime(six_months[date_col], errors='coerce')
        
        # Clean up attorney data
        attorneys = attorneys[attorneys['Attorney pipeline stage'] == '🟢 Active']
        
        # Add Fee Band (based on fees paid to firm)
        client_revenue = six_months.groupby('Client Name')['Amount'].sum().reset_index()
        client_revenue['Fee Band'] = client_revenue['Amount'].apply(get_fee_band)
        
        # Assign Company Revenue Band (based on client's actual company revenue)
        # This would be based on a column like 'Company Revenue' or similar
        if 'Company Revenue' in six_months.columns:
            client_company_revenue = six_months.groupby('Client Name')['Company Revenue'].first().reset_index()
            client_company_revenue['Revenue Band'] = client_company_revenue['Company Revenue'].apply(get_company_revenue_band)
        else:
            # If no company revenue data exists, create placeholder
            client_company_revenue = pd.DataFrame({'Client Name': client_revenue['Client Name'].unique()})
            client_company_revenue['Revenue Band'] = 'Unknown'
        
        # Add Fee type column if it doesn't exist (Time/Fixed Fee/All)
        if 'Fee Type' not in six_months.columns:
            # Try to determine fee type based on other columns
            # e.g., if Rate exists and is non-zero, it's likely Time-based
            if 'Rate' in six_months.columns:
                six_months['Fee Type'] = six_months.apply(
                    lambda row: 'Time' if pd.notnull(row['Rate']) and row['Rate'] > 0 else 'Fixed', 
                    axis=1
                )
            else:
                # Default all to Time if no way to determine
                six_months['Fee Type'] = 'Time'
        
        # Filter out expenses if indicated in the data
        if 'Transaction Type' in six_months.columns:
            six_months = six_months[six_months['Transaction Type'] != 'Expense']
        elif 'Activity Type' in six_months.columns:
            six_months = six_months[six_months['Activity Type'] != 'Expense']
            
        # Merge fee bands and revenue bands back to main dataset
        six_months = six_months.merge(
            client_revenue[['Client Name', 'Fee Band']],
            on='Client Name',
            how='left'
        )
        
        six_months = six_months.merge(
            client_company_revenue[['Client Name', 'Revenue Band']],
            on='Client Name',
            how='left'
        )
        
        # Merge attorney target hours
        six_months = six_months.merge(
            attorneys[['Attorney Name', '🎚️ Target Hours / Month']],
            left_on='Associated Attorney',
            right_on='Attorney Name',
            how='left'
        )
        
        six_months['Target Hours'] = six_months['🎚️ Target Hours / Month']
        
        # Ensure we have a clean billable hours column
        if 'Activity Type' in six_months.columns:
            # Create a clean case-insensitive Activity Type for filtering
            six_months['Activity Type Clean'] = six_months['Activity Type'].str.strip().str.lower()
            
            # Mark billable rows
            six_months['Is Billable'] = six_months['Activity Type Clean'].isin(['billable', 'bill', 'time'])
        else:
            # Default all to billable if no way to determine
            six_months['Is Billable'] = True
        
        return six_months, attorneys, attorney_clients, utilization, pivot_source
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None, None, None

# Function to clear all filters
def clear_filters():
    # Reset all filter session state variables
    st.session_state.filters_active = False
    if 'selected_bands' in st.session_state:
        st.session_state.selected_bands = []
    if 'selected_attorneys' in st.session_state:
        st.session_state.selected_attorneys = []
    if 'selected_practices' in st.session_state:
        st.session_state.selected_practices = []
    if 'selected_matters' in st.session_state:
        st.session_state.selected_matters = []
    if 'selected_clients' in st.session_state:
        st.session_state.selected_clients = []
    if 'selected_fee_types' in st.session_state:
        st.session_state.selected_fee_types = []
    if 'date_range' in st.session_state:
        st.session_state.date_range = None

# Main app logic
if check_password():
    # Remove the password input field after authentication
    if st.session_state.authenticated:
        st.sidebar.empty()
    
    # Load data
    six_months_df, attorneys_df, attorney_clients_df, utilization_df, pivot_source_df = load_data()

    if six_months_df is not None:
        # Sidebar filters
        st.sidebar.header('Filters')

        # Date filter
        try:
            min_date = six_months_df['Service Date'].min()
            max_date = six_months_df['Service Date'].max()
            
            # Store date range in session state if not already set
            if 'date_range' not in st.session_state:
                st.session_state.date_range = (min_date.date(), max_date.date())
                
            date_range = st.sidebar.date_input(
                "Date Range",
                value=st.session_state.date_range,
                min_value=min_date.date(),
                max_value=max_date.date()
            )
            st.session_state.date_range = date_range
        except:
            st.error("Error with date range")
            date_range = None

        # Fee Type filter (Time/Fixed Fee/All)
        fee_types = ['Time', 'Fixed Fee', 'All']
        if 'selected_fee_types' not in st.session_state:
            st.session_state.selected_fee_types = []
        selected_fee_types = st.sidebar.multiselect('Fee Types', fee_types, st.session_state.selected_fee_types)
        st.session_state.selected_fee_types = selected_fee_types

        # Revenue Band filter (Company's actual revenue)
        revenue_bands = [
            "< $10M", "$10M - $30M", "$30M - $100M", "$100M - $500M",
            "$500M - $1B", "$1B - $3B", "$3B - $10B", "> $10B", "Unknown"
        ]
        if 'selected_revenue_bands' not in st.session_state:
            st.session_state.selected_revenue_bands = []
        selected_revenue_bands = st.sidebar.multiselect('Company Revenue Bands', revenue_bands, st.session_state.selected_revenue_bands)
        st.session_state.selected_revenue_bands = selected_revenue_bands

        # Fee Band filter (fees paid to firm)
        fee_bands = [
            "Under $50K", "$50K-$100K", "$100K-$250K", "$250K-$500K",
            "$500K-$1M", "$1M-$2M", "$2M-$5M", "$5M-$10M", "Over $10M"
        ]
        if 'selected_fee_bands' not in st.session_state:
            st.session_state.selected_fee_bands = []
        selected_fee_bands = st.sidebar.multiselect('Fee Bands', fee_bands, st.session_state.selected_fee_bands)
        st.session_state.selected_fee_bands = selected_fee_bands

        # Attorney filter
        attorneys = sorted(six_months_df['Associated Attorney'].dropna().unique())
        if 'selected_attorneys' not in st.session_state:
            st.session_state.selected_attorneys = []
        selected_attorneys = st.sidebar.multiselect('Attorneys', attorneys, st.session_state.selected_attorneys)
        st.session_state.selected_attorneys = selected_attorneys

        # Practice Group filter
        practice_groups = sorted(six_months_df['PG'].dropna().unique())
        if 'selected_practices' not in st.session_state:
            st.session_state.selected_practices = []
        selected_practices = st.sidebar.multiselect('Practice Groups', practice_groups, st.session_state.selected_practices)
        st.session_state.selected_practices = selected_practices

        # Client filter
        clients = sorted(six_months_df['Client Name'].dropna().unique())
        if 'selected_clients' not in st.session_state:
            st.session_state.selected_clients = []
        selected_clients = st.sidebar.multiselect('Clients', clients, st.session_state.selected_clients)
        st.session_state.selected_clients = selected_clients

        # Matter filter
        matters = sorted(six_months_df['Matter Name'].dropna().unique())
        if 'selected_matters' not in st.session_state:
            st.session_state.selected_matters = []
        selected_matters = st.sidebar.multiselect('Matters', matters, st.session_state.selected_matters)
        st.session_state.selected_matters = selected_matters

        # Clear Filters button
        if st.sidebar.button('Clear All Filters'):
            clear_filters()

        # Apply filters
        filtered_df = six_months_df.copy()
        
        # Check if any filters are active
        st.session_state.filters_active = (
            (date_range and len(date_range) == 2) or 
            selected_fee_types or 
            selected_revenue_bands or 
            selected_fee_bands or
            selected_attorneys or 
            selected_practices or
            selected_clients or
            selected_matters
        )
        
        if date_range and len(date_range) == 2:
            filtered_df = filtered_df[
                (filtered_df['Service Date'].dt.date >= date_range[0]) &
                (filtered_df['Service Date'].dt.date <= date_range[1])
            ]
        
        if selected_fee_types:
            if 'All' not in selected_fee_types:
                if 'Time' in selected_fee_types and 'Fixed Fee' in selected_fee_types:
                    # Both selected, no filtering needed
                    pass
                elif 'Time' in selected_fee_types:
                    filtered_df = filtered_df[filtered_df['Fee Type'] == 'Time']
                elif 'Fixed Fee' in selected_fee_types:
                    filtered_df = filtered_df[filtered_df['Fee Type'] == 'Fixed']
            
        if selected_revenue_bands:
            filtered_df = filtered_df[filtered_df['Revenue Band'].isin(selected_revenue_bands)]
            
        if selected_fee_bands:
            filtered_df = filtered_df[filtered_df['Fee Band'].isin(selected_fee_bands)]
            
        if selected_attorneys:
            filtered_df = filtered_df[filtered_df['Associated Attorney'].isin(selected_attorneys)]
        
        if selected_practices:
            filtered_df = filtered_df[filtered_df['PG'].isin(selected_practices)]
            
        if selected_clients:
            filtered_df = filtered_df[filtered_df['Client Name'].isin(selected_clients)]
        
        if selected_matters:
            filtered_df = filtered_df[filtered_df['Matter Name'].isin(selected_matters)]

        # Status indicator for active filters
        if st.session_state.filters_active:
            st.sidebar.warning('Filters are active')
        else:
            st.sidebar.success('No filters applied')

        # Tabs
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "Overview", "Client Analysis", "Fee Bands", "Client Segmentation", 
            "Attorney Analysis", "Practice Areas", "Trending", "Attorney Fx"
        ])

        with tab1:
            st.header("Overview")
            
            # Key Performance Indicators
            col1, col2, col3, col4 = st.columns(4)
            
            # Monthly bills generated
            monthly_bills = filtered_df.groupby(pd.Grouper(key='Invoice Date', freq='M'))['Invoice Number'].nunique()
            with col1:
                st.metric(
                    "Monthly Bills Generated", 
                    f"{monthly_bills.iloc[-1] if not monthly_bills.empty else 0:,.0f}",
                    help="Number of unique bills generated in the last month"
                )
            
            # Total billable hours - Fix to use Is Billable flag
            total_billable = filtered_df[filtered_df['Is Billable']]['Hours'].sum()
            total_hours = filtered_df['Hours'].sum()
            
            with col2:
                st.metric(
                    "Total Billable Hours", 
                    f"{total_billable:,.1f}",
                    delta=f"{(total_billable/total_hours*100):.1f}% of total" if total_hours > 0 else "0%",
                    help="Total billable hours and percentage of total hours"
                )
            
            # Average rate
            avg_rate = filtered_df['Rate'].mean()
            with col3:
                st.metric(
                    "Average Rate", 
                    f"${avg_rate:,.2f}",
                    help="Average hourly rate across all matters"
                )
            
            # Total fees (excluding expenses)
            total_fees = filtered_df['Amount'].sum()
            with col4:
                st.metric(
                    "Total Fees", 
                    f"${total_fees:,.2f}",
                    help="Total fees from all matters (excluding expenses)"
                )
            
            # Monthly trends
            st.subheader("Monthly Performance Trends")
            
            # Format dates properly for display
            monthly_metrics = filtered_df.groupby(pd.Grouper(key='Service Date', freq='M')).agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Invoice Number': 'nunique'
            }).reset_index()
            
            # Create formatted date string for display
            monthly_metrics['Month'] = monthly_metrics['Service Date'].dt.strftime('%b %Y')
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=monthly_metrics['Month'],
                y=monthly_metrics['Hours'],
                name='Hours',
                yaxis='y'
            ))
            
            fig.add_trace(go.Scatter(
                x=monthly_metrics['Month'],
                y=monthly_metrics['Amount'],
                name='Fees',
                yaxis='y2',
                line=dict(color='red')
            ))
            
            fig.update_layout(
                title='Monthly Hours and Fees',
                yaxis=dict(title='Hours', side='left'),
                yaxis2=dict(title='Fees', side='right', overlaying='y', tickprefix="$", tickformat=",.0f"),
                showlegend=True,
                xaxis=dict(type='category')  # Use category type for proper ordering
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # Utilization metrics - use individual targets
            st.subheader("Attorney Utilization Overview")
            
            # Group by attorney and calculate utilization against their own targets
            attorney_util = filtered_df.groupby('Associated Attorney').agg({
                'Hours': 'sum',
                'Target Hours': 'first'
            }).reset_index()
            
            # Filter out attorneys with 0 or 1 hours
            attorney_util = attorney_util[(attorney_util['Hours'] > 1) & (~attorney_util['Target Hours'].isna())]
            
            # Calculate percentage of target
            attorney_util['Utilization Rate'] = attorney_util.apply(
                lambda x: (x['Hours'] / (x['Target Hours'] * 6) * 100) if pd.notnull(x['Target Hours']) and x['Target Hours'] > 0 else 0,
                axis=1
            )
            
            # Sort by utilization rate
            attorney_util = attorney_util.sort_values('Utilization Rate', ascending=False)
            
            # Create the chart with individual targets
            fig = px.bar(
                attorney_util,
                x='Associated Attorney',
                y='Utilization Rate',
                title='Attorney Utilization Rates (% of Individual Target)'
            )
            
            # Add a red line at 100% for reference
            fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% Target")
            
            # Add click-through functionality
            fig.update_traces(
                hovertemplate="<b>%{x}</b><br>Utilization: %{y:.1f}%<br>Click for details"
            )
            
            # Display the chart
            st.plotly_chart(fig, use_container_width=True)
            
            # Add informational text for click-through
            st.info("Click on an attorney's bar to view their detailed metrics")

        with tab2:
            st.header("Client Analysis")
            
            # Client metrics
            clients_df = filtered_df.groupby('Client Name').agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Matter Name': 'nunique',
                'Invoice Number': 'nunique',
                'Revenue Band': 'first',
                'Fee Band': 'first'
            }).reset_index()
            
            # Calculate averages
            avg_revenue_per_client = clients_df['Amount'].mean()
            avg_hours_per_client = clients_df['Hours'].mean()
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Total Clients",
                    f"{len(clients_df):,}",
                    help="Number of unique clients"
                )
            
            with col2:
                st.metric(
                    "Avg Fees per Client",
                    f"${avg_revenue_per_client:,.2f}",
                    help="Average fees generated per client"
                )
            
            with col3:
                st.metric(
                    "Avg Hours per Client",
                    f"{avg_hours_per_client:.1f}",
                    help="Average hours spent per client"
                )
            
            # Top clients by revenue
            st.subheader("Top Clients by Fees")
            
            # Color-code by Revenue Band consistently
            top_clients = clients_df.nlargest(10, 'Amount')
            
            fig = px.bar(
                top_clients,
                x='Client Name',
                y='Amount',
                color='Revenue Band',
                title='Top 10 Clients by Fees',
                labels={'Amount': 'Fees ($)', 'Client Name': 'Client'}
            )
            
            # Update to make clickable for drill-in
            fig.update_traces(
                hovertemplate="<b>%{x}</b><br>Fees: $%{y:,.2f}<br>Click for details"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add informational text for click-through
            st.info("Click on a client's bar to filter dashboard to that client")
            
            # Client hours distribution
            st.subheader("Client Hours Distribution")
            fig = px.histogram(
                clients_df,
                x='Hours',
                nbins=50,
                color='Revenue Band',
                title='Distribution of Hours Across Clients'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Detailed client metrics
            st.subheader("Detailed Client Metrics")
            
            # Hide index column
            detailed_clients = clients_df.sort_values('Amount', ascending=False).reset_index(drop=True)
            
            st.dataframe(
                detailed_clients
                .style.format({
                    'Amount': '${:,.2f}',
                    'Hours': '{:,.1f}'
                }),
                use_container_width=True,
                height=400
            )

        with tab3:
            st.header("Fee Band Analysis")
            
            # Calculate fee band metrics
            fee_band_metrics = filtered_df.groupby('Fee Band').agg({
                'Client Name': 'nunique',
                'Amount': 'sum',
                'Hours': 'sum',
                'Matter Name': 'nunique',
                'Associated Attorney': 'nunique'
            }).reset_index()
            
            # Calculate percentages
            total_clients = fee_band_metrics['Client Name'].sum()
            total_fees = fee_band_metrics['Amount'].sum()
            
            fee_band_metrics['Client %'] = (fee_band_metrics['Client Name'] / total_clients * 100).round(1)
            fee_band_metrics['Fee %'] = (fee_band_metrics['Amount'] / total_fees * 100).round(1)
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(
                    fee_band_metrics,
                    values='Client Name',
                    names='Fee Band',
                    title='Client Distribution by Fee Band'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.pie(
                    fee_band_metrics,
                    values='Amount',
                    names='Fee Band',
                    title='Fee Distribution by Band'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Also show the company revenue bands
            st.subheader("Company Revenue Band Analysis")
            
            # Calculate company revenue band metrics
            rev_band_metrics = filtered_df.groupby('Revenue Band').agg({
                'Client Name': 'nunique',
                'Amount': 'sum',
                'Hours': 'sum',
                'Matter Name': 'nunique',
                'Associated Attorney': 'nunique'
            }).reset_index()
            
            # Calculate percentages
            rev_band_metrics['Client %'] = (rev_band_metrics['Client Name'] / total_clients * 100).round(1)
            rev_band_metrics['Fee %'] = (rev_band_metrics['Amount'] / total_fees * 100).round(1)
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(
                    rev_band_metrics,
                    values='Client Name',
                    names='Revenue Band',
                    title='Client Distribution by Company Revenue Band'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.pie(
                    rev_band_metrics,
                    values='Amount',
                    names='Revenue Band',
                    title='Fee Distribution by Company Revenue Band'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Detailed metrics table for fee bands
            st.subheader("Fee Band Details")
            formatted_metrics = fee_band_metrics.style.format({
                'Amount': '${:,.2f}',
                'Client %': '{:.1f}%',
                'Fee %': '{:.1f}%',
                'Hours': '{:,.1f}'
            })
            st.dataframe(formatted_metrics, use_container_width=True)
            
            # Top clients in each band
            st.subheader("Top Clients by Revenue Band")
            for band in sorted(filtered_df['Revenue Band'].unique()):
                band_clients = filtered_df[filtered_df['Revenue Band'] == band]
                if not band_clients.empty:
                    st.write(f"**{band}**")
                    top_clients = band_clients.groupby('Client Name')['Amount'].sum()\
                        .sort_values(ascending=False)\
                        .reset_index()
                    top_clients['Amount'] = top_clients['Amount'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(top_clients, use_container_width=True, height=200)

        with tab4:
            st.header("Client Segmentation")
        
        try:
        # Calculate comprehensive client metrics
        client_metrics = filtered_df.groupby('Client Name').agg({
            'Amount': ['sum', 'mean'],
            'Hours': ['sum', 'mean'],
            'Matter Name': 'nunique',
            'Invoice Number': 'nunique',
            'PG': lambda x: x.iloc[0] if not x.empty else None,
            'Service Date': ['min', 'max'],
            'Revenue Band': 'first',
            'Fee Band': 'first'
        }).reset_index()

        # Flatten column names
        client_metrics.columns = ['Client Name', 'Total Fees', 'Avg Fees', 
                                'Total Hours', 'Avg Hours', 'Matter Count',
                                'Invoice Count', 'Practice Area', 'First Service', 'Last Service',
                                'Revenue Band', 'Fee Band']
        
        # Calculate retention period
        client_metrics['Retention Days'] = (
            client_metrics['Last Service'] - client_metrics['First Service']
        ).dt.days
        
        # Calculate Daily Fees
        client_metrics['Daily Fees'] = client_metrics['Total Fees'] / \
            client_metrics['Retention Days'].clip(lower=1)
        client_metrics['Projected Annual Value'] = client_metrics['Daily Fees'] * 365
        
        # Revenue band distribution - by actual company revenue
        st.subheader("Client Distribution")
        col1, col2 = st.columns(2)
        
        with col1:
            revenue_dist = client_metrics['Revenue Band'].value_counts()
            fig = px.pie(
                values=revenue_dist.values,
                names=revenue_dist.index,
                title="Clients by Company Revenue Band"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            revenue_total = client_metrics.groupby('Revenue Band')['Total Fees'].sum()
            fig = px.pie(
                values=revenue_total.values,
                names=revenue_total.index,
                title="Fees by Company Revenue Band"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Practice Area Distribution
        st.subheader("Practice Area Analysis")
        
        # Group by practice area and company revenue band
        practice_data = filtered_df.groupby(['PG', 'Revenue Band']).agg({
            'Amount': 'sum',
            'Client Name': 'nunique'
        }).reset_index()
        
        # Create stacked bar chart similar to Scale's
        fig = px.bar(
            practice_data,
            x='PG',
            y='Amount',
            color='Revenue Band',
            title='Fees by Practice Area and Company Revenue Band',
            labels={'PG': 'Practice Area', 'Amount': 'Fees ($)'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Calculate LTV metrics
        st.subheader("Client Lifetime Value Analysis")
        
        # Get most recent date from the data
        recent_date = filtered_df['Service Date'].max()
        
        # Calculate LTV metrics (changed from Revenue to Fees)
        client_metrics['Monthly Fees'] = client_metrics['Total Fees'] / \
            (client_metrics['Retention Days'] / 30).clip(lower=1)
        client_metrics['Avg Monthly Fees'] = client_metrics['Monthly Fees']
        
        # Estimate churn rate based on activity
        client_metrics['Churn Probability'] = np.where(
            (recent_date - client_metrics['Last Service']).dt.days > 90,
            0.8,  # High churn probability for inactive clients
            0.2   # Lower churn probability for active clients
        )
        
        # LTV = Average Monthly Fees / Churn Rate * 12 months
        client_metrics['LTV'] = (client_metrics['Avg Monthly Fees'] / \
            client_metrics['Churn Probability']) * 12
        
        # Calculate value band metrics by Company Revenue Band
        value_metrics = client_metrics.groupby('Revenue Band').agg({
            'Client Name': 'count',
            'Total Fees': ['sum', 'mean'],
            'Monthly Fees': 'mean',
            'LTV': ['mean', 'median', 'max'],
            'Retention Days': ['mean', 'median'],
            'Matter Count': 'mean'
        }).round(2)
        
        # Sort the index to display highest value bands on the left
        ordered_bands = [
            "> $10B", "$3B - $10B", "$1B - $3B", "$500M - $1B", 
            "$100M - $500M", "$30M - $100M", "$10M - $30M", "< $10M", "Unknown"
        ]
        value_metrics = value_metrics.reindex(
            [band for band in ordered_bands if band in value_metrics.index]
        )
        
        # Flatten column names
        value_metrics.columns = [
            'Client Count', 'Total Fees', 'Avg Fees', 'Avg Monthly Fees',
            'Avg LTV', 'Median LTV', 'Max LTV', 'Avg Retention', 'Median Retention',
            'Avg Matters'
        ]
        
        # Add fee concentration
        total_fees = value_metrics['Total Fees'].sum()
        value_metrics['Fee Concentration (%)'] = \
            (value_metrics['Total Fees'] / total_fees * 100).round(1)
        
        # Display value metrics
        formatted_metrics = value_metrics.style.format({
            'Total Fees': '${:,.2f}',
            'Avg Fees': '${:,.2f}',
            'Avg Monthly Fees': '${:,.2f}',
            'Avg LTV': '${:,.2f}',
            'Median LTV': '${:,.2f}',
            'Max LTV': '${:,.2f}',
            'Fee Concentration (%)': '{:.1f}%'
        })
        
        st.dataframe(formatted_metrics, use_container_width=True)
        
        # LTV Analysis
        st.subheader("Lifetime Value Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # LTV by Revenue Band (sorted by value)
            fig = px.bar(
                x=value_metrics.index,
                y=value_metrics['Avg LTV'],
                title="Average Lifetime Value by Company Revenue Band",
                labels={'x': 'Revenue Band', 'y': 'Average LTV ($)'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Fee Concentration
            fig = px.pie(
                values=value_metrics['Fee Concentration (%)'],
                names=value_metrics.index,
                title="Fee Concentration by Company Revenue Band"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Top LTV Clients - show all clients, not just top 10
        st.subheader("All Clients by Lifetime Value")
        all_ltv_clients = client_metrics.sort_values('LTV', ascending=False)[
            ['Client Name', 'Revenue Band', 'LTV', 'Total Fees', 'Retention Days']
        ].reset_index(drop=True)
        
        st.dataframe(
            all_ltv_clients.style.format({
                'LTV': '${:,.2f}',
                'Total Fees': '${:,.2f}',
                'Retention Days': '{:,.0f}'
            }),
            use_container_width=True,
            height=400
        )
        
    except Exception as e:
        st.error(f"Error in client segmentation analysis: {str(e)}")

with tab5:
    st.header("Attorney Analysis")
    
    try:
        # Attorney productivity metrics
        attorney_metrics = filtered_df.groupby('Associated Attorney').agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Client Name': 'nunique',
            'Matter Name': 'nunique',
            'Target Hours': 'first',
            'PG': 'first'
        }).reset_index()
        
        # Filter out attorneys with 1 or 0 hours
        attorney_metrics = attorney_metrics[attorney_metrics['Hours'] > 1]
        
        # Calculate utilization rate based on individual target
        # Assuming target hours is monthly, and we have 6 months of data
        attorney_metrics['Utilization Rate'] = attorney_metrics.apply(
            lambda x: (x['Hours'] / (x['Target Hours'] * 6) * 100) 
            if pd.notnull(x['Target Hours']) and x['Target Hours'] > 0 
            else 0,
            axis=1
        )
            
        # Calculate average hourly rate
        attorney_metrics['Avg Hourly Rate'] = attorney_metrics['Amount'] / \
            attorney_metrics['Hours']
        
        # Display metrics
        st.subheader("Attorney Performance Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Average Hours per Attorney",
                f"{attorney_metrics['Hours'].mean():.1f}",
                help="Average hours worked per attorney"
            )
        
        with col2:
            st.metric(
                "Average Fees per Attorney",
                f"${attorney_metrics['Amount'].mean():,.2f}",
                help="Average fees generated per attorney"
            )
        
        with col3:
            st.metric(
                "Average Clients per Attorney",
                f"{attorney_metrics['Client Name'].mean():.1f}",
                help="Average number of clients per attorney"
            )
        
        with col4:
            st.metric(
                "Average Utilization Rate",
                f"{attorney_metrics['Utilization Rate'].mean():.1f}%",
                help="Average utilization rate across attorneys"
            )
        
        # Monthly Attorney Hours vs Target
        st.subheader("Monthly Attorney Hours vs Target")
        
        # Get monthly hours by attorney
        monthly_attorney_hours = filtered_df.groupby([
            'Associated Attorney', 
            pd.Grouper(key='Service Date', freq='M')
        ])['Hours'].sum().reset_index()
        
        # Merge with attorney metrics to get target
        monthly_attorney_hours = monthly_attorney_hours.merge(
            attorney_metrics[['Associated Attorney', 'Target Hours']],
            on='Associated Attorney',
            how='left'
        )
        
        # Calculate percentage of monthly target
        monthly_attorney_hours['Target Percentage'] = (
            monthly_attorney_hours['Hours'] / 
            monthly_attorney_hours['Target Hours'] * 100
        ).clip(upper=200)  # Cap at 200% for better visualization
        
        # Format month for display
        monthly_attorney_hours['Month'] = monthly_attorney_hours['Service Date'].dt.strftime('%b %Y')
        
        # Top 10 attorneys by hours
        top_hours_attorneys = attorney_metrics.nlargest(10, 'Hours')['Associated Attorney'].tolist()
        
        # Filter to top attorneys for this visualization
        top_monthly_data = monthly_attorney_hours[
            monthly_attorney_hours['Associated Attorney'].isin(top_hours_attorneys)
        ]
        
        # Create heatmap
        fig = px.density_heatmap(
            top_monthly_data,
            x='Month',
            y='Associated Attorney',
            z='Target Percentage',
            title='Monthly Hours as Percentage of Target',
            labels={'Target Percentage': '% of Target'},
            color_continuous_scale='RdYlGn',  # Red to Yellow to Green
            range_color=[0, 150]  # 0% to 150% of target
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Top performers by Hours
        st.subheader("Top Performing Attorneys by Hours")
        
        # By hours, all attorneys
        hours_by_attorney = attorney_metrics.sort_values('Hours', ascending=False)
        
        # Group by Practice Group for coloring
        hours_by_attorney_pg = hours_by_attorney.copy()
        
        fig = px.bar(
            hours_by_attorney_pg,
            x='Associated Attorney',
            y='Hours',
            color='PG',
            title='Attorneys by Hours',
            labels={'Associated Attorney': 'Attorney', 'Hours': 'Total Hours'}
        )
        
        # Add click-through functionality
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>Hours: %{y:.1f}<br>Click for client details"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Top performers by Fees
        st.subheader("Top Performing Attorneys by Fees")
        
        # By fees, top 10
        top_fees = attorney_metrics.nlargest(10, 'Amount')
        
        fig = px.bar(
            top_fees,
            x='Associated Attorney',
            y='Amount',
            color='PG',
            title='Top 10 Attorneys by Fees',
            labels={'Associated Attorney': 'Attorney', 'Amount': 'Total Fees ($)'}
        )
        
        # Add click-through functionality
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>Fees: $%{y:,.2f}<br>Click for client details"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Attorney clients section
        st.subheader("Attorney Client Breakdown")
        
        # Create attorney selector
        selected_attorney = st.selectbox(
            "Select Attorney to View Clients",
            attorney_metrics['Associated Attorney'].sort_values().tolist()
        )
        
        if selected_attorney:
            # Get clients for selected attorney
            attorney_clients = filtered_df[
                filtered_df['Associated Attorney'] == selected_attorney
            ].groupby('Client Name').agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Matter Name': 'nunique',
                'Revenue Band': 'first'
            }).reset_index()
            
            # Show client breakdown
            if not attorney_clients.empty:
                # By hours
                fig = px.bar(
                    attorney_clients.sort_values('Hours', ascending=False),
                    x='Client Name',
                    y='Hours',
                    color='Revenue Band',
                    title=f'Clients for {selected_attorney} by Hours'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # By fees
                fig = px.bar(
                    attorney_clients.sort_values('Amount', ascending=False),
                    x='Client Name',
                    y='Amount',
                    color='Revenue Band',
                    title=f'Clients for {selected_attorney} by Fees'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Table with details
                st.dataframe(
                    attorney_clients.sort_values('Amount', ascending=False)
                    .style.format({
                        'Hours': '{:,.1f}',
                        'Amount': '${:,.2f}'
                    }),
                    use_container_width=True
                )
            else:
                st.info(f"No client data available for {selected_attorney}")
        
        # Detailed metrics table for all attorneys
        st.subheader("Detailed Attorney Metrics")
        st.dataframe(
            attorney_metrics.sort_values('Amount', ascending=False)
            .style.format({
                'Hours': '{:,.1f}',
                'Amount': '${:,.2f}',
                'Utilization Rate': '{:,.1f}%',
                'Avg Hourly Rate': '${:,.2f}'
            }),
            use_container_width=True,
            height=400
        )
        
    except Exception as e:
        st.error(f"Error in attorney analysis: {str(e)}")

with tab6:
    st.header("Practice Areas")
    
    try:
        if 'PG' in filtered_df.columns:
            # Practice area metrics
            practice_metrics = filtered_df.groupby('PG').agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Matter Name': 'nunique',
                'Client Name': 'nunique',
                'Associated Attorney': 'nunique'
            }).reset_index()
            
            # Calculate derived metrics
            practice_metrics['Avg Rate'] = practice_metrics['Amount'] / practice_metrics['Hours']
            practice_metrics['Revenue per Client'] = practice_metrics['Amount'] / \
                practice_metrics['Client Name']
            
            # Overview metrics
            st.subheader("Practice Area Overview")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Practice area distribution by hours
                fig = px.pie(
                    practice_metrics,
                    values='Hours',
                    names='PG',
                    title='Hours by Practice Area'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Practice area distribution by revenue
                fig = px.pie(
                    practice_metrics,
                    values='Amount',
                    names='PG',
                    title='Fees by Practice Area'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Practice area revenue distribution by revenue band
            st.subheader("Practice Area Performance by Revenue Band")
            
            # Create stacked bar chart showing revenue bands within each practice area
            practice_band_metrics = filtered_df.groupby(['PG', 'Revenue Band']).agg({
                'Amount': 'sum',
                'Hours': 'sum'
            }).reset_index()
            
            fig = px.bar(
                practice_band_metrics,
                x='PG',
                y='Amount',
                color='Revenue Band',
                title='Practice Area Fee Distribution by Company Revenue Band',
                labels={'PG': 'Practice Area', 'Amount': 'Fees ($)'}
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Practice area efficiency bubble chart (as requested by Ankita)
            st.subheader("Practice Area Efficiency Analysis")
            
            # Create bubble chart showing hours, fees, and client count
            fig = px.scatter(
                practice_metrics,
                x='Hours',
                y='Amount',
                size='Client Name',  # Bubble size based on client count
                color='PG',          # Color by practice area
                hover_name='PG',
                text='PG',
                size_max=60,         # Maximum bubble size
                title='Practice Area Efficiency (Hours vs Fees)',
                labels={
                    'Hours': 'Total Hours',
                    'Amount': 'Total Fees ($)',
                    'Client Name': 'Number of Clients'
                }
            )
            
            # Format y-axis as currency
            fig.update_layout(
                yaxis=dict(tickprefix="$", tickformat=",.0f")
            )
            
            # Add trendline for reference
            fig.update_layout(
                annotations=[
                    dict(
                        x=0.5,
                        y=1.05,
                        xref="paper",
                        yref="paper",
                        text="Bubble size represents number of clients",
                        showarrow=False
                    )
                ]
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Detailed metrics table
            st.subheader("Detailed Practice Area Metrics")
            st.dataframe(
                practice_metrics.sort_values('Amount', ascending=False)
                .style.format({
                    'Hours': '{:,.1f}',
                    'Amount': '${:,.2f}',
                    'Avg Rate': '${:,.2f}',
                    'Revenue per Client': '${:,.2f}'
                }),
                use_container_width=True
            )
            
    except Exception as e:
        st.error(f"Error in practice area analysis: {str(e)}")

with tab7:
    st.header("Trending")
    
    try:
        # Time series analysis
        monthly_trends = filtered_df.groupby([
            pd.Grouper(key='Service Date', freq='M'),
            'Revenue Band'
        ]).agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Invoice Number': 'nunique',
            'Matter Name': 'nunique',
            'Client Name': 'nunique'
        }).reset_index()
        
        # Format month for display
        monthly_trends['Month'] = monthly_trends['Service Date'].dt.strftime('%b %Y')
        
        # Calculate derived metrics
        monthly_trends['Avg Rate'] = monthly_trends['Amount'] / monthly_trends['Hours']
        
        # Overall trends - Monthly Hours by Revenue Band and Total Fees
        st.subheader("Monthly Performance Trends")
        
        # Hours and fees trend
        fig = go.Figure()
        
        # Revenue bands for consistent coloring
        revenue_bands = [
            "> $10B", "$3B - $10B", "$1B - $3B", "$500M - $1B", 
            "$100M - $500M", "$30M - $100M", "$10M - $30M", "< $10M", "Unknown"
        ]
        
        # Create color map
        colors = px.colors.qualitative.Set1
        color_map = {band: colors[i % len(colors)] for i, band in enumerate(revenue_bands)}
        
        # Add bars for hours by revenue band
        for band in revenue_bands:
            band_data = monthly_trends[monthly_trends['Revenue Band'] == band]
            if not band_data.empty:
                fig.add_trace(go.Bar(
                    x=band_data['Month'],
                    y=band_data['Hours'],
                    name=f'{band}',
                    marker_color=color_map.get(band, 'gray'),
                    yaxis='y'
                ))
        
        # Add line for total revenue
        revenue_by_month = monthly_trends.groupby('Month')['Amount'].sum().reset_index()
        fig.add_trace(go.Scatter(
            x=revenue_by_month['Month'],
            y=revenue_by_month['Amount'],
            name='Total Fees',
            yaxis='y2',
            line=dict(color='red', width=3)
        ))
        
        fig.update_layout(
            title='Monthly Hours by Revenue Band and Total Fees',
            yaxis=dict(title='Hours', side='left'),
            yaxis2=dict(title="Fees ($)", side="right", overlaying="y", tickprefix="$", tickformat=",.0f"),
            barmode="stack",
            showlegend=True,
            xaxis=dict(type="category"),  # Use category for proper ordering
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Client and matter trends by revenue band
        st.subheader("Client and Matter Trends")
        
        # Create multi-line chart
        fig = go.Figure()
        
        # Add lines for clients by revenue band
        for band in revenue_bands:
            band_data = monthly_trends[monthly_trends['Revenue Band'] == band]
            if not band_data.empty:
                fig.add_trace(go.Scatter(
                    x=band_data['Month'],
                    y=band_data['Client Name'],
                    name=f'Clients: {band}',
                    mode='lines+markers',
                    marker=dict(color=color_map.get(band, 'gray'))
                ))
        
        fig.update_layout(
            title='Monthly Active Clients by Revenue Band',
            yaxis=dict(title='Number of Clients'),
            xaxis=dict(title='Month', type='category'),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.5, xanchor='center', x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Average rate trend by revenue band
        st.subheader("Rate Trends")
        
        # Create multi-line chart for rates
        fig = go.Figure()
        
        # Add lines for average rate by revenue band
        for band in revenue_bands:
            band_data = monthly_trends[monthly_trends['Revenue Band'] == band]
            if not band_data.empty:
                fig.add_trace(go.Scatter(
                    x=band_data['Month'],
                    y=band_data['Avg Rate'],
                    name=f'Rate: {band}',
                    mode='lines+markers',
                    marker=dict(color=color_map.get(band, 'gray'))
                ))
        
        fig.update_layout(
            title="Monthly Average Rate by Revenue Band",
            yaxis=dict(title="Average Rate ($)", tickprefix="$", tickformat=",.0f"),
            xaxis=dict(title="Month", type="category"),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Custom trending view
        st.subheader("Custom Trending Analysis")
        
        # Create selector for metric
        trending_metric = st.selectbox(
            "Select Metric to Analyze",
            ["Hours", "Fees", "Clients", "Matters", "Average Rate"]
        )
        
        # Create selector for grouping
        trending_group = st.selectbox(
            "Group By",
            ["Revenue Band", "Practice Area", "Fee Type"]
        )
        
        # Map selection to actual column names
        metric_column = {
            "Hours": "Hours",
            "Fees": "Amount",
            "Clients": "Client Name",
            "Matters": "Matter Name",
            "Average Rate": "Avg Rate"
        }[trending_metric]
        
        group_column = {
            "Revenue Band": "Revenue Band",
            "Practice Area": "PG",
            "Fee Type": "Fee Type"
        }[trending_group]
        
        # Create custom groupby for trending analysis
        if group_column in filtered_df.columns:
            custom_trends = filtered_df.groupby([
                pd.Grouper(key='Service Date', freq='M'),
                group_column
            ]).agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Client Name': 'nunique',
                'Matter Name': 'nunique'
            }).reset_index()
            
            # Calculate average rate if needed
            if metric_column == "Avg Rate":
                custom_trends['Avg Rate'] = custom_trends['Amount'] / custom_trends['Hours']
            
            # Format month for display
            custom_trends['Month'] = custom_trends['Service Date'].dt.strftime('%b %Y')
            
            # Create the chart
            if metric_column in ["Client Name", "Matter Name"]:
                # For count metrics, use lines
                fig = px.line(
                    custom_trends,
                    x='Month',
                    y=metric_column,
                    color=group_column,
                    title=f'Monthly {trending_metric} by {trending_group}'
                )
            else:
                # For value metrics, use bars
                fig = px.bar(
                    custom_trends,
                    x='Month',
                    y=metric_column,
                    color=group_column,
                    title=f'Monthly {trending_metric} by {trending_group}'
                )
            
            # Format y-axis for currency if needed
            if metric_column in ["Amount", "Avg Rate"]:
                fig.update_layout(
                    yaxis=dict(tickprefix="$", tickformat=",.0f")
                )
            
            # Use category type for proper month ordering
            fig.update_layout(
                xaxis=dict(type='category')
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"The selected grouping '{trending_group}' is not available in the data")
        
    except Exception as e:
        st.error(f"Error in trending analysis: {str(e)}")

with tab8:
    st.header("Attorney Fx Analysis")
    
    try:
        # Load 9-box data for attorneys
        attorney_fx_data = pd.read_csv('paste.txt', delimiter='\t')
        
        # Ensure column names are correct
        if '9 Box' in attorney_fx_data.columns:
            # Clean up the data
            attorney_fx_data = attorney_fx_data[['Attorney Name', 'Practice Area (Primary)', 
                                                '9 Legal', '9 Client', '9 Box',
                                                '🎚️ Target Hours / Month',
                                                'Sector (Primary)']]
            
            # Merge with activity data if needed
            if not filtered_df.empty:
                attorney_activity = filtered_df.groupby('Associated Attorney').agg({
                    'Hours': 'sum',
                    'Amount': 'sum',
                    'Client Name': 'nunique'
                }).reset_index()
                
                # Rename for merge
                attorney_activity.rename(columns={'Associated Attorney': 'Attorney Name'}, inplace=True)
                
                # Merge the data
                attorney_fx_data = attorney_fx_data.merge(
                    attorney_activity,
                    on='Attorney Name',
                    how='left'
                )
                
                # Fill missing values for attorneys with no activity
                attorney_fx_data['Hours'] = attorney_fx_data['Hours'].fillna(0)
                attorney_fx_data['Amount'] = attorney_fx_data['Amount'].fillna(0)
                attorney_fx_data['Client Name'] = attorney_fx_data['Client Name'].fillna(0)
            
            # Sort options
            sort_options = ['9 Box (Highest to Lowest)', '9 Legal (Highest to Lowest)', 
                            '9 Client (Highest to Lowest)', 'Hours (Highest to Lowest)',
                            'Fees (Highest to Lowest)']
            
            sort_by = st.selectbox("Sort By:", sort_options)
            
            # Apply sorting
            if sort_by == '9 Box (Highest to Lowest)':
                attorney_fx_data = attorney_fx_data.sort_values('9 Box', ascending=False)
            elif sort_by == '9 Legal (Highest to Lowest)':
                attorney_fx_data = attorney_fx_data.sort_values('9 Legal', ascending=False)
            elif sort_by == '9 Client (Highest to Lowest)':
                attorney_fx_data = attorney_fx_data.sort_values('9 Client', ascending=False)
            elif sort_by == 'Hours (Highest to Lowest)':
                attorney_fx_data = attorney_fx_data.sort_values('Hours', ascending=False)
            elif sort_by == 'Fees (Highest to Lowest)':
                attorney_fx_data = attorney_fx_data.sort_values('Amount', ascending=False)
            
            # Filter options
            col1, col2 = st.columns(2)
            
            with col1:
                # Filter by 9 Box score
                box_scores = sorted(attorney_fx_data['9 Box'].unique(), reverse=True)
                selected_box_scores = st.multiselect(
                    "Filter by 9 Box Score:", 
                    box_scores,
                    default=box_scores
                )
            
            with col2:
                # Filter by Practice Area
                practice_areas = sorted(attorney_fx_data['Practice Area (Primary)'].unique())
                selected_practice_areas = st.multiselect(
                    "Filter by Practice Area:",
                    practice_areas,
                    default=[]
                )
            
            # Apply filters
            filtered_fx_data = attorney_fx_data.copy()
            
            if selected_box_scores:
                filtered_fx_data = filtered_fx_data[filtered_fx_data['9 Box'].isin(selected_box_scores)]
                
            if selected_practice_areas:
                filtered_fx_data = filtered_fx_data[
                    filtered_fx_data['Practice Area (Primary)'].isin(selected_practice_areas)
                ]
            
            # Create 9-box matrix visualization
            st.subheader("Attorney 9-Box Matrix")
            
            # Create a scatter plot for the 9-box
            fig = px.scatter(
                filtered_fx_data,
                x='9 Client',
                y='9 Legal',
                size='9 Box',  # Size by combined score
                color='Practice Area (Primary)',
                hover_name='Attorney Name',
                text='Attorney Name',
                size_max=30,
                title='Attorney 9-Box Matrix (Client vs Legal)',
                labels={
                    '9 Client': 'Client Score (1-3)',
                    '9 Legal': 'Legal Score (1-3)'
                }
            )
            
            # Set axis ranges for the 9-box
            fig.update_layout(
                xaxis=dict(range=[0.5, 3.5], dtick=1, title='Client Score'),
                yaxis=dict(range=[0.5, 3.5], dtick=1, title='Legal Score')
            )
            
            # Add grid lines to create the 9-box
            fig.update_layout(
                shapes=[
                    # Vertical lines
                    dict(type="line", x0=1.5, y0=0.5, x1=1.5, y1=3.5, line=dict(color="gray", width=1)),
                    dict(type="line", x0=2.5, y0=0.5, x1=2.5, y1=3.5, line=dict(color="gray", width=1)),
                    # Horizontal lines
                    dict(type="line", x0=0.5, y0=1.5, x1=3.5, y1=1.5, line=dict(color="gray", width=1)),
                    dict(type="line", x0=0.5, y0=2.5, x1=3.5, y1=2.5, line=dict(color="gray", width=1))
                ]
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Performance metrics by 9-box score
            st.subheader("Performance by 9-Box Score")
            
            # Group by 9-box score
            fx_performance = filtered_fx_data.groupby('9 Box').agg({
                'Attorney Name': 'count',
                'Hours': 'sum',
                'Amount': 'sum',
                'Client Name': 'sum',
                '🎚️ Target Hours / Month': 'mean'
            }).reset_index()
            
            # Rename columns
            fx_performance.rename(columns={
                'Attorney Name': 'Attorney Count',
                'Client Name': 'Client Count',
                '🎚️ Target Hours / Month': 'Avg Target Hours'
            }, inplace=True)
            
            # Calculate utilization if we have target hours
            if 'Avg Target Hours' in fx_performance.columns:
                fx_performance['Utilization %'] = (fx_performance['Hours'] / 
                    (fx_performance['Avg Target Hours'] * fx_performance['Attorney Count'] * 6) * 100)
            
            # Create bar chart for performance metrics
            metrics_to_show = st.multiselect(
                "Select metrics to display:",
                ['Hours', 'Amount', 'Attorney Count', 'Client Count', 'Utilization %'],
                default=['Hours', 'Amount']
            )
            
            if metrics_to_show:
                # Create a figure for each selected metric
                for metric in metrics_to_show:
                    fig = px.bar(
                        fx_performance.sort_values('9 Box', ascending=False),
                        x='9 Box',
                        y=metric,
                        title=f'{metric} by 9-Box Score',
                        color='9 Box',
                        labels={
                            '9 Box': '9-Box Score',
                            metric: metric
                        }
                    )
                    
                    # Format y-axis for currency if needed
                    if metric == 'Amount':
                        fig.update_layout(
                            yaxis=dict(title="Fees ($)", tickprefix="$", tickformat=",.0f")
                        )
                    elif metric == 'Utilization %':
                        fig.update_layout(
                            yaxis=dict(title="Utilization %", ticksuffix="%")
                        )
                        # Add reference line at 100%
                        fig.add_hline(y=100, line_dash="dash", line_color="red")
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            # Detailed attorney table
            st.subheader("Detailed Attorney Fx Data")
            
            # Format for display
            display_cols = ['Attorney Name', 'Practice Area (Primary)', '9 Legal', '9 Client', '9 Box']
            
            # Add performance metrics if available
            if 'Hours' in filtered_fx_data.columns:
                display_cols.extend(['Hours', 'Amount', 'Client Name'])
            
            display_data = filtered_fx_data[display_cols].reset_index(drop=True)
            
            # Format the dataframe
            if 'Amount' in display_data.columns:
                st.dataframe(
                    display_data.style.format({
                        'Hours': '{:,.1f}',
                        'Amount': '${:,.2f}',
                        'Client Name': '{:,.0f}'
                    }),
                    use_container_width=True,
                    height=400
                )
            else:
                st.dataframe(display_data, use_container_width=True, height=400)
        
        else:
            st.error("The attorney Fx data does not contain the required '9 Box' column.")
    
    except Exception as e:
        st.error(f"Error in Attorney Fx analysis: {str(e)}")
        st.write("Make sure you have the 'paste.txt' file in the same directory as the app.")

else:
    st.title("OGC Analytics Dashboard")
    st.write("Please enter the password in the sidebar to access the dashboard.")
