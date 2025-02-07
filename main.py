import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar

# Set page configuration
st.set_page_config(
    page_title="OGC Utilization Dashboard",
    page_icon="⚖️",
    layout="wide"
)

@st.cache_data
def load_and_process_data():
    """Load and process all data files with proper cleaning"""
    try:
        # Load all CSV files
        six_months_df = pd.read_csv('SIX_FULL_MOS.csv')
        attorney_pg_df = pd.read_csv('ATTORNEY_PG_AND_HRS.csv')
        attorney_clients_df = pd.read_csv('ATTORNEY_CLIENTS.csv')
        pivot_source_df = pd.read_csv('PIVOT_SOURCE_1.csv')
        utilization_df = pd.read_csv('UTILIZATION.csv')
        
        # Convert date columns
        six_months_df['Service Date'] = pd.to_datetime(six_months_df['Service Date'])
        
        return six_months_df, attorney_pg_df, attorney_clients_df, pivot_source_df, utilization_df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None, None, None

def calculate_attorney_metrics(df):
    """Calculate attorney metrics using only available columns"""
    attorney_metrics = df.groupby('Associated Attorney').agg({
        'Hours': 'sum',
        'Amount': 'sum',
        'Time Entry ID': 'count'
    }).reset_index()
    
    # Calculate billable rate using available data
    billable_mask = df['Activity Type'] == 'Billable'
    billable_hours = df[billable_mask].groupby('Associated Attorney')['Hours'].sum()
    total_hours = df.groupby('Associated Attorney')['Hours'].sum()
    
    # Add utilization rate
    attorney_metrics['Utilization Rate'] = (
        billable_hours / total_hours * 100
    ).fillna(0).round(2)
    
    # Calculate average rate from Amount and Hours
    attorney_metrics['Average Rate'] = (
        attorney_metrics['Amount'] / attorney_metrics['Hours']
    ).fillna(0).round(2)
    
    return attorney_metrics

def create_sidebar_filters(df, attorney_df):
    """Create sidebar filters using available columns"""
    st.sidebar.header("Filters")
    
    filter_tabs = st.sidebar.tabs(["Time", "Attorneys", "Practice Groups"])
    
    with filter_tabs[0]:
        st.subheader("Time Period")
        date_range = st.date_input(
            "Select Date Range",
            value=(df['Service Date'].min(), df['Service Date'].max())
        )
    
    with filter_tabs[1]:
        st.subheader("Attorney Information")
        selected_attorneys = st.multiselect(
            "Select Attorneys",
            options=sorted(df['Associated Attorney'].unique())
        )
        
        selected_pipeline_stages = st.multiselect(
            "Attorney Pipeline Stage",
            options=sorted(attorney_df['Attorney pipeline stage'].unique())
        )
    
    with filter_tabs[2]:
        st.subheader("Practice Groups")
        selected_practice_areas = st.multiselect(
            "Primary Practice Areas",
            options=sorted(attorney_df['Practice Area (Primary)'].unique())
        )
    
    return {
        'date_range': date_range,
        'attorneys': selected_attorneys,
        'pipeline_stages': selected_pipeline_stages,
        'practice_areas': selected_practice_areas
    }

def create_attorney_analysis(df):
    """Create attorney analysis visualizations"""
    st.header("Attorney Analysis")
    
    # Summary metrics
    total_hours = df['Hours'].sum()
    total_amount = df['Amount'].sum()
    avg_rate = (total_amount / total_hours) if total_hours > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Hours", f"{total_hours:,.1f}")
    with col2:
        st.metric("Total Amount", f"${total_amount:,.2f}")
    with col3:
        st.metric("Average Rate", f"${avg_rate:.2f}/hr")
    
    # Attorney performance chart
    attorney_performance = df.groupby('Associated Attorney').agg({
        'Hours': 'sum',
        'Amount': 'sum'
    }).reset_index()
    
    fig = px.scatter(
        attorney_performance,
        x='Hours',
        y='Amount',
        hover_name='Associated Attorney',
        title='Attorney Performance'
    )
    st.plotly_chart(fig, use_container_width=True)

def create_practice_group_analysis(df):
    """Create practice group analysis using PG column"""
    st.header("Practice Group Analysis")
    
    pg_metrics = df.groupby('PG').agg({
        'Hours': 'sum',
        'Amount': 'sum'
    }).reset_index()
    
    fig = px.bar(
        pg_metrics,
        x='PG',
        y=['Hours', 'Amount'],
        title='Practice Group Performance',
        barmode='group'
    )
    st.plotly_chart(fig, use_container_width=True)

def main():
    st.title("OGC Utilization Dashboard")
    
    # Load all data
    six_months_df, attorney_pg_df, attorney_clients_df, pivot_source_df, utilization_df = load_and_process_data()
    
    if all(df is not None for df in [six_months_df, attorney_pg_df, attorney_clients_df, pivot_source_df, utilization_df]):
        # Create filters
        filters = create_sidebar_filters(six_months_df, attorney_pg_df)
        
        # Create tabs
        tabs = st.tabs(["Attorney Analysis", "Practice Groups"])
        
        with tabs[0]:
            create_attorney_analysis(six_months_df)
        
        with tabs[1]:
            create_practice_group_analysis(six_months_df)

if __name__ == "__main__":
    main()
