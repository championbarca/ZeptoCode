from typing import Optional, Dict, Any
import os
import statistics
from datetime import datetime
import pytz
from pydriller import Repository
from pydriller.domain.commit import ModifiedFile
from openai import OpenAI

OPENAI_KEY = "YOUR_OPENAI_KEY"
openai_client = OpenAI(api_key=OPENAI_KEY)

def get_code_snippet(file: ModifiedFile) -> Optional[str]:
    """
    Extracts a code snippet from a file between specified start and end lines.
    """
    filename = file.new_path
    start_line = file.changed_methods[0].start_line
    end_line = file.changed_methods[-1].end_line

    if not os.path.exists(filename):
        # Logging error for non-existent file
        print(f"File not found: {filename}")
        return None

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
        return ''.join(lines[start_line - 1:end_line])
    except OSError as e:
        # Logging error for file operation issues
        print(f"Error reading file {filename}: {e}")
        return None
    
def get_last_checkin(repo_path: str, last_review_date: datetime) -> Dict[str, str]:
    """
    Retrieves code snippets from commits made after the last review date.
    """
    code_snippets = {}
    utc_last_review_date = last_review_date.astimezone(pytz.UTC)

    for commit in Repository(repo_path).traverse_commits():
        if commit.committer_date.astimezone(pytz.UTC) <= utc_last_review_date:
            continue

        for file in commit.modified_files:
            if file.added_lines > 0 and file.changed_methods:
                code_snippet = get_code_snippet(file)
                if code_snippet and len(code_snippet) >= 10:
                    code_snippets[file.new_path] = code_snippet

    return code_snippets

def create_prompt(code_snippet: str) -> Dict[str, str]:
    """
    Creates a set of prompts for reviewing different aspects of code.
    """
    metrics = ["code quality", "bugs"]
    return {
        metric: (
            f"I want to review this part of the code for {metric}.\n\n"
            f"{code_snippet}"
        ) for metric in metrics
    }


def query_chatgpt(client: OpenAI, query: str) -> Optional[str]:
    """
    Queries the OpenAI ChatGPT model and returns the response.
    """
    try:
        completion = client.chat.completions.create(messages=[{"role": "user", "content": query}], model="gpt-4")
        return completion.choices[0].message.content
    except Exception as e:
        # Logging the error from API call
        print(f"Error querying ChatGPT: {e}")
        return None


# Main script execution
repo_path = 'YOUR_REPO_PATH'
last_review_date = LAST_REVIEW_DATE #datetime.strptime("2023-12-20", "%Y-%m-%d")
code_snippets = get_last_checkin(repo_path, last_review_date)

code_grades = []
for code_snippet in code_snippets.values():
    prompt = create_prompt(code_snippet)["code quality"]
    response = query_chatgpt(openai_client, prompt)
    grade_query = f"Grade the code snippet on a scale of 1 to 10 for code quality. "\
                  f"1 being the lowest and 10 being the highest.\n\n{code_snippet}"
    grade_response = query_chatgpt(openai_client, grade_query)
    code_grades.append(grade_response)

valid_grades = [float(grade) for grade in code_grades if grade.isdigit()]
if valid_grades:
    avg_grade = statistics.mean(valid_grades)
    print("Average Code Grade: ", avg_grade)
else:
    print("No valid grades received.")