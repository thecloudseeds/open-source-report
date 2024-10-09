"""
This module assesses the documentation quality of GitHub repositories.
It analyzes various repository aspects such as:

    - Existence of basic documentation files like `README.md`.
    - Presence of a "docs" folder indicating dedicated documentation.
    - Contents of README files, searching for "contributing," "description,"
      and instructions on "installation," "running," or "starting" the project.
    - Existence of setup files (`setup.py`, `requirements.txt`, etc.).
    - Links or files related to API documentation.
    - Existence of documentation-related topics/tags

The score for documentation quality is determined based on the presence and contents
of these elements.
"""
import ast
from typing import Optional, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from src.github_api import GitHubAPI

API_DOC_KEYWORDS = [
    'swagger', 'openapi', 'postman', 'api docs', 'rest api', 'documentation',
    'endpoints', 'swagger.json', 'openapi.json', 'postman_collection.json',
    'api-docs', 'api-spec',
]


class GitHubDocAssessor(GitHubAPI):
    """
    Assesses the documentation quality of a GitHub repository based on various factors.
    """

    def __init__(self, row: Dict):
        """
        Initializes the DocumentationAssessor with a row from the repository DataFrame.

        Args:
            row (Dict): A row representing a repository from the DataFrame.
            token (Optional[str], optional): GitHub token for API authentication. Defaults to None.
        """

        super().__init__()  # Call the GitHubAPI class constructor for logger setup

        self.row = row
        repo_owner = self.row['repo_html_url'].split("/")[-2]
        repo_name = self.row['repo_html_url'].split("/")[-1]
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

    def check_readme_guidelines(self, filename: str) -> int:
        """
        Checks a README file for CONTRIBUTING guidelines, how-to-run instructions, and a description.

        Returns: A score representing the number of guidelines found in the README:
            - 1 points: for each of[ CONTRIBUTING, how-to-run instructions, and a description] are found.
            - 1 point : for every guideline found.
            - 0 points: If none of the guidelines are found.
        """

        readme_url = urljoin(self.base_url, f'/blob/master/{filename}')
        readme_data = self._get(readme_url)
        contribution = 0
        how_to_run = 0
        description = 0

        if readme_data:
            soup = BeautifulSoup(readme_data.content, 'html.parser')
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

            for heading in headings:
                if 'contribut' in heading.text.lower():
                    contribution = 1
                if 'description' in heading.text.lower():
                    description = 1
                if any(word in heading.text.lower()
                       for word in ['install', 'run', 'start', 'venv']):
                    how_to_run = 1

        return contribution + how_to_run + description

    def check_api_documentation(self) -> int:
        """
        Checks for the presence of API documentation within a repository.

        Returns:
            - 3 points: If API documentation links or files are found.
            - 0 points: If no API documentation is found.
        """
        api_docs_found = 0

        api_response = self._get(self.base_url)
        if "content" not in api_response or api_response["content"] is None:
            self.logger.warning("Missing content in the repository response.")
            return 0  # Return 0 score since API content is not found
        else:
            soup = BeautifulSoup(api_response['content'], 'html.parser')

            # Check for API documentation links in README and other files
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if any(keyword in href.lower()
                       for keyword in API_DOC_KEYWORDS):
                    api_docs_found = 3
                    break

        # Check for API documentation files directly within the repository
        if api_docs_found == 0:
            for file in soup.find_all('a', {'class': 'js-navigation-open'}):
                filename = file.text.strip()
                if any(keyword in filename.lower()
                       for keyword in API_DOC_KEYWORDS):
                    api_docs_found = 3
                    break

        return api_docs_found

    def assess_documentation(self) -> int:
        """
        Assesses the documentation quality based on the presence of specific files, content, and links.

        Returns: A score representing the overall documentation quality, where:
            - Higher score = Better documentation
            - Score is determined based on the presence of:
                - README guidelines (CONTRIBUTING, how-to-run, description)
                - Setup files (setup.py, requirements.txt, etc.)
                - "docs" directory
                - API documentation
        """
        contribution = 0
        setup_file = 0
        docs_dir = 0
        repo_desc = 0

        api_docs = self.check_api_documentation()
        filenames = ast.literal_eval(
            self.row["filenames"]) if isinstance(
            self.row["filenames"],
            str) else self.row["filenames"]

        if len(filenames) == 0:
            self.logger.info(
                "Repository %s has no files - score: 0.",
                self.base_url)
            return 0

        readme_files = [
            f for f in filenames if f.lower().startswith('readme.')]
        if readme_files:
            readme_file = readme_files[0]
            readme_score = self.check_readme_guidelines(readme_file)
        else:
            readme_score = 0

        if self.row['repo_description'] or self.row['topics']:
            repo_desc = 0
        else:
            repo_desc = 1

        # Check for intensive documentation
        if 'doc' in self.row["filenames"]:
            docs_dir = 3

        if 'CONTRIBUTING.md' in self.row["filenames"]:
            contribution = 2

        # Check for specific setup files
        setup_files = [
            'setup.py',
            'requirements.txt',
            'package.json',
            'environment.yml',
            'Pipfile',
            'setup.cfg',
            'config',
            '.gitignore',
            'LICENCE',
            'SUPPORT.md',
            'SECURITY.md',
        ]
        setup_file = sum(1 for file in setup_files if file in filenames)

        results = (
            contribution
            + readme_score
            + setup_file
            + docs_dir
            + repo_desc
            + api_docs
        )
        self.logger.info(
            "Repository %s has score: %s.",
            self.base_url,
            results)

        return results


# if __name__ == "__main__":

#     import pandas as pd
#     from tqdm import tqdm

#     df = pd.read_csv("./data/egypt_open_source_data.csv").sample(10)

#     scores = []
#     for index, row in tqdm(df.iterrows(), total=len(df),
#                            desc="Documentation Scoring"):
#         assessor = GitHubDocAssessor(row)
#         df.loc[index, 'documentation_score'] = assessor.assess_documentation()

#     df.to_csv("./data/docs.csv", index=False)
