import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar

# Page config
st.set_page_config(
    page_title="OGC Utilization Dashboard",
    page_icon="⚖️",
    layout="wide"
)

@st.cache_data
def load_data():
    """Load and process all data files"""
    try:
        # Load CSV files
        df = pd.read_csv('SIX_FULL_MOS.csv')
        df['Service Date'] = pd.to_datetime(df['Service Date'])
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def create_filters(df):
    """Create sidebar filters"""
    st.sidebar.header("Filters")
    
    # Date filters
    st.sidebar.subheader("Date Range")
    date_range = st.sidebar.date_input(
        "Select period",
        value=(df['Service Date'].min(), df['Service Date'].max()),
        min_value=df['Service Date'].min(),
        max_value=df['Service Date'].max()
    )
    
    # Attorney filters
    st.sidebar.subheader("Attorney Filters")
    selected_attorneys = st.sidebar.multiselect(
        "Select Attorneys",
        options=sorted(df['Associated Attorney'].unique())
    )
    
    # Practice Group filters
    st.sidebar.subheader("Practice Groups")
    selected_pg = st.sidebar.multiselect(
        "Select Practice Groups",
        options=sorted(df['PG'].unique())
    )
    
    return date_range, selected_attorneys, selected_pg

def filter_data(df, date_range, selected_attorneys, selected_pg):
    """Apply filters to dataframe"""
    filtered_df = df.copy()
    
    # Apply date filter
    if len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df['Service Date'].dt.date >= date_range[0]) &
            (filtered_df['Service Date'].dt.date <= date_range[1])
        ]
    
    # Apply attorney filter
    if selected_attorneys:
        filtered_df = filtered_df[
            filtered_df['Associated Attorney'].isin(selected_attorneys)
        ]
    
    # Apply practice group filter
    if selected_pg:
        filtered_df = filtered_df[
            filtered_df['PG'].isin(selected_pg)
        ]
    
    return filtered_df

def calculate_metrics(df):
    """Calculate key metrics"""
    metrics = {
        'total_hours': df['Hours'].sum(),
        'total_amount': df['Amount'].sum(),
        'avg_rate': df['Amount'].sum() / df['Hours'].sum() if df['Hours'].sum() > 0 else 0,
        'billable_entries': len(df[df['Activity Type'] == 'Billable']),
        'total_entries': len(df)
    }
    return metrics

def create_overview_section(df, metrics):
    """Create overview section with key metrics"""
    st.header("Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Hours",
            f"{metrics['total_hours']:,.1f}"
        )
    
    with col2:
        st.metric(
            "Total Amount",
            f"${metrics['total_amount']:,.2f}"
        )
    
    with col3:
        st.metric(
            "Average Rate",
            f"${metrics['avg_rate']:,.2f}/hr"
        )
    
    with col4:
        utilization_rate = (metrics['billable_entries'] / metrics['total_entries'] * 100) if metrics['total_entries'] > 0 else 0
        st.metric(
            "Utilization Rate",
            f"{utilization_rate:.1f}%"
        )

def create_attorney_section(df):
    """Create attorney analysis section"""
    st.header("Attorney Analysis")
    
    # Attorney metrics
    attorney_metrics = df.groupby('Associated Attorney').agg({
        'Hours': 'sum',
        'Amount': 'sum',
        'Time Entry ID': 'count'
    }).reset_index()
    
    # Create visualization
    fig = px.scatter(
        attorney_metrics,
        x='Hours',
        y='Amount',
        hover_name='Associated Attorney',
        size='Time Entry ID',
        title='Attorney Performance'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add attorney metrics table
    st.subheader("Attorney Metrics")
    st.dataframe(
        attorney_metrics.sort_values('Hours', ascending=False),
        column_config={
            'Hours': st.column_config.NumberColumn('Total Hours', format="%.1f"),
            'Amount': st.column_config.NumberColumn('Total Amount', format="$%.2f"),
            'Time Entry ID': st.column_config.NumberColumn('Entry Count', format="%d")
        }
    )

def create_practice_group_section(df):
    """Create practice group analysis section"""
    st.header("Practice Group Analysis")
    
    pg_metrics = df.groupby('PG').agg({
        'Hours': 'sum',
        'Amount': 'sum'
    }).reset_index()
    
    fig = px.bar(
        pg_metrics,
        x='PG',
        y=['Hours', 'Amount'],
        barmode='group',
        title='Practice Group Performance'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add practice group metrics table
    st.subheader("Practice Group Metrics")
    st.dataframe(
        pg_metrics.sort_values('Hours', ascending=False),
        column_config={
            'Hours': st.column_config.NumberColumn('Total Hours', format="%.1f"),
            'Amount': st.column_config.NumberColumn('Total Amount', format="$%.2f")
        }
    )

def main():
    st.title("OGC Utilization Dashboard")
    
    # Load data
    df = load_data()
    
    if df is not None:
        # Create filters
        date_range, selected_attorneys, selected_pg = create_filters(df)
        
        # Apply filters
        filtered_df = filter_data(df, date_range, selected_attorneys, selected_pg)
        
        # Calculate metrics
        metrics = calculate_metrics(filtered_df)
        
        # Create tabs
        tabs = st.tabs(["Overview", "Attorney Analysis", "Practice Groups"])
        
        with tabs[0]:
            create_overview_section(filtered_df, metrics)
        
        with tabs[1]:
            create_attorney_section(filtered_df)
        
        with tabs[2]:
            create_practice_group_section(filtered_df)

if __name__ == "__main__":
    main()
