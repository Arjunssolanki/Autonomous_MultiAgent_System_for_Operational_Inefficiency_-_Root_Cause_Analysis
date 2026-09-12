import streamlit as st
import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

from main import run_operational_analysis

st.set_page_config(page_title="Agentic BA Analytics Workspace", layout="wide")

st.title("Autonomous Operational Inefficiency & Root-Cause Analyst")
st.subheader("Leveraging Multi-Agent AI to translate data operational bottlenecks into business strategy.")

user_input = st.text_area(
    "Enter an operational problem statement or text-based report snippet to analyze:",
    placeholder="Example: Regional distribution hubs are reporting a 15% increase in transit delivery lag times..."
)

if st.button("Run Multi-Agent Analysis"):
    if user_input.strip() == "":
        st.warning("Please provide a valid business problem statement to initiate the workflow.")
    else:
        with st.spinner("Agents are collaborating! Running data tracking and strategic analysis loops..."):
            try:
                final_report = run_operational_analysis(user_input)
                
                st.success("Analysis Complete!")
                st.markdown("### Final Generated Business Strategy & Requirements")
                st.info(final_report)
                
            except Exception as e:
                st.error("An error occurred during execution. Please check your configuration framework state.")
