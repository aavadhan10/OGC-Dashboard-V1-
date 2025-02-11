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

def check_password():
    if st.session_state.authenticated:
        return True
    
    password = st.sidebar.text_input("Enter Password", type="password")
    if password == "OGC2025AI":  # Note the space at the beginning as specified
        st.session_state.authenticated = True
        return True
    elif password:
        st.sidebar.error("Incorrect password")
    return False

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
        
        # Convert date columns in six_months
        for date_col in ['Service Date', 'Invoice Date']:
            if date_col in six_months.columns:
                six_months[date_col] = pd.to_datetime(six_months[date_col], errors='coerce')
        
        # Clean up attorney data
        attorneys = attorneys[attorneys['Attorney pipeline stage'] == '🟢 Active']
        
        # Merge attorney target hours into main dataset
        six_months = six_months.merge(
            attorneys[['Attorney Name', '🎚️ Target Hours / Month']],
            left_on='Associated Attorney',
            right_on='Attorney Name',
            how='left'
        )
        
        # Calculate utilization against target
        six_months['Target Hours'] = six_months['🎚️ Target Hours / Month']
        
        return six_months, attorneys, attorney_clients, utilization, pivot_source
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None, None, None

# Function to calculate revenue band
def get_revenue_band(revenue):
    try:
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
    except:
        return "0-10M"

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
            
            # Total billable hours
            total_billable = filtered_df[filtered_df['Activity Type'] == 'Billable']['Hours'].sum()
            total_hours = filtered_df['Hours'].sum()
            with col2:
                st.metric(
                    "Total Billable Hours", 
                    f"{total_billable:,.1f}",
                    delta=f"{(total_billable/total_hours*100):.1f}% of total",
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
            
            # Total revenue
            total_revenue = filtered_df['Amount'].sum()
            with col4:
                st.metric(
                    "Total Revenue", 
                    f"${total_revenue:,.2f}",
                    help="Total revenue from all matters"
                )
                
            # Monthly trends
            st.subheader("Monthly Performance Trends")
            monthly_metrics = filtered_df.groupby(pd.Grouper(key='Service Date', freq='M')).agg({
                'Hours': 'sum',
                'Amount': 'sum',
                'Invoice Number': 'nunique'
            }).reset_index()
            
            fig = go.Figure()
            
            # Add hours trend
            fig.add_trace(go.Bar(
                x=monthly_metrics['Service Date'],
                y=monthly_metrics['Hours'],
                name='Hours',
                yaxis='y'
            ))
            
            # Add revenue trend
            fig.add_trace(go.Scatter(
                x=monthly_metrics['Service Date'],
                y=monthly_metrics['Amount'],
                name='Revenue',
                yaxis='y2',
                line=dict(color='red')
            ))
            
            fig.update_layout(
                title='Monthly Hours and Revenue',
                yaxis=dict(title='Hours', side='left'),
                yaxis2=dict(title='Revenue', side='right', overlaying='y'),
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # Utilization metrics
            st.subheader("Utilization Overview")
            
            # Calculate utilization metrics by attorney
            attorney_util = filtered_df.groupby('Associated Attorney').agg({
                'Hours': 'sum',
                'Target Hours': 'first'
            }).reset_index()
            
            attorney_util['Utilization Rate'] = attorney_util.apply(
                lambda x: (x['Hours'] / x['Target Hours'] * 100) if pd.notnull(x['Target Hours']) and x['Target Hours'] > 0 else 0,
                axis=1
            )
            
            fig = px.bar(
                attorney_util.sort_values('Utilization Rate', ascending=False),
                x='Associated Attorney',
                y='Utilization Rate',
                title='Attorney Utilization Rates (%)'
            )
            
            fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Target")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.header("Client Analysis")
            
            try:
                # Client metrics
                clients_df = filtered_df.groupby('Client Name').agg({
                    'Hours': 'sum',
                    'Amount': 'sum',
                    'Matter Name': 'nunique',
                    'Invoice Number': 'nunique'
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
                        "Avg Revenue per Client",
                        f"${avg_revenue_per_client:,.2f}",
                        help="Average revenue generated per client"
                    )
                
                with col3:
                    st.metric(
                        "Avg Hours per Client",
                        f"{avg_hours_per_client:.1f}",
                        help="Average hours spent per client"
                    )
                
                # Top clients by revenue
                st.subheader("Top Clients by Revenue")
                top_clients = clients_df.nlargest(10, 'Amount')
                fig = px.bar(
                    top_clients,
                    x='Client Name',
                    y='Amount',
                    title='Top 10 Clients by Revenue'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Client hours distribution
                st.subheader("Client Hours Distribution")
                fig = px.histogram(
                    clients_df,
                    x='Hours',
                    nbins=50,
                    title='Distribution of Hours Across Clients'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Detailed client metrics
                st.subheader("Detailed Client Metrics")
                st.dataframe(
                    clients_df.sort_values('Amount', ascending=False)
                    .style.format({
                        'Amount': '${:,.2f}',
                        'Hours': '{:,.1f}'
                    }),
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Error in client analysis: {str(e)}")

        with tab3:
            st.header("Client Segmentation")
            
            try:
                # Calculate comprehensive client metrics
                client_metrics = filtered_df.groupby('Client Name').agg({
                    'Amount': ['sum', 'mean'],
                    'Hours': ['sum', 'mean'],
                    'Matter Name': 'nunique',
                    'Invoice Number': 'nunique',
                    'SECTOR': lambda x: x.iloc[0] if not x.empty else None,
                    'Service Date': ['min', 'max']
                }).reset_index()

                # Flatten column names
                client_metrics.columns = ['Client Name', 'Total Revenue', 'Avg Revenue', 
                                        'Total Hours', 'Avg Hours', 'Matter Count',
                                        'Invoice Count', 'Sector', 'First Service', 'Last Service']
                
                # Calculate revenue bands
                client_metrics['Revenue Band'] = client_metrics['Total Revenue'].apply(get_revenue_band)
                
                # Calculate retention period
                client_metrics['Retention Days'] = (
                    client_metrics['Last Service'] - client_metrics['First Service']
                ).dt.days
                
                # Calculate Lifetime Value
                client_metrics['Daily Revenue'] = client_metrics['Total Revenue'] / client_metrics['Retention Days'].clip(lower=1)
                client_metrics['Projected Annual Value'] = client_metrics['Daily Revenue'] * 365
                
                # Revenue band distribution
                st.subheader("Revenue Distribution")
                col1, col2 = st.columns(2)
                
                with col1:
                    revenue_dist = client_metrics['Revenue Band'].value_counts()
                    fig = px.pie(
                        values=revenue_dist.values,
                        names=revenue_dist.index,
                        title="Clients by Revenue Band"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    revenue_total = client_metrics.groupby('Revenue Band')['Total Revenue'].sum()
                    fig = px.pie(
                        values=revenue_total.values,
                        names=revenue_total.index,
                        title="Revenue by Band"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Industry Analysis
                st.subheader("Industry Analysis")
                if 'Sector' in client_metrics.columns:
                    sector_metrics = client_metrics.groupby('Sector').agg({
                        'Client Name': 'count',
                        'Total Revenue': 'sum',
                        'Total Hours': 'sum'
                    }).reset_index()
                    
                    fig = px.bar(
                        sector_metrics,
                        x='Sector',
                        y=['Total Revenue', 'Total Hours'],
                        title="Industry Metrics",
                        barmode='group'
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Client Value Analysis
                st.subheader("Client Value Analysis")
                # Get most recent date from the data
                recent_date = filtered_df['Service Date'].max()
                
                # Calculate LTV metrics
                client_metrics['Monthly Revenue'] = client_metrics['Total Revenue'] / (client_metrics['Retention Days'] / 30).clip(lower=1)
                client_metrics['Avg Monthly Revenue'] = client_metrics['Monthly Revenue'].rolling(window=3, min_periods=1).mean()
                client_metrics['Churn Probability'] = np.where(
                    (recent_date - client_metrics['Last Service']).dt.days > 90,
                    0.8,  # High churn probability for inactive clients
                    0.2   # Lower churn probability for active clients
                )
                client_metrics['LTV'] = (client_metrics['Avg Monthly Revenue'] / client_metrics['Churn Probability']) * 12
                
                # Calculate revenue band metrics
                value_metrics = client_metrics.groupby('Revenue Band').agg({
                    'Client Name': 'count',
                    'Total Revenue': ['sum', 'mean'],
                    'Monthly Revenue': 'mean',
                    'LTV': ['mean', 'median', 'max'],
                    'Retention Days': ['mean', 'median'],
                    'Matter Count': 'mean'
                }).round(2)
                
                value_metrics.columns = [
                    'Client Count', 'Total Revenue', 'Avg Revenue', 'Avg Monthly Revenue',
                    'Avg LTV', 'Median LTV', 'Max LTV', 'Avg Retention', 'Median Retention',
                    'Avg Matters'
                ]
                
                # Add revenue concentration
                total_revenue = value_metrics['Total Revenue'].sum()
                value_metrics['Revenue Concentration (%)'] = (value_metrics['Total Revenue'] / total_revenue * 100).round(1)
                
                # Display value metrics
                formatted_metrics = value_metrics.style.format({
                    'Total Revenue': '${:,.2f}',
                    'Avg Revenue': '${:,.2f}',
                    'Avg Monthly Revenue': '${:,.2f}',
                    'Avg LTV': '${:,.2f}',
                    'Median LTV': '${:,.2f}',
                    'Max LTV': '${:,.2f}',
                    'Revenue Concentration (%)': '{:.1f}%'
                })
                
                st.dataframe(formatted_metrics, use_container_width=True)
                
                # LTV Analysis
                st.subheader("Lifetime Value Analysis")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # LTV by Revenue Band
                    fig = px.bar(
                        x=value_metrics.index,
                        y=value_metrics['Avg LTV'],
                        title="Average Lifetime Value by Revenue Band",
                        labels={'x': 'Revenue Band', 'y': 'Average LTV ($)'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Revenue Concentration
                    fig = px.pie(
                        values=value_metrics['Revenue Concentration (%)'],
                        names=value_metrics.index,
                        title="Revenue Concentration by Band"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Distribution of LTV
                st.subheader("LTV Distribution")
                fig = px.histogram(
                    client_metrics,
                    x='LTV',
                    nbins=50,
                    title='Distribution of Client Lifetime Values',
                    labels={'LTV': 'Lifetime Value ($)'}
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Top LTV Clients
                st.subheader("Top Clients by Lifetime Value")
                top_ltv_clients = client_metrics.nlargest(10, 'LTV')[
                    ['Client Name', 'Revenue Band', 'LTV', 'Total Revenue', 'Retention Days']
                ].reset_index(drop=True)
                
                st.dataframe(
                    top_ltv_clients.style.format({
                        'LTV': '${:,.2f}',
                        'Total Revenue': '${:,.2f}',
                        'Retention Days': '{:,.0f}'
                    }),
                    use_container_width=True
                )
                
                # Retention by revenue band
                retention_by_band = client_metrics.groupby('Revenue Band')['Retention Days'].mean().round(0)
                fig = px.bar(
                    x=retention_by_band.index,
                    y=retention_by_band.values,
                    title="Average Retention Period by Revenue Band (Days)",
                    labels={'x': 'Revenue Band', 'y': 'Days'}
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error in client segmentation analysis: {str(e)}")

        with tab4:
            st.header("Attorney Analysis")
            
            try:
                # Attorney productivity metrics
                attorney_metrics = filtered_df.groupby('Associated Attorney').agg({
                    'Hours': 'sum',
                    'Amount': 'sum',
                    'Client Name': 'nunique',
                    'Matter Name': 'nunique',
                    'Target Hours': 'first'
                }).reset_index()
                
                # Calculate utilization rate
                attorney_metrics['Utilization Rate'] = (attorney_metrics['Hours'] / 
                    attorney_metrics['Target Hours'].fillna(100)) * 100
                    
                # Calculate average hourly rate
                attorney_metrics['Avg Hourly Rate'] = attorney_metrics['Amount'] / attorney_metrics['Hours']
                
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
                        "Average Revenue per Attorney",
                        f"${attorney_metrics['Amount'].mean():,.2f}",
                        help="Average revenue generated per attorney"
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
                
                # Attorney utilization chart
                st.subheader("Attorney Utilization")
                fig = px.bar(
                    attorney_metrics.sort_values('Utilization Rate', ascending=False),
                    x='Associated Attorney',
                    y='Utilization Rate',
                    title='Attorney Utilization Rates (%)'
                )
                fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Target")
                st.plotly_chart(fig, use_container_width=True)
                
                # Top performers
                st.subheader("Top Performing Attorneys")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # By revenue
                    top_revenue = attorney_metrics.nlargest(5, 'Amount')
                    fig = px.bar(
                        top_revenue,
                        x='Associated Attorney',
                        y='Amount',
                        title='Top 5 Attorneys by Revenue'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # By hours
                    top_hours = attorney_metrics.nlargest(5, 'Hours')
                    fig = px.bar(
                        top_hours,
                        x='Associated Attorney',
                        y='Hours',
                        title='Top 5 Attorneys by Hours'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Detailed metrics table
                st.subheader("Detailed Attorney Metrics")
                st.dataframe(
                    attorney_metrics.style.format({
                        'Hours': '{:,.1f}',
                        'Amount': '${:,.2f}',
                        'Utilization Rate': '{:,.1f}%',
                        'Avg Hourly Rate': '${:,.2f}'
                    }),
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Error in attorney analysis: {str(e)}")

        with tab5:
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
                    practice_metrics['Revenue per Client'] = practice_metrics['Amount'] / practice_metrics['Client Name']
                    
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
                            title='Revenue by Practice Area'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Practice area performance metrics
                    st.subheader("Practice Area Performance")
                    fig = px.bar(
                        practice_metrics,
                        x='PG',
                        y=['Hours', 'Amount'],
                        title='Practice Area Performance Metrics',
                        barmode='group'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Detailed metrics table
                    st.subheader("Detailed Practice Area Metrics")
                    st.dataframe(
                        practice_metrics.style.format({
                            'Hours': '{:,.1f}',
                            'Amount': '${:,.2f}',
                            'Avg Rate': '${:,.2f}',
                            'Revenue per Client': '${:,.2f}'
                        }),
                        use_container_width=True
                    )
                    
                    # Practice area efficiency
                    st.subheader("Practice Area Efficiency")
                    fig = px.scatter(
                        practice_metrics,
                        x='Hours',
                        y='Amount',
                        size='Client Name',
                        text='PG',
                        title='Practice Area Efficiency (Hours vs Revenue)',
                        labels={'Hours': 'Total Hours', 'Amount': 'Total Revenue', 'Client Name': 'Number of Clients'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error in practice area analysis: {str(e)}")

        with tab6:
            st.header("Trending")
            
            try:
                # Time series analysis
                monthly_trends = filtered_df.groupby(pd.Grouper(key='Service Date', freq='M')).agg({
                    'Hours': 'sum',
                    'Amount': 'sum',
                    'Invoice Number': 'nunique',
                    'Matter Name': 'nunique',
                    'Client Name': 'nunique'
                }).reset_index()
                
                # Calculate derived metrics
                monthly_trends['Avg Rate'] = monthly_trends['Amount'] / monthly_trends['Hours']
                
                # Overall trends
                st.subheader("Monthly Performance Trends")
                
                # Hours and revenue trend
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=monthly_trends['Service Date'],
                    y=monthly_trends['Hours'],
                    name='Hours',
                    yaxis='y'
                ))
                
                fig.add_trace(go.Scatter(
                    x=monthly_trends['Service Date'],
                    y=monthly_trends['Amount'],
                    name='Revenue',
                    yaxis='y2',
                    line=dict(color='red')
                ))
                
                fig.update_layout(
                    title='Monthly Hours and Revenue Trends',
                    yaxis=dict(title='Hours', side='left'),
                    yaxis2=dict(title='Revenue', side='right', overlaying='y'),
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Client and matter trends
                st.subheader("Client and Matter Trends")
                fig = px.line(
                    monthly_trends,
                    x='Service Date',
                    y=['Client Name', 'Matter Name'],
                    title='Monthly Client and Matter Counts'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Average rate trend
                st.subheader("Rate Trends")
                fig = px.line(
                    monthly_trends,
                    x='Service Date',
                    y='Avg Rate',
                    title='Monthly Average Rate Trend'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Detailed trends table
                st.subheader("Detailed Monthly Metrics")
                st.dataframe(
                    monthly_trends.style.format({
                        'Hours': '{:,.1f}',
                        'Amount': '${:,.2f}',
                        'Avg Rate': '${:,.2f}',
                        'Client Name': '{:,.0f}',
                        'Matter Name': '{:,.0f}',
                        'Invoice Number': '{:,.0f}'
                    }),
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Error in trending analysis: {str(e)}")

    else:
        st.error("Failed to load data. Please check your data files and try again.")
else:
    st.title("OGC Analytics Dashboard")
    st.write("Please enter the password in the sidebar to access the dashboard.")
