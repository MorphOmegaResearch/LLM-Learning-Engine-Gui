from modules.dev_tools.tkinter_analyzer import TkinterAnalyzer
import os

def run_dev_analysis():
    analyzer = TkinterAnalyzer()
    project_dir = os.getcwd()
    print(f"Analyzing project: {project_dir}")
    analysis = analyzer.select_project(project_dir)
    
    print("\n--- Analysis Statistics ---")
    for key, value in analysis.stats.items():
        print(f"{key}: {value}")
    
    print("\n--- Tkinter Specific Issues ---")
    if not analysis.tk_specific_issues:
        print("None found.")
    for issue in analysis.tk_specific_issues:
        print(f"[{issue.severity.upper()}] {issue.file}:{issue.line} - {issue.code}: {issue.message}")

    print("\n--- General Issues (Sample) ---")
    for issue in analysis.issues[:10]:
        print(f"[{issue.severity.upper()}] {issue.file}:{issue.line} - {issue.message}")

if __name__ == "__main__":
    run_dev_analysis()
