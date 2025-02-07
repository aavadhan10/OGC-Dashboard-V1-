import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

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

# Function to calculate revenue band
def get_revenue_band(revenue):
    if pd.isna(revenue) or revenue == 0:
        return "0-10M"
    revenue_in_millions = float(revenue) / 1000000
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

# Load data
six_months_df, attorneys_df, attorney_clients_df = load_data()

if six_months_df is not None:
    # Sidebar filters
    st.sidebar.header('Filters')

    # Date filter
    try:
        min_date = six_months_df['Service Date'].min()
        max_date = six_months_df['Service Date'].max()
        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
    except:
        st.error("Error with date range")
        date_range = None

    # Attorney filter
    attorneys = sorted(six_months_df['Associated Attorney'].dropna().unique())
    selected_attorneys = st.sidebar.multiselect('Attorneys', attorneys)

    # Practice Group filter
    practice_groups = sorted(six_months_df['PG'].dropna().unique())
    selected_practices = st.sidebar.multiselect('Practice Groups', practice_groups)

    # Matter filter
    matters = sorted(six_months_df['Matter Name'].dropna().unique())
    selected_matters = st.sidebar.multiselect('Matters', matters)

    # Apply filters
    filtered_df = six_months_df.copy()
    
    if date_range and len(date_range) == 2:
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
        monthly_bills = filtered_df.groupby(pd.Grouper(key='Invoice Date', freq='M'))['Invoice Number'].nunique()
        with col1:
            st.metric("Monthly Bills Generated", monthly_bills.iloc[-1] if not monthly_bills.empty else 0)
        
        # Monthly matters opened
        monthly_matters = filtered_df.groupby(pd.Grouper(key='Service Date', freq='M'))['Matter Name'].nunique()
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

    with tab2:
        st.header("Client Analysis")
        
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
        st.header("Client Segmentation")
        
        try:
            # Calculate client revenue metrics
            client_metrics = filtered_df.groupby('Client Name').agg({
                'Amount': 'sum',
                'SECTOR': lambda x: x.iloc[0] if not x.empty else None,
                'Service Date': ['min', 'max']
            }).reset_index()

            # Rename columns
            client_metrics.columns = ['Client Name', 'Total Revenue', 'Sector', 'First Service', 'Last Service']
            
            # Calculate revenue bands
            client_metrics['Revenue Band'] = client_metrics['Total Revenue'].apply(get_revenue_band)
            
            # Calculate retention period
            client_metrics['Retention Days'] = (client_metrics['Last Service'] - client_metrics['First Service']).dt.days
            
            # Revenue band distribution
            st.subheader("Revenue Band Distribution")
            revenue_dist = client_metrics['Revenue Band'].value_counts()
            fig = px.pie(values=revenue_dist.values, names=revenue_dist.index,
                        title="Client Distribution by Revenue Band")
            st.plotly_chart(fig, use_container_width=True)
            
            # Sector analysis
            if 'Sector' in client_metrics.columns:
                st.subheader("Industry Distribution")
                sector_dist = client_metrics['Sector'].value_counts()
                fig = px.bar(x=sector_dist.index, y=sector_dist.values,
                            title="Clients by Industry Sector")
                st.plotly_chart(fig, use_container_width=True)
            
            # Revenue metrics
            st.subheader("Revenue Analysis")
            revenue_analysis = client_metrics.groupby('Revenue Band').agg({
                'Total Revenue': ['mean', 'sum', 'count'],
                'Retention Days': 'mean'
            }).round(2)
            
            revenue_analysis.columns = ['Avg Revenue', 'Total Revenue', 'Client Count', 'Avg Retention Days']
            st.dataframe(revenue_analysis)
            
            # Retention analysis
            st.subheader("Retention Analysis")
            retention_by_band = client_metrics.groupby('Revenue Band')['Retention Days'].mean().round(0)
            fig = px.bar(x=retention_by_band.index, y=retention_by_band.values,
                        title="Average Retention Period by Revenue Band (Days)")
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error in client segmentation analysis: {str(e)}")

    with tab4:
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

    with tab5:
        st.header("Practice Areas")
        if 'PG' in filtered_df.columns:
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

    with tab6:
        st.header("Trending")
        
        # Time series analysis
        monthly_trends = filtered_df.groupby(pd.Grouper(key='Service Date', freq='M')).agg({
            'Hours': 'sum',
            'Amount': 'sum',
            'Invoice Number': 'nunique'
        }).reset_index()
        
        # Trending metrics visualization
        st.subheader("Monthly Trends")
        fig = px.line(monthly_trends, x='Service Date', y=['Hours', 'Amount'],
                      title='Monthly Performance Trends')
        st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Failed to load data. Please check your data files and try again.")
