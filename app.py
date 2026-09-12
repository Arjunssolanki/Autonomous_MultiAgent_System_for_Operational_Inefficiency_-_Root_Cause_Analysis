import streamlit as st
import pandas as pd
import numpy as np
import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

from main import run_operational_analysis

st.set_page_config(page_title="Agentic BA Analytics Workspace", layout="wide")

st.title("Autonomous Operational Inefficiency & Root-Cause Analyst")
st.subheader("Leveraging Multi-Agent AI to translate data operational bottlenecks into business strategy.")

col1, col2 = st.columns([1, 1])

with col1:
    user_input = st.text_area(
        "Enter an operational problem statement or text-based report snippet to analyze:",
        placeholder="Example: Regional distribution hubs are reporting a 15% increase in transit delivery lag times...",
        height=200
    )
    
    execute_analysis = st.button("Run Multi-Agent Analysis")

with col2:
    st.markdown("### Operational Metrics Simulation Workspace")
    metric_scale = st.slider("Simulated Operational Deviation (%)", min_value=0, max_value=100, value=22)
    sample_volume = st.number_input("Analysis Data Batch Size (Rows)", min_value=100, max_value=50000, value=1000)

if execute_analysis:
    if user_input.strip() == "":
        st.warning("Please provide a valid business problem statement to initiate the workflow.")
    else:
        with st.spinner("Agents are collaborating! Running data tracking and strategic analysis loops..."):
            try:
                final_report = run_operational_analysis(user_input)
                
                st.success("Analysis Complete!")
                
                tab1, tab2 = st.tabs(["Strategic Requirements Report", "Analytical Performance Charts"])
                
                with tab1:
                    st.markdown("### Final Generated Business Strategy & Requirements")
                    st.info(final_report)
                    
                    st.download_button(
                        label="Download Strategic Report (.md)",
                        data=final_report,
                        file_name="operational_requirements_report.md",
                        mime="text/markdown"
                    )
                
                with tab2:
                    st.markdown("### Anomaly Distribution & Anisotropic Lags Summary")
                    
                    chart_data = pd.DataFrame(
                        np.random.randn(sample_volume, 2) / [50, 50] + [0.1, 0.15],
                        columns=['Baseline Delay Processing', 'Anomalous Phase Lag']
                    )
                    
                    st.line_chart(chart_data)
                    
                    summary_metrics = pd.DataFrame({
                        "Metric Indicator": ["Target Deviation", "Evaluated Baseline Rows", "Identified Anomaly Skew"],
                        "Value": [f"{metric_scale}%", sample_volume, "High Variance / Left Skewed"]
                    })
                    
                    st.dataframe(summary_metrics, use_container_width=True)
                    
                    csv_metrics = summary_metrics.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Export Summary Metrics Dataset (.csv)",
                        data=csv_metrics,
                        file_name="operational_metrics_summary.csv",
                        mime="text/csv"
                    )
                    
            except Exception as e:
                st.error("An error occurred during execution. Please check your configuration framework state.")
