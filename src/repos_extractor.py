"""
This module relies on a base `GitHubAPI` class and is used to extract detailed information from GitHub repositories.
The module extracts detailed information about GitHub repositories and analyzes various aspects such as 
files, contributors, commits, issues, pull requests, tags, and CI/CD Tools

The module is used in the `data_collection` module before calling it to collect data from the GitHub API.
"""
import csv
import json
# import urllib
# import signal
from typing import Optional, Dict, List
from src.github_api import GitHubAPI


class GitHubRepoExtractor(GitHubAPI):
    """    
    This class extracts data about GitHub repositories, processing information
    like file structure, contributors, and activity metrics. It uses the
    `GitHubAPI` class for communication with the GitHub API.
    """
    def __init__(self):
        """
        Initializes the GitHubRepoExtractor class.

        Args:
            - row (Dict): repository row.
            - base_url (str): The base URL of the GitHub repository.
            - repos_details (List[str]): A list of repository details to extract.
            - un_important_dir (List[str]): A list of unimportant directories to ignore.
            - db_files (List[str]): A list of database-related filenames to look for in the repository.
            - important_filenames (List[str]): A list of important filenames to look for in the repository.
        """
        super().__init__()
        self.row = None
        self.base_url = None
        self.repos_details = [
            'owner', 'repo_name', 'filenames', 'tags', 'dependencies',
            'issues', 'pull_requests', 'commits_count','ci_cd_tool']
        self.un_important_dir = [
            # Ignore directories containing static assets
            "images", "imgs", "img", "figures","figure","figs",
            # Ignore directories containing build artifacts
            "assets","asset", "__pycache__", "log","logs", ".git",
            # Ignore directories containing third-party code
            "3rdparty", "bin", "buildfiles", "darwin"]

        # List of important filenames to look for in the repository
        self.important_filenames = self.db_files + list(self.ci_cd.keys()) + self.doc_files
    
    def get_filenames(self) -> List[str]:
        """
        Recursively retrieves all filnames and directories within a repository.
        
        This method uses a stack to traverse the directory structure of the
        repository.

        Steps:
            1) It starts from the root directory and adds all files and
            directories to the stack. 
            2) Then, it iterates through the stack and
            processes each item. 
                a. If the item is a file and its name is in the list of important filenames,
                   it is added to the set of filenames. 
                b. If the item is a directory, it will be added to the stack if it is not 
                   in the list of unimportant directories. 
                c. If the directory is named "doc", "docs", "documentation" or "documentations",
                   it is added to the set of filenames even if it is in the list of unimportant directories.
        return: 
            A list of filenames within the repository.
        """
        if not self.base_url:
            raise ValueError("base_url must not be null")

        filenames = set()
        stack = [self.base_url + "/contents/"]

        while stack:
            contents_url = stack.pop()
            # contents_url = urllib.parse.quote(contents_url)
            # self.logger.info("Retrieving filenames for: %s", contents_url)
            data = self._get(contents_url)

            if not data:
                self.logger.warning("Failed to retrieve contents for: %s", contents_url)
                continue

            self.logger.info("Retrieved %d items for: %s", len(data), self.base_url)
            for item in data:
                if item["type"] == "file" and item["name"].lower() in self.important_filenames:
                    self.logger.info("Found file: %s", item["path"])
                    filenames.add(item["path"])

                elif item["type"] == "dir" and item["name"].lower() not in self.un_important_dir:
                    if item["name"].lower() in ["doc", "docs", "documentation", "documentations"]:
                        self.logger.info("Found directory: %s", item["name"])
                        filenames.add(item["name"])
                    else:
                        stack.append(item["url"])

        self.logger.info("Returning %d filenames", len(filenames))
        return list(filenames)

    def get_contribs_count(self, row) -> Optional[int]:
        """Fetches the number of contributors for a given repository."""
        
        self.row = row[['owner', 'repo_name', 'repo_html_url']]
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        contributors_url = f"{self.base_url}/contributors"

        data = self._get(contributors_url)
        if data:
            self.logger.info("Contributors count: %s", len(data))
            return len(data)

        return None
    def get_commits_count(self) -> Optional[int]:
        """Fetches the number of commits for a given repository."""

        commits_url = f"{self.base_url}/commits"
        data = self._get(commits_url)

        if data:
            self.logger.info("Commits count: %s", len(data))
            return len(data)

        return None

    def get_issues_count(self) -> Optional[Dict[str, int]]:
        """
        Fetches open and closed issues counts from a GitHub repository.
        Returns:
            A dictionary containing the counts of open and closed issues.
        """
        # Get all issues, both open and closed
        data = self._get(f"{self.base_url}/issues", params={"state": "all"})
        if data:
            open_count   = sum(1 for issue in data if issue["state"] == "open")
            closed_count = sum(1 for issue in data if issue["state"] == "closed")
            self.logger.info("Issues count: open - %s, closed - %s", open_count, closed_count)
            return {"open": open_count, "closed": closed_count}

        return  None
    def get_pull_requests_count(self) -> Optional[Dict[str, int]]:
        """
        Fetches open, closed and merged pull request counts from a GitHub repository.
        Returns:
            A dictionary containing the counts of open, closed and merged pull requests.
        """
        pulls_url = f"{self.base_url}/pulls"
        data = self._get(pulls_url, params={"state": "all"})

        if data:
            open_count   = sum(1 for pull_request in data if pull_request["state"] == "open")
            closed_count = sum(1 for pull_request in data if pull_request["state"] == "closed")
            # (optional) the closed repo is a merged repo 
            merged_count = sum(1 for pull_request in data if pull_request["merged_at"] is not None) 
            self.logger.info("Pull Requests count: open - %s, closed - %s , merged - %s",
                             open_count, closed_count, merged_count)
            return {"open": open_count, "closed": closed_count, "merged": merged_count}

        return  None 

    def get_tags(self) -> Optional[List[str]]:
        """Fetches tags list for a specific repository."""

        tags_url = f"{self.base_url}/tags"
        data = self._get(tags_url)

        if data:
            tags = [tag["name"] for tag in data]
            self.logger.info("Tags: %s", tags)
            return tags

        return None

    def get_dependencies(self) -> Optional[List[str]]:
        """
        Fetches dependency information using the GitHub dependency graph API.
        Returns:
            A list of strings representing the names of the dependencies.
        """
        url = f"{self.base_url}/dependency-graph/sbom"
        response = self._get(url)

        if response and "sbom" in response and "packages" in response["sbom"]:
            # Extract the package names from the response
            packages = [package["name"] for package in response["sbom"]["packages"] if package]
            package_names = [package.split(":")[-1] for package in packages]
            
            # Return the list of package names, excluding the first element (which is the package name itself)                
            return package_names[1:]
        return "No Dependencies"  
        
    def get_ci_cd_tool(self) -> Optional[str]:
        """
        Checks the presence of CI/CD files in the repository.

        This method takes the intersection of the CI/CD filenames from the
        CI_CD dictionary and the filenames from the row. The first element
        of the intersection is returned, which is the name of the CI/CD
        tool used in the repository.

        Returns:
            str: The name of the CI/CD tool used in the repository, or
                "No CI/CD" if none is found.
        """        
        ci_cd_filenames = set(self.ci_cd.keys())
        filenames_set = set(self.row["filenames"])
        intersection = ci_cd_filenames.intersection(filenames_set)
        if intersection:
            # Return the first element of the intersection, which is the name of the CI/CD tool
            return self.ci_cd[next(iter(intersection))]

        return "No CI/CD"

    def extract_repo_details(self, row: Dict, output_path: str) -> None:
        """
        Process a single repo (single row) from the dataframe.
        
        Args:
            row (Dict): A row representing a repository from the DataFrame.
            output_path (str): Path to the output CSV file.
        """
        # Get the repository owner and name from the row
        self.row = row[['owner', 'repo_name']]
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']

        # Construct the base URL for the GitHub API
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

        # Get the filenames and tags for the repository 
        self.row['filenames'] = json.dumps(self.get_filenames())
        self.row['tags'] = json.dumps(self.get_tags())

        # Get the dependencies for the repository and limit the number of 
        # dependencies to be stored in csv 20 for storage purpose
        deps = self.get_dependencies()
        self.row['dependencies'] = json.dumps(deps[:20])

        # Get the issues, pull requests, and commits counts as well as ci/cd tool for the repository
        self.row['issues'] = json.dumps(self.get_issues_count())
        self.row['pull_requests'] = json.dumps(self.get_pull_requests_count())
        self.row['commits_count'] = self.get_commits_count()
        self.row['ci_cd_tool'] = self.get_ci_cd_tool()

        with open(output_path, 'a', newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.row.keys())
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()
            
            # Convert the row using the dictionary format to be stored using the writer
            row_json = {
                k: v for k,
                v in self.row.items() if k in writer.fieldnames}
            writer.writerow(row_json)

        self.logger.info("\n%s", self.row)
        return {"owner": repo_owner, "dependencies": deps}

"""
This block serves as the entry point for the script.
Uncomment it to test the module. It tests the following:

    - Scrape number of contributors.
    - Scrape repositories details.
"""
# if __name__ == '__main__':

#     import pandas as pd
#     from tqdm import tqdm

#     extractor = GitHubRepoExtractor()
#     contribs = []

#     df = pd.read_csv("./data/draft/all_egy_repos")

#     for index, row in tqdm(df.iterrows(), total=len(df), desc="Extracting Repos Details"):
#         contribs.append(extractor.contribs_count(row))

#     df["contribs_count"] = contribs

    
#     for index, row in tqdm(df.iterrows(), total=len(df), desc="Extracting Repos Details"):
        
#         extractor.extract_repo_details(row, output_path= "./data/raw/all_egy_repos_details.csv")
