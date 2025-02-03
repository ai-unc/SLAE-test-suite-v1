import subprocess
from datetime import datetime
from typing import List, Set, Literal
import csv
import io
import requests
import json
import base64
from dotenv import load_dotenv
import os

load_dotenv()


class Result:
    document_name: str
    independent_variable: str
    dependent_variable: str
    predicted_classification: str
    coded_classification: str

    def __init__(
        self,
        document_name: str,
        independent_variable: str,
        dependent_variable: str,
        predicted_classification: Literal["+", "-", "I", "N/A"],
        coded_classification: Literal["+", "-", "I", "N/A"],
    ):
        self.document_name = document_name
        self.independent_variable = independent_variable
        self.dependent_variable = dependent_variable
        self.predicted_classification = predicted_classification
        self.coded_classification = coded_classification

    def to_csv_row(self):
        return [
            self.document_name,
            self.independent_variable,
            self.dependent_variable,
            self.predicted_classification,
            self.coded_classification,
        ]


class ResultsLogger:
    __executed_by: str
    __commit_hash: str
    __pipeline_repo_url: str
    __datetime: str
    __runtime: datetime = None
    __data: List[Result] = []
    __unique_documents: Set[str] = set()
    __total_correct: int = 0
    # Debug
    is_verbose: bool

    def __init__(self, is_verbose=True):
        self.is_verbose = is_verbose

        # Get pipeline repo url
        output = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True
        )
        if output.returncode != 0:
            print(output.stderr)
            exit(1)
        self.__pipeline_repo_url = output.stdout[:-5]

        # Check in and commit code
        output = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        if output.returncode != 0:
            print(output.stderr)
            exit(1)
        output = subprocess.run(
            ["git", "commit", "-m", "Running test"], capture_output=True, text=True
        )
        if output.returncode != 0:
            if output.returncode == 1:
                print(
                    "No changes detected in code base. Make changes before trying to run another test."
                )
            else:
                print(output.stderr)
            exit(1)

        # Get commit hash
        output = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        )
        if output.returncode != 0:
            print(output.stderr)
            exit(1)
        self.__commit_hash = output.stdout[:-1]

        # Get git user name
        output = subprocess.run(
            ["git", "show", "-s", "--format='%an <%ae>'", "HEAD"],
            capture_output=True,
            text=True,
        )
        if output.returncode != 0:
            print(output.stderr)
            exit(1)
        self.__executed_by = output.stdout[:-1]

        self.__datetime = datetime.today().strftime("%m-%d-%Y-%H:%M:%S")

        print(
            f"Created Results Logger for {self.__pipeline_repo_url}/commit/{self.__commit_hash}"
        )

    def log_result(
        self,
        document_name: str,
        independent_variable: str,
        dependent_variable: str,
        predicted_classification: str,
        coded_classification: str,
    ) -> None:
        if self.__runtime == None:
            self.__runtime = datetime.now()
            print(f"Starting test at {self.__runtime} executed by {self.__executed_by}")

        self.__data.append(
            Result(
                document_name,
                independent_variable,
                dependent_variable,
                predicted_classification,
                coded_classification,
            )
        )
        self.__unique_documents.add(document_name)
        if predicted_classification == coded_classification:
            self.__total_correct += 1
        if self.is_verbose:
            print(
                f"{document_name}: {independent_variable} -> {dependent_variable}, Predicted: {predicted_classification}, Coded: {coded_classification}"
            )

    def save_results(self):
        self.__runtime = datetime.now() - self.__runtime
        print(
            f"Total Accuracy: {(self.__total_correct / len(self.__data) * 100):.2f}% ({self.__total_correct} / {len(self.__data)} Coded Relations)"
        )
        print(f"Test Runtime: {self.__runtime}")

        output = io.StringIO()
        csv_writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        csv_writer.writerow(
            ["Pipeline", f"{self.__pipeline_repo_url}/commit/{self.__commit_hash}"]
        )
        csv_writer.writerow(["Executed By", self.__executed_by])
        csv_writer.writerow(["Date", self.__datetime])
        csv_writer.writerow(["Runtime", self.__runtime])
        csv_writer.writerow(["Total Documents", len(self.__unique_documents)])
        csv_writer.writerow([])
        csv_writer.writerow(
            [
                "Document Name",
                "Independent Variable",
                "Dependent Variable",
                "Predicted Classification",
                "Coded Classification",
            ]
        )
        for result in self.__data:
            csv_writer.writerow(result.to_csv_row())
        csv_string = output.getvalue()
        output.close()

        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
        encoded_content = base64.b64encode(csv_string.encode()).decode()
        url = f"https://api.github.com/repos/ai-unc/SLAE-test-suite-v1/contents/results/{self.__pipeline_repo_url.split('/')[-1]}/{self.__datetime}.csv"
        payload = {
            "message": "Automated Commit by Test Suite",
            "content": encoded_content,
        }
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.put(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 201:
            print("Results uploaded to Test Suite repository")
        else:
            print("Failed to upload results")
            print("Status Code:", response.status_code)
            print("Response:", response.json())
            print("Writing results to local csv file")
            with open(
                f"local_{self.__pipeline_repo_url.split('/')[-1]}_{self.__datetime}.csv",
                "w",
            ) as file:
                file.write(csv_string)
