import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import calendar

# Set page config
st.set_page_config(page_title="Law Firm Analytics Dashboard", layout="wide")

# Function to load data
@st.cache_data
def load_data():
    try:
        six_months = pd.read_csv('SIX_FULL_MOS.csv')
        attorneys = pd.read_csv('ATTORNEY_PG_AND_HRS.csv')
        attorney_clients = pd.read_csv('ATTORNEY_CLIENTS.csv')
        
        # Convert date columns
        for date_col in ['Service Date', 'Invoice Date']:
            if date_col in six_months.columns:
                six_months[date_col] = pd.to_datetime(six_months[date_col], errors='coerce')
        
        return six_months, attorneys, attorney_clients
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None

# Load data
six_months_df, attorneys_df, attorney_clients_df = load_data()

if six_months_df is not None:
    # Sidebar filters
    st.sidebar.header('Filters')

    # Date filter
    if 'Service Date' in six_months_df.columns:
        min_date = six_months_df['Service Date'].min()
        max_date = six_months_df['Service Date'].max()
        if pd.notnull(min_date) and pd.notnull(max_date):
            date_range = st.sidebar.date_input(
                "Date Range",
                value=(min_date.date(), max_date.date()),
                min_value=min_date.date(),
                max_value=max_date.date()
            )
        else:
            st.error("Invalid date range in data")
            st.stop()

    # Attorney filter
    if 'Associated Attorney' in six_months_df.columns:
        attorneys = sorted(six_months_df['Associated Attorney'].dropna().unique())
        selected_attorneys = st.sidebar.multiselect('Attorneys', attorneys)

    # Practice Group filter
    if 'PG' in six_months_df.columns:
        practice_groups = sorted(six_months_df['PG'].dropna().unique())
        selected_practices = st.sidebar.multiselect('Practice Groups', practice_groups)

    # Matter filter
    if 'Matter Name' in six_months_df.columns:
        matters = sorted(six_months_df['Matter Name'].dropna().unique())
        selected_matters = st.sidebar.multiselect('Matters', matters)

    # Apply filters
    filtered_df = six_months_df.copy()
    
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df['Service Date'].dt.date >= date_range[0]) &
            (filtered_df['Service Date'].dt.date <= date_range[1])
        ]
    
    if selected_attorneys:
        filtered_df = filtered_df[filtered_df['Associated Attorney'].isin(selected_attorneys)]
    
    if selected_practices:
        filtered_df = filtered_df[filtered_df['PG'].isin(selected_practices)]
    
    if selected_matters:
        filtered_df = filtered_df[filtered_df['Matter Name'].isin(selected_matters)]

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview", "Client Analysis", "Client Segmentation", "Attorney Analysis", 
        "Practice Areas", "Trending"
    ])

    with tab1:
        st.header("Overview")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        # Monthly bills generated
        monthly_bills = filtered_df.groupby(filtered_df['Invoice Date'].dt.to_period('M'))['Invoice Number'].nunique()
        with col1:
            st.metric("Monthly Bills Generated", monthly_bills.iloc[-1] if not monthly_bills.empty else 0)
        
        # Monthly matters opened
        monthly_matters = filtered_df.groupby(filtered_df['Service Date'].dt.to_period('M'))['Matter Name'].nunique()
        with col2:
            st.metric("Monthly Matters Opened", monthly_matters.iloc[-1] if not monthly_matters.empty else 0)
        
        # Firm utilization
        total_hours = filtered_df['Hours'].sum()
        billable_hours = filtered_df[filtered_df['Activity Type'] == 'Billable']['Hours'].sum()
        utilization_rate = (billable_hours / total_hours * 100) if total_hours > 0 else 0
        with col3:
            st.metric("Firm Utilization", f"{utilization_rate:.1f}%")
        
        # Average attorney production
        avg_attorney_production = filtered_df.groupby('Associated Attorney')['Hours'].mean().mean()
        with col4:
            st.metric("Avg Attorney Production (Hours)", f"{avg_attorney_production:.1f}")
        
        # Trending charts
        st.subheader("Trending Metrics")
        
        # Monthly production trend
        monthly_production = filtered_df.groupby(filtered_df['Service Date'].dt.to_period('M')).agg({
            'Hours': 'sum',
            'Amount': 'sum'
        }).reset_index()
        
        monthly_production['Service Date'] = monthly_production['Service Date'].astype(str)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=monthly_production['Service Date'],
            y=monthly_production['Hours'],
            name='Hours'
        ))
        fig.add_trace(go.Scatter(
            x=monthly_production['Service Date'],
            y=monthly_production['Amount'],
            name='Amount',
            yaxis='y2'
        ))
        fig.update_layout(
            title='Monthly Production Trends',
            yaxis=dict(title='Hours'),
            yaxis2=dict(title='Amount', overlaying='y', side='right')
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Client Analysis")
        
    with tab3:
        st.header("Client Segmentation")
        
        # Calculate revenue bands
        def get_revenue_band(revenue):
            revenue_in_millions = revenue / 1000000
            if revenue_in_millions <= 10:
                return "0-10M"
            elif revenue_in_millions <= 25:
                return "10M-25M"
            elif revenue_in_millions <= 50:
                return "25M-50M"
            elif revenue_in_millions <= 75:
                return "50M-75M"
            else:
                return "75M+"
        
        # Aggregate client revenue
        client_revenue = filtered_df.groupby('Client Name').agg({
            'Amount': 'sum',
            'SECTOR': 'first',
            'Service Date': ['min', 'max']
        }).reset_index()
        
        # Add revenue band column
        client_revenue['Revenue Band'] = client_revenue['Amount'].apply(get_revenue_band)
        
        # Calculate retention period in days
        client_revenue['Retention Period'] = (
            client_revenue['Service Date']['max'] - 
            client_revenue['Service Date']['min']
        ).dt.days
        
        # Revenue Bands Distribution
        st.subheader("Revenue Band Distribution")
        revenue_band_dist = client_revenue['Revenue Band'].value_counts()
        fig = px.pie(
            values=revenue_band_dist.values,
            names=revenue_band_dist.index,
            title="Client Distribution by Revenue Band"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Industry Classification
        st.subheader("Industry Classification")
        sector_dist = client_revenue['SECTOR'].value_counts()
        fig = px.bar(
            x=sector_dist.index,
            y=sector_dist.values,
            title="Client Distribution by Industry"
        )
        fig.update_layout(xaxis_title="Industry Sector", yaxis_title="Number of Clients")
        st.plotly_chart(fig, use_container_width=True)
        
        # Revenue Metrics
        st.subheader("Revenue Metrics")
        
        # Average revenue by band
        avg_revenue = client_revenue.groupby('Revenue Band')['Amount'].mean().reset_index()
        fig = px.bar(
            avg_revenue,
            x='Revenue Band',
            y='Amount',
            title="Average Annual Revenue per Client by Revenue Band"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Revenue concentration
        revenue_concentration = client_revenue.groupby('Revenue Band')['Amount'].sum().reset_index()
        total_revenue = revenue_concentration['Amount'].sum()
        revenue_concentration['Percentage'] = (revenue_concentration['Amount'] / total_revenue) * 100
        
        fig = px.bar(
            revenue_concentration,
            x='Revenue Band',
            y='Percentage',
            title="Revenue Concentration by Band (%)"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Retention Analysis
        st.subheader("Retention Analysis")
        
        # Average retention period by revenue band
        avg_retention = client_revenue.groupby('Revenue Band')['Retention Period'].mean().reset_index()
        fig = px.bar(
            avg_retention,
            x='Revenue Band',
            y='Retention Period',
            title="Average Retention Period (Days) by Revenue Band"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed metrics
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Average Client Lifetime (Days)", 
                f"{client_revenue['Retention Period'].mean():.0f}"
            )
            
        with col2:
            # Calculate churn rate (clients with no activity in last 90 days)
            last_activity = filtered_df.groupby('Client Name')['Service Date'].max()
            latest_date = filtered_df['Service Date'].max()
            churned_clients = (latest_date - last_activity).dt.days > 90
            churn_rate = (churned_clients.sum() / len(churned_clients)) * 100
            
            st.metric(
                "90-Day Churn Rate", 
                f"{churn_rate:.1f}%"
            )
            
        # Revenue band details table
        st.subheader("Revenue Band Details")
        band_metrics = client_revenue.groupby('Revenue Band').agg({
            'Client Name': 'count',
            'Amount': ['mean', 'sum'],
            'Retention Period': 'mean'
        }).round(2)
        
        band_metrics.columns = ['Client Count', 'Avg Revenue', 'Total Revenue', 'Avg Retention (Days)']
        st.dataframe(band_metrics)
        
        # Client metrics
        clients_df = filtered_df.groupby('Client Name').agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Matter Name': 'nunique'
        }).reset_index()
        
        # Top clients by revenue
        st.subheader("Top Clients by Revenue")
        top_clients = clients_df.nlargest(10, 'Amount')
        fig = px.bar(top_clients, x='Client Name', y='Amount',
                     title='Top 10 Clients by Revenue')
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Attorney Analysis")
        
        # Attorney productivity metrics
        attorney_metrics = filtered_df.groupby('Associated Attorney').agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Client Name': 'nunique'
        }).reset_index()
        
        # Attorney utilization rates
        st.subheader("Attorney Utilization Rates")
        fig = px.bar(attorney_metrics, x='Associated Attorney', y='Hours',
                     title='Attorney Hours Distribution')
        st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.header("Practice Areas")
        
        # Practice area metrics
        practice_metrics = filtered_df.groupby('PG').agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Matter Name': 'nunique'
        }).reset_index()
        
        # Practice area distribution
        st.subheader("Practice Area Distribution")
        fig = px.pie(practice_metrics, values='Hours', names='PG',
                     title='Hours by Practice Area')
        st.plotly_chart(fig, use_container_width=True)

    with tab5:
        st.header("Trending")
        
        # Time series analysis
        monthly_trends = filtered_df.groupby(filtered_df['Service Date'].dt.to_period('M')).agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Invoice Number': 'nunique'
        }).reset_index()
        
        monthly_trends['Service Date'] = monthly_trends['Service Date'].astype(str)
        
        # Trending metrics visualization
        st.subheader("Monthly Trends")
        fig = px.line(monthly_trends, x='Service Date', y=['Hours', 'Amount'],
                      title='Monthly Performance Trends')
        st.plotly_chart(fig, use_container_width=True)

    # Add CSS for better styling
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 4px;
            gap: 12px;
            padding: 0px 16px;
        }
        </style>
    """, unsafe_allow_html=True)
else:
    st.error("Failed to load data. Please check your data files and try again.")
