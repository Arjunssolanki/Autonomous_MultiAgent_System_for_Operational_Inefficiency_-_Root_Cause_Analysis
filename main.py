import os
import time
from datetime import datetime
from dotenv import load_dotenv
import boto3
import mlflow
from crewai import Agent, Task, Crew, Process, LLM

import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg

load_dotenv()

custom_llm = LLM(
    model="gemini/gemini-3.6-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2
)

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"))
mlflow.set_experiment("Agentic_BA_Operational_Analysis")

s3_client = boto3.client('s3')
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

data_analyst = Agent(
    role="Senior Operations Data Analyst",
    goal="Identify and isolate statistically significant process delays and metrics anomalies within raw data structures.",
    backstory="You are an expert data detective. You analyze data patterns, find processing bottlenecks, and pinpoint exactly where operational timelines are falling behind.",
    verbose=True,
    allow_delegation=False,
    llm=custom_llm
)

business_analyst = Agent(
    role="Lead Business Systems Analyst",
    goal="Translate raw data anomalies into clear root causes, business impacts, and actionable requirements.",
    backstory="You bridge the gap between technical data metrics and strategic planning. You take identified data bottlenecks and outline why they happen, how they hurt the business, and how to fix them.",
    verbose=True,
    allow_delegation=False,
    llm=custom_llm
)

def run_operational_analysis(business_problem):
    with mlflow.start_run() as run:
        print(f"\n[MLFLOW] Active Run Context Initialized: ID {run.info.run_id}")
        mlflow.log_param("model_name", "gemini-3.6-flash")
        mlflow.log_param("framework", "CrewAI")
        mlflow.log_text(business_problem, "input_problem_statement.txt")

        start_time = time.time()

        task_investigate = Task(
            description=f"Analyze the following operational issue and isolate the core data-driven indicators: {business_problem}",
            expected_output="A structured summary identifying the clear data anomalies, process steps experiencing delays, and measurable metric deviations.",
            agent=data_analyst
        )

        task_custom_requirements = Task(
            description="Review the data anomalies discovered by the investigator. Conduct a root-cause analysis and translate these findings into business requirements.",
            expected_output="A complete operational report containing: 1. Root-Cause Analysis 2. Business Impact Summary 3. Actionable Business Requirements for the engineering team.",
            agent=business_analyst
        )

        operational_crew = Crew(
            agents=[data_analyst, business_analyst],
            tasks=[task_investigate, task_custom_requirements],
            process=Process.sequential,
            verbose=True
        )

        raw_result = operational_crew.kickoff()
        final_report = str(raw_result)

        elapsed_time = time.time() - start_time
        mlflow.log_metric("execution_duration_seconds", round(elapsed_time, 2))
        
        mlflow.log_text(final_report, "final_strategic_requirements.md")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_filename = f"ba_analysis_report_{timestamp}.md"
        s3_key_path = f"operational_reports/{s3_filename}"

        try:
            print(f"[AWS S3] Uploading asset copy to folder target: {s3_key_path}...")
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key_path,
                Body=final_report,
                ContentType='text/markdown'
            )
            print("[AWS S3] Asset ingestion successfully completed!")
            mlflow.log_param("s3_destination_uri", f"s3://{S3_BUCKET}/{s3_key_path}")
        except Exception as s3_error:
            print(f"⚠️ S3 Storage Operation Delayed: {str(s3_error)}")
            mlflow.log_param("s3_upload_status", "failed")

        return final_report

if __name__ == "__main__":
    print("## Initiating Multi-Agent Analytics Framework Engine ##\n")
    user_problem = input("Please enter the operational problem statement to analyze: ")
    
    if user_problem.strip():
        result = run_operational_analysis(user_problem)
        print("\n## Final Extracted Strategic Output ##\n")
        print(result)
    else:
        print("Execution cancelled: A valid problem statement is required.")
