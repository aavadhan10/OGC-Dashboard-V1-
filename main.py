import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar
import numpy as np

# Set page configuration
st.set_page_config(
    page_title="Law Firm Analytics Dashboard",
    page_icon="⚖️",
    layout="wide"
)

# Custom styling
st.markdown("""
    <style>
    .main { padding: 0rem 1rem; }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_and_process_data():
    """Load and process all data files with proper cleaning"""
    try:
        # Load all CSV files
        utilization_df = pd.read_csv('SIX_FULL_MOS.csv')
        attorney_pg_df = pd.read_csv('ATTORNEY_PG_AND_HRS.csv')
        attorney_clients_df = pd.read_csv('ATTORNEY_CLIENTS.csv')
        
        # Convert date columns
        utilization_df['Service Date'] = pd.to_datetime(utilization_df['Service Date'])
        utilization_df['Invoice Date'] = pd.to_datetime(utilization_df['Invoice Date'])
        
        # Calculate attorney efficiency metrics
        attorney_metrics = calculate_attorney_metrics(utilization_df)
        
        # Calculate client LTV metrics
        client_ltv = calculate_client_ltv(utilization_df)
        
        return utilization_df, attorney_pg_df, attorney_clients_df, attorney_metrics, client_ltv
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None, None, None

def calculate_attorney_metrics(df):
    """Calculate comprehensive attorney performance metrics"""
    attorney_metrics = df.groupby('Associated Attorney').agg({
        'Hours': ['sum', 'mean'],
        'Amount': ['sum', 'mean'],
        'Time Entry ID': 'count'
    }).reset_index()
    
    # Calculate efficiency metrics
    billable_hours = df[df['Activity Type'] == 'Billable'].groupby('Associated Attorney')['Hours'].sum()
    total_hours = df.groupby('Associated Attorney')['Hours'].sum()
    attorney_metrics['Utilization Rate'] = (billable_hours / total_hours * 100).round(2)
    
    return attorney_metrics

def calculate_client_ltv(df):
    """Calculate Client Lifetime Value metrics"""
    client_ltv = df.groupby('Client Name').agg({
        'Amount': 'sum',
        'Hours': 'sum',
        'Time Entry ID': 'count',
        'Service Date': ['min', 'max']
    }).reset_index()
    
    # Calculate engagement duration in months
    client_ltv['Engagement Duration'] = (
        (client_ltv['Service Date']['max'] - client_ltv['Service Date']['min'])
        .dt.total_seconds() / (30 * 24 * 60 * 60)
    ).round(1)
    
    # Calculate monthly value
    client_ltv['Monthly Value'] = (
        client_ltv['Amount']['sum'] / client_ltv['Engagement Duration']
    ).round(2)
    
    return client_ltv

def create_sidebar_filters(df, attorney_df):
    """Create comprehensive sidebar filters"""
    st.sidebar.header("Filters")
    
    # Create filter tabs
    filter_tabs = st.sidebar.tabs([
        "Time", "Attorneys", "Practice", "Matter", "Financial", "Clients"
    ])
    
    with filter_tabs[0]:  # Time Filters
        st.subheader("Time Period")
        selected_year = st.selectbox(
            "Year",
            options=sorted(df['Service Date'].dt.year.unique()),
            index=len(df['Service Date'].dt.year.unique()) - 1
        )
        
        selected_months = st.multiselect(
            "Months",
            options=sorted(df['Service Date'].dt.month.unique())
        )
        
        date_range = st.date_input(
            "Custom Date Range",
            value=(df['Service Date'].min(), df['Service Date'].max())
        )

    with filter_tabs[1]:  # Attorney Filters
        st.subheader("Attorney Information")
        selected_attorney_levels = st.multiselect(
            "Attorney Levels",
            options=sorted(attorney_df['Attorney pipeline stage'].unique())
        )
        
        selected_attorneys = st.multiselect(
            "Select Attorneys",
            options=sorted(df['Associated Attorney'].unique())
        )

    with filter_tabs[2]:  # Practice Filters
        st.subheader("Practice Areas")
        selected_practice_areas = st.multiselect(
            "Practice Areas",
            options=sorted(df['PG'].unique())
        )

    # Return all filters in a dictionary
    return {
        'year': selected_year,
        'months': selected_months,
        'date_range': date_range,
        'attorney_levels': selected_attorney_levels,
        'attorneys': selected_attorneys,
        'practice_areas': selected_practice_areas
    }

def create_attorney_analysis_section(df, attorney_metrics):
    """Create comprehensive attorney analysis section"""
    st.header("Attorney Analysis")
    
    # Key attorney metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Average Attorney Hours",
            f"{attorney_metrics['Hours']['mean'].mean():.1f}"
        )
    with col2:
        st.metric(
            "Average Revenue per Attorney",
            f"${attorney_metrics['Amount']['mean'].mean():,.2f}"
        )
    with col3:
        st.metric(
            "Average Utilization Rate",
            f"{attorney_metrics['Utilization Rate'].mean():.1f}%"
        )
    
    # Attorney performance chart
    fig = px.scatter(
        attorney_metrics,
        x=('Hours', 'sum'),
        y=('Amount', 'sum'),
        size='Utilization Rate',
        hover_name='Associated Attorney',
        title='Attorney Performance Matrix'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Attorney utilization trends
    monthly_attorney_util = df.groupby([
        'Service Date', 'Associated Attorney'
    ])['Hours'].sum().reset_index()
    
    fig2 = px.line(
        monthly_attorney_util,
        x='Service Date',
        y='Hours',
        color='Associated Attorney',
        title='Attorney Utilization Trends'
    )
    st.plotly_chart(fig2, use_container_width=True)

def create_client_analysis_section(df, client_ltv):
    """Create comprehensive client analysis section"""
    st.header("Client Analysis")
    
    # Client LTV metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Average Client LTV",
            f"${client_ltv['Amount']['sum'].mean():,.2f}"
        )
    with col2:
        st.metric(
            "Average Engagement Duration",
            f"{client_ltv['Engagement Duration'].mean():.1f} months"
        )
    with col3:
        st.metric(
            "Average Monthly Value",
            f"${client_ltv['Monthly Value'].mean():,.2f}"
        )
    
    # Client LTV visualization
    fig = px.scatter(
        client_ltv,
        x='Engagement Duration',
        y=('Amount', 'sum'),
        size='Monthly Value',
        hover_name='Client Name',
        title='Client Lifetime Value Analysis'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Client segmentation
    client_segments = pd.qcut(
        client_ltv['Monthly Value'],
        q=4,
        labels=['Bronze', 'Silver', 'Gold', 'Platinum']
    )
    client_ltv['Segment'] = client_segments
    
    fig2 = px.box(
        client_ltv,
        x='Segment',
        y='Monthly Value',
        title='Client Value Segmentation'
    )
    st.plotly_chart(fig2, use_container_width=True)

def create_practice_group_section(df):
    """Create practice group analysis section"""
    st.header("Practice Group Analysis")
    
    practice_metrics = df.groupby('PG').agg({
        'Hours': 'sum',
        'Amount': 'sum',
        'Time Entry ID': 'count'
    }).reset_index()
    
    # Practice group performance chart
    fig = px.bar(
        practice_metrics,
        x='PG',
        y=['Hours', 'Amount'],
        title='Practice Group Performance',
        barmode='group'
    )
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.title("OGC Utilization Dashboard")
    
    # Load data
    utilization_df, attorney_pg_df, attorney_clients_df, attorney_metrics, client_ltv = load_and_process_data()
    
    if all(df is not None for df in [utilization_df, attorney_pg_df, attorney_clients_df]):
        # Create sidebar filters
        filters = create_sidebar_filters(utilization_df, attorney_pg_df)
        
        # Create main tabs
        tabs = st.tabs([
            "Overview",
            "Attorney Analysis",
            "Client Analysis",
            "Practice Groups"
        ])
        
        with tabs[0]:
            st.header("Department Overview")
            # Add department overview metrics and charts
        
        with tabs[1]:
            create_attorney_analysis_section(utilization_df, attorney_metrics)
        
        with tabs[2]:
            create_client_analysis_section(utilization_df, client_ltv)
        
        with tabs[3]:
            create_practice_group_section(utilization_df)

if __name__ == "__main__":
    main()
