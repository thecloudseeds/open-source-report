import re
import ast
import json
import base64
import binascii

from typing import Dict
from src.github_api import GitHubAPI


class GitHubDocAssessor(GitHubAPI):
    """
    Assesses the documentation quality of a GitHub repository based on various factors.
    """

    def __init__(self):
        """
        Initializes the GitHubDocAssessor class, setting up necessary attributes.

        base_url: The base URL of the repository.
        doc_files: A set of relevant documentation files.
        api_files: A set of API documentation files.
        """
        super().__init__()
        self.base_url = None
        self.doc_files = None  # A set of relevant documentation files
        self.api_files = None  # A set of API documentation files

    def decode_file(self, response: Dict) -> str:
        """
        Decode file content based on the encoding.
        Args:
        ------
            response (Dict): The response from the GitHub API containing the file content.
        Returns:
        --------
            str: The decoded content of the file.
        """
        try:
            content = response.get("content", "")
            if not content:
                return ""

            encoding = response.get("encoding", "utf-8")
            if encoding == "base64":
                # Decode base64 content
                content = base64.b64decode(content).decode(
                    "utf-8", errors="replace")
            elif encoding == "hex":
                # Decode hex content
                content = bytes.fromhex(content).decode(
                    "utf-8", errors="replace")

            # Check if the content is binary using magic numbers
            if content.startswith(b'\x89PNG') or content.startswith(b'\xFF\xD8'):
                self.logger.info(
                    "Binary file detected. Replacing binary content.")
                content = "[Binary content skipped]"

        except (binascii.Error, UnicodeDecodeError, TypeError) as e:
            self.logger.error("Error decoding file content: %s", e)

        return content

    def readme_guidelines_score(self) -> int:
        """Check README for common sections and return a score based on presence.

        This function assesses the quality of a repository's README file by checking
        for the presence of common sections like contributing guidelines, how-to-run
        instructions, and tutorials or examples.
        """
        contributing_pattern = r"(?i)(?:contributing|contributions|contribution)"
        run_instructions_pattern = r"(?i)(?:run|start|install|use|get\s+started|quickstart|installation)"
        tutorial_pattern = r"(?i)(?:tutorial|example|tutorials|examples|usage|use\s+cases|applications)"

        score = 0

        # Iterate over the files and search for common sections in their content
        readme_content = ""

        for readme_file in [f for f in self.doc_files if 'readme' in f.lower()]:

            self.logger.info("Checking README file: %s", readme_file)
            readme_url = f"{self.base_url}/contents/{readme_file}"
            response = self._get(readme_url)

            if not response:
                readme_file = readme_file.lower()
                readme_url = f"{self.base_url}/contents/{readme_file}"
                response = self._get(readme_url)

                if not response:
                    self.logger.warning(
                        "Failed to fetch README file: %s", readme_file)
                    continue

            readme_content += self.decode_file(response)

        self.logger.info("Decoded readme Content: %s", readme_content)

        if re.search(contributing_pattern, readme_content, re.IGNORECASE):
            self.logger.info("Found contributing guidelines.")
            # Score +1 for having a contributing guidelines section
            score += 1
        if re.search(run_instructions_pattern, readme_content, re.IGNORECASE):
            self.logger.info("Found how-to-run instructions.")
            # Score +1 for having a how-to-run instructions section
            score += 1
        if re.search(tutorial_pattern, readme_content, re.IGNORECASE):
            self.logger.info("Found tutorials or examples.")
            # Score +1 for having a tutorials or examples section
            score += 1

        self.logger.info("Readme scoring result: %s out of 3.", score)

        return score

    def assess_repo_doc(self, row: Dict) -> int:
        """
        Assesses repository documentation and returns a quality score.

        The score is a sum of the following components:
        - Presence of repository description: 1 point
        - Presence of API documentation files: 3 points
        - Presence of common sections in the README file: 1 point for each of the following sections:
            - Contributing guidelines
            - How-to-run instructions
            - Tutorials or examples
        """

        self.base_url = f"{self.config['API_BASE_URL']}/repos/{row['owner']}/{row['repo_name']}"

        try:
            # Parse the file lists from the row
            self.doc_files = set(ast.literal_eval(row['doc_files']))
            self.api_files = set(ast.literal_eval(row['api_files']))
        except:
            self.doc_files = set(row['doc_files'])
            self.api_files = set(row['api_files'])

        # Compute the basic scores
        try:
            basic_desc = row['repo_description'] + row['topics']
        except TypeError:
            basic_desc = ""

        repo_desc = 1 if not basic_desc else 0

        # Determine the exsitance of api and doc files
        api_score = 3 if self.api_files else 0
        doc_files_score = 1 if self.doc_files else 0

        # Compute the score for the README file
        if self.doc_files:
            self.logger.info("Checking Dic_file %s", self.doc_files)
            readme_score = self.readme_guidelines_score()
        else:
            readme_score = 0

        # Compute the total score
        total_score = repo_desc + api_score + readme_score + doc_files_score

        self.logger.info("Repo %s scored: %s out of 8",
                         self.base_url, total_score)

        return total_score
