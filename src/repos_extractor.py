import os
import re
import csv
import json
import base64
import binascii

from typing import Optional, Dict, List, Tuple, Set
from src.github_api import GitHubAPI


class GitHubRepoExtractor(GitHubAPI):
    """
    This class extracts relevant repository details from GitHub repositories,
    focusing on database usage and other key metrics, including documentation files,
    contributors, commits, issues, pull requests, and CI/CD tools.
    """

    def __init__(self):
        super().__init__()

        self.row = None
        self.base_url = None
        self.db_files, self.cicd_files = set(), set()
        self.doc_files, self.api_files = set(), set()

        self.db_keywords = self.load_db_keywords()

    def load_db_keywords(self) -> Dict:
        """Load database keywords from the configuration file."""

        db_keywords_file_path = os.path.join(
            self.json_dir, self.config["DB_KEYWORDS_FILENAME"])

        if not os.path.isfile(db_keywords_file_path):
            raise FileNotFoundError(f"{db_keywords_file_path} does not exist")

        with open(db_keywords_file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_repo_filenames(self) -> None:
        """
        Recursively retrieves all relevant filenames from a repository.
        Focuses on important files like database, CI/CD, and documentation files.
        """

        stack = [self.base_url + "/contents/"]
        visited_urls = set()

        # Create combined regex patterns for performance
        doc_pattern = re.compile(r"|".join(self.config["DOC_FILES_PATTERNS"]))
        db_pattern = re.compile(r"|".join(self.config["DB_FILES_PATTERNS"]))
        cicd_pattern = re.compile(
            r"|".join(self.config["CI_CD_PATTERNS"].keys()))
        api_pattern = re.compile(r"|".join(self.config["API_FILES_PATTERNS"]))
        unimportant_dirs_pattern = re.compile(
            r"|".join(self.config["UN_IMPORTANT_DIRS_PATTERNS"]))
        api_dirs_pattern = re.compile(
            r"|".join(self.config["API_DIRS_PATTERNS"]))

        beginning = True
        while stack:
            contents_url = stack.pop()

            if contents_url in visited_urls:
                continue
            visited_urls.add(contents_url)

            data = self._get(contents_url)
            if not data:
                self.logger.warning(
                    "Failed to retrieve contents %s", contents_url)
                continue

            # Check for too much data and skip the loop if necessary
            if len(data) > 20 and not beginning:
                self.logger.warning(
                    "Too much data retrieved: [%d] for: %s", len(data), contents_url)
                continue
            beginning = False

            # Initialize sets for each file type
            important_dirs = set()

            # Filter important files in a single pass using combined regex patterns
            for item in data:
                if item["type"] == "file":
                    file_path = item["path"]
                    file_name = item["name"]

                    if doc_pattern.search(file_name):
                        self.doc_files.add(file_path)
                    elif db_pattern.search(file_name):
                        self.db_files.add(file_path)
                    elif cicd_pattern.search(file_name):
                        self.cicd_files.add(file_path)
                    elif api_pattern.search(file_name):
                        self.api_files.add(file_path)

                elif item["type"] == "dir":
                    if not unimportant_dirs_pattern.search(item["name"]):
                        important_dirs.add(item["path"])
                        # Check if the directory is an API directory
                        if api_dirs_pattern.search(item["name"]):
                            self.api_files.add(item["path"])
            # Add important directories to the stack
            if important_dirs:
                stack.extend(
                    f"{self.base_url}/contents/{dir_name}" for dir_name in important_dirs)

        # Logging the results
        self.logger.info("Doc files: %s", list(self.doc_files))
        self.logger.info("DB files: %s", list(self.db_files))
        self.logger.info("CI/CD files: %s", list(self.cicd_files))
        self.logger.info("API files: %s", list(self.api_files))

    def get_contribs_count(self, row) -> Optional[int]:
        """Fetches the number of contributors for a given repository."""

        if row is None:
            raise ValueError("row must not be null")

        self.row = row[['owner', 'repo_name', 'repo_html_url']]
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']
        self.base_url = f"{self.config['API_BASE_URL']}/repos/{repo_owner}/{repo_name}"

        contributors_url = f"{self.base_url}/contributors"

        data = self._get(contributors_url)
        if data is None:
            self.logger.warning(
                "Failed to retrieve contributors count for: %s", contributors_url)
            return -1

        self.logger.info("Contributors count: %s", len(data))

        return len(data)

    def get_ci_cd_tools(self) -> str:
        """
        Collects all CI/CD tools from the configuration based on the filenames in cicd_files
        and returns them as a single string joined with '&'.
        Returns:
            str: A string of CI/CD tools joined by '&', or an empty string if none found.
        """
        ci_cd_tools = set()  # Use a set to avoid duplicates

        if self.cicd_files:

            # Iterate through each CI/CD file
            for cicd_file in self.cicd_files:
                # Check which patterns match the filename and collect corresponding tools
                for pattern, tool_name in self.config["CI_CD_PATTERNS"].items():
                    if re.search(pattern, cicd_file):
                        ci_cd_tools.add(tool_name)

            return list(ci_cd_tools)

        return list(ci_cd_tools)

    def get_commits_count(self) -> Optional[int]:
        """Fetches the number of commits for a given repository."""

        commits_url = f"{self.base_url}/commits"
        data = self._get(commits_url)

        if data:
            self.logger.info("Commits count: %s", len(data))
            return len(data)

        return -1

    def get_issues_count(self) -> Optional[Tuple[int, int]]:
        """Fetches open and closed issues counts from a GitHub repository."""

        # Get all issues, both open and closed
        data = self._get(f"{self.base_url}/issues", params={"state": "all"})
        if data:
            open_count = sum(1 for issue in data if issue["state"] == "open")
            closed_count = sum(
                1 for issue in data if issue["state"] == "closed")

            self.logger.info(
                "Issues count: open - %s, closed - %s", open_count, closed_count)

            return open_count, closed_count

        return -1, -1

    def get_pull_requests_count(self) -> Optional[Tuple[int, int, int]]:
        """
        Fetches open, closed and merged pull request counts from a GitHub repository.
        """
        pulls_url = f"{self.base_url}/pulls"
        data = self._get(pulls_url, params={"state": "all"})

        if data:

            open_count = sum(
                1 for pull_request in data if pull_request["state"] == "open")
            closed_count = sum(
                1 for pull_request in data if pull_request["state"] == "closed")
            merged_count = sum(
                1 for pull_request in data if pull_request["merged_at"] is not None)

            self.logger.info("Pull Requests count: open - %s, closed - %s , merged - %s",
                             open_count, closed_count, merged_count)

            return open_count, closed_count, merged_count

        return -1, -1, -1

    def get_tags(self) -> Optional[List[str]]:
        """Fetches tags list for a specific repository."""

        tags_url = f"{self.base_url}/tags"
        data = self._get(tags_url)

        if data:
            tags = [tag["name"] for tag in data]
            self.logger.info("Tags: %s", tags)
            return tags

        return []

    def get_dependencies(self) -> Optional[List[str]]:
        """
        Fetches dependency information using the GitHub dependency graph API.
        """
        url = f"{self.base_url}/dependency-graph/sbom"
        response = self._get(url)

        if response and "sbom" in response and "packages" in response["sbom"]:
            # Extract the package names from the response
            packages = [package["name"]
                        for package in response["sbom"]["packages"] if package]
            package_names = [package.split(":")[-1] for package in packages]

            # Return the list of package names, excluding the first element (which is the package name itself)
            return package_names[1:]

        return []

###################################################################################
# Extracting Database Type
###################################################################################

    def search_db_type_in_content(self, content: str) -> Optional[List[str]]:
        """
        Optimized helper function to search for database keywords within text content.
        """
        if not isinstance(content, str):
            self.logger.warning(
                "Content must be a string. Received type: %s" % type(content))
            return None

        db_type = set()
        # Compute set of keywords for faster intersection.
        content_set = set(content.lower().split())

        # Use set intersection to check if any keyword is present.
        for db, keywords in self.db_keywords.items():
            if content_set.intersection(keywords):
                self.logger.info("Find Database type %s", db)
                db_type.add(db)
            else:
                continue

        return list(db_type)

    def search_db_type_in_lang(self) -> Optional[str]:
        """Search for database languages within the primary repository language."""

        if not isinstance(self.row['language'], str):
            return ''

        if self.row['language'] in self.config["DB_LANGUAGES"]:
            self.logger.info("Find Database type %s", self.row['language'])
            return self.row['language']

        return ''

    def search_db_type_in_files(self) -> Optional[List[str]]:
        """
        Search for database types in the list of files within a repository.
        Args:
            row (Dict): A row from the DataFrame containing the repository details.
        Returns:
            Dict[str, str]: A dictionary with the detected database types.
        """
        if not self.db_files:  # check empty set
            return []

        db_type = []

        # Iterate over the files and search for database types in their content
        for file_name in self.db_files:

            download_url = f"{self.base_url}/contents/{file_name}"
            response = self._get(download_url)

            if response is None:
                self.logger.warning(
                    "No response from GitHub API for %s", download_url)
                continue

            # Decode content based on encoding type
            try:
                encoding = response.get(
                    "encoding", "utf-8")  # Get encoding from response
                if encoding == "base64":
                    file_content = base64.b64decode(response.get("content", "")).decode(
                        "utf-8")
                elif encoding == "hex":
                    file_content = bytes.fromhex(response.get("content", "")).decode(
                        "utf-8")
                else:
                    file_content = response.get("content", "").encode(
                        encoding).decode("utf-8")

                # Search for database types in the file content
                db_type.extend(self.search_db_type_in_content(file_content))

            except (binascii.Error, UnicodeDecodeError, OSError) as e:
                self.logger.error("Error while decoding file content: %s", e)

        return db_type

    def get_database_type(self):
        """Search for database types in the repository."""
        db_type = []
        db_type.append(self.search_db_type_in_lang())

        if len(self.db_files) > 0:
            db_type.extend(self.search_db_type_in_files())

        return db_type

    ###################################################################################
    # Put all togeather and write the details row in the file
    ###################################################################################

    def extract_repo_details(self, row: Dict, output_path: str) -> Dict:
        """Extracts relevant repository details including filenames and CI/CD tools."""

        # Initialize the row
        self.row = row[['owner', 'repo_name',
                        'repo_html_url', 'language']]
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']
        self.base_url = f"{self.config['API_BASE_URL']}/repos/{repo_owner}/{repo_name}"

        # Get the issues, pull requests, and commits counts as well as ci/cd tool for the repository
        self.row['commits_count'] = self.get_commits_count()
        self.row['open_issues'], self.row['closed_issues'] = self.get_issues_count()
        self.row['open_pull_requests'], self.row['closed_pull_requests'], self.row['merged_pull_requests'] = self.get_pull_requests_count()

        # Get the tags for the repository
        self.row['tags'] = json.dumps(self.get_tags())

        # Get the dependencies for the repository and limit the number of
        # dependencies to be stored in csv 20 for storage purpose
        # deps = self.get_dependencies()
        # self.row['dependencies'] = json.dumps(deps[:10])

        # Assign value to self.repo_filenames and get documentation files
        self.get_repo_filenames()
        self.row['doc_files'] = json.dumps(list(self.doc_files))
        self.row['cicd_files'] = json.dumps(list(self.cicd_files))
        self.row['db_files'] = json.dumps(list(self.db_files))
        self.row['api_files'] = json.dumps(list(self.api_files))

        # Get CI/CD tools used in the repository
        self.row['ci_cd_tool'] = self.get_ci_cd_tools()

        # Get database types
        self.row['database_types'] = json.dumps(self.get_database_type())

        # Preprocess row for CSV writing
        self.row = {key: value if value is not None else '' for key,
                    value in self.row.items()}

        # Save the details to a CSV
        with open(output_path, 'a', newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.row.keys())
            if file.tell() == 0:
                writer.writeheader()
            writer.writerow(self.row)

        self.logger.info("Raw saved in the file\n")
        self.logger.info(self.row)
        self.logger.info(f"{'='*200}\n")

        # return deps
