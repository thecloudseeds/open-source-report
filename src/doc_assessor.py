import re
import csv
import ast
import json
import base64
import binascii

from typing import Dict, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from src.github_api import GitHubAPI


class GitHubDocAssessor(GitHubAPI):
    """
    Assesses the documentation quality of a GitHub repository based on various factors.
    """

    def __init__(self):
        super().__init__()

        self.row = None
        self.base_url = ""
        # Cache for filenames and readme content. So that we don't have to fetch the filenames multiple times.
        self.doc_files, self.api_files = set(), set()

        # The API documentation keywords are the words that are used to search for API documentation.
        # We use a regular expression to search for these words in the repository's description and topics.
        api_doc_keywords = r"\b(?:swagger|openapi|postman|api\s*docs|rest\s*api|documentation|endpoints|swagger\.json|openapi\.json|postman_collection\.json|api-[Dd]ocs|api-spec)\b"
        self.api_doc_keywords = re.compile(api_doc_keywords)

    def get_readme_content(self) -> str:
        """
        This method is used to fetch the content of the README file in the repository.
        It handles cases where the README filename is stored incorrectly in the file (e.g., readme.md instead of README.md).

        Returns:
        --------
            The content of the README file.
        """
        # Search for README file, considering potential case mismatch
        readme_files = [f for f in self.doc_files if 'readme' in f.lower()]

        # If no README file is found, we set the content to an empty string.
        if not readme_files:
            self.logger.info(f"No README file found for this repo")
            return ""

        # Add common README variants
        readme_files.extend(["README.md", "README"])
        readme_content = ""
        # Iterate over the README files and fetch their content
        for readme_file in readme_files:
            # Construct the URL of the README file
            readme_url = f"{self.base_url}/contents/{readme_file}"
            self.logger.debug(f"Fetching README file from: {readme_url}")
            response = self._get(readme_url)

            try:
                # Get encoding from response
                encoding = response["encoding"]
                self.logger.info(f"Response encoding: {encoding}")
                if encoding == "base64":
                    # Decode the base64 encoded content
                    readme_content += base64.b64decode(
                        response["content"]).decode("utf-8")
                elif encoding == "hex":
                    # Decode the hex encoded content
                    readme_content += bytes.fromhex(
                        response["content"]).decode("utf-8")
                else:
                    # Decode the content using the specified encoding
                    readme_content += response["content"].encode(
                        encoding).decode("utf-8")

            except (binascii.Error, UnicodeDecodeError, OSError) as e:
                # Handle any errors that occur while decoding the README content
                self.logger.warning(
                    "Error while decoding README content: %s", e)

        return readme_content

    def check_readme_guidelines(self, readme_content) -> int:
        """
        Checks a README file for contributing guidelines, how-to-run instructions, and other common sections.

        Returns:
        --------
            A score representing the number of guidelines found in the README.
        """
        # A list of regular expressions representing the guidelines we want to check for.
        # We use case-insensitive matching to make sure we catch variations in capitalization.
        guidelines = [
            # Check for contributing guidelines
            r'(?:contributing|contributions|contribution)',
            # Check for getting started or quickstart instructions
            r'(?:run|start|install|use|get started|getting started|quickstart|installation)',
            # Check for tutorials or example code
            r'(?:tutorial|example|tutorials|examples|usage|use cases|applications|use case|application)'
        ]

        # Log the guidelines we're checking for
        self.logger.debug(f"Checking guidelines: {guidelines}")

        if readme_content == '':
            return 0

        readme_score = 0
        for guideline in guidelines:
            if re.search(guideline, readme_content, re.IGNORECASE):
                self.logger.info(f"Found guideline: {guideline}")
                readme_score += 1
            else:
                self.logger.info(f"Did not find guideline: {guideline}")

        self.logger.info(f"Readme score: {readme_score}")

        return readme_score

    # def check_api_documentation(self, readme_content) -> int:
    #     """
    #     Checks for the presence of API documentation links or files within a repository.

    #     Returns:
    #     --------
    #         - 3 points if API documentation links or files are found.
    #         - 0 points if no API documentation is found.
    #     """
    #     # Check if the repository's description or topics contain API documentation keywords
    #     if self.api_doc_keywords.search(self.row['repo_description']) or \
    #             self.api_doc_keywords.search(self.row['topics']):
    #         self.logger.info(
    #             "Found API documentation keywords in description or topics.")
    #         return 2

    #     # Check if the repository's README file contains API documentation keywords
    #     if self.api_doc_keywords.search(readme_content):
    #         self.logger.info(
    #             "Found API documentation keywords in the README file.")
    #         return 2

    #     # Search for API documentation files in the repository's files
    #     for api_pattern in self.config['API_FILES_PATTERNS']:
    #         if self.api_files):
    #             self.logger.info(
    #                 "Found API documentation file matching pattern: %s", api_pattern)
    #             return 3
    #     # No API documentation found
    #     self.logger.info("No API documentation found in the repository.")
    #     return 0

    def assess_repo_doc(self, row: Dict) -> int:
        """
        Assesses the documentation quality of a repository based on the presence
        of specific files, content, and links.
        Args:
        -----
            row (Dict): A dictionary containing the repository information.
        Returns:
        --------
            A score representing the overall documentation quality.
        """
        self.row = row
        # Fetch the base URL for the repository
        self.base_url = f"{self.config['API_BASE_URL']}/repos/{self.row['owner']}/{self.row['repo_name']}"
        # Fetch the list of documentation files and api_files in the repository
        self.doc_files = set(ast.literal_eval(self.row['doc_files']))
        self.api_files = set(ast.literal_eval(self.row['api_files']))

        # Repo description, topic and tags score
        basic_desc = self.row['repo_description'] + \
            self.row['topics']+self.row['tags']
        repo_desc = 1 if basic_desc else 0

        # Check for API documentation
        api_scroe = 3 if self.api_files else 0

        # Readme content and guidelines assessment
        readme_content = self.get_readme_content()
        readme_score = self.check_readme_guidelines(readme_content)

        # Total score calculation
        total_score = (repo_desc + readme_score + api_scroe)

        self.logger.info("Repository %s has score: %s.",
                         self.base_url, total_score)

        return total_score
