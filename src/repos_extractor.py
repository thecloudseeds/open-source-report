"""
This module relies on a base `GitHubAPI` class.
The module extracts detailed information about GitHub repositories and analyzes various aspects such as:

- Files
- Contributors
- Commits
- Issues
- Pull Requests
- Tags
- CI/CD Tools

"""
import csv
import json
import urllib
import signal
from typing import Optional, Dict, List
from src.github_api import GitHubAPI

REPO_COLS = ['owner', 'repo_name', 'repo_html_url', 'language', 'topics',
             'repo_description', 'open_issues_count', 'forks_count',
             'stargazers_count', 'last_repo_commit_date', 'license',
             'contribs_count', 'commits_count', 'filenames',
             'tags', 'dependencies', 'issues', 'pull_request', 'ci_cd_tool']

exclude_files_ext = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".wav", ".webp", ".mp4",
    ".pptx", ".pdf", ".xlsx", ".csv", ".log", ".gz", ".rar", ".zip",
    ".jsx", ".cs", ".vsidx", ".cshtml", ".c", ".cpp",".spice", ".mag", 
    ".cs", ".pyc", ".cshtml","idx", ""
    ".map", ".exe", ".so", ".dylib", ".pdb", ".o", ".a", ".obj", ".lib",
    ".DS_Store", ".git", ".cache",".ico" ]


class GitHubRepoExtractor(GitHubAPI):
    """
    This class extracts data about GitHub repositories, processing information
    like file structure, contributors, and activity metrics. It uses the
    `GitHubAPI` class for communication with the GitHub API.
    """

    def __init__(self):

        super().__init__()
        self.row = None
        self.base_url = None

    def _filenames(self) -> List[str]:
        """Recursively retrieves all files and directories within a repository."""

        def _fetch_recursive(directory: str) -> List[str]:
            """Helper function to recursively get files/directories."""
            # Replace reserved characters with their encoded equivalents
            # Example:
            # - "MyFile.cs#" becomes "MyFile.cs%23" (as %23 is # encoded for URL)
            # - "MyFile&More.cs" becomes "MyFile%26More.cs"
            # This ensures proper URL encoding for filenames containing special
            # characters

            directory = urllib.parse.quote(directory)
            contents_url = f"{self.base_url}/contents/{directory}"
            data = self._get(contents_url)

            cicd_filenames = [
                    "Jenkinsfile", ".github/workflows", ".circleci/config.yml",
                    ".drone.yml", ".gitlab-ci.yml", ".travis.yml"
                    ]
            exclude_dirs = [
                        "images", "imgs", "imag", "figures","figure","figs",
                        "assets","asset", "__pycache__", "log","logs", ".git", 
                        "3rdparty",  "bin/test", "bin/git", "buildfiles/msvc", "darwin/util",]

            needed_filenames = self.db_files + self.cicd_filenames

            if data:
                for item in data:
                    # Don't retraive imamges and backup python files

                    if item["type"] == "file" and not item["name"].lower().isin(needed_filenames):

                        yield item["path"]

                    elif item["type"] == "dir" and item["name"].lower() not in exclude_dirs:
                        yield from _fetch_recursive(item["path"])

            else:
                self.logger.warning(
                    f"Failed to retrieve content for directory: {directory}")
                return None

        return list(_fetch_recursive(""))

    def contribs_count(self, row) -> Optional[int]:
        """Fetches the number of contributors for a given repository."""

        self.row = row
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        contributors_url = f"{self.base_url}/contributors"

        data = self._get(contributors_url)

        if data:
            self.logger.info(f"Contributor count: {len(data)}")
            return len(data)

        return None

    def _commits_count(self) -> Optional[int]:
        """Fetches the number of commits for a given repository."""

        commits_url = f"{self.base_url}/commits"
        data = self._get(commits_url)

        if data:
            self.logger.info(f"Commit count: {len(data)}")
            return len(data)

        return 0

    def _issues_count(self) -> Optional[Dict[str, int]]:
        """Fetches open and closed issues counts from a GitHub repository."""

        issues_url = f"{self.base_url}/issues"
        data = self._get(issues_url, params={"state": "all"})

        if data:

            open_count = sum(1 for issue in data if issue["state"] == "open")
            closed_count = sum(
                1 for issue in data if issue["state"] == "closed")

            self.logger.info(
                f"Issue counts: open - {open_count}, closed - {closed_count}")

            return {"open": open_count, "closed": closed_count}

        return {"open": 0, "closed": 0}

    def _pull_requests_count(self) -> Optional[Dict[str, int]]:
        """Fetches open and closed pull request counts from a GitHub repository."""

        pulls_url = f"{self.base_url}/pulls"
        data = self._get(pulls_url, params={"state": "all"})

        if data:

            open_count = sum(
                1 for pull_request in data if pull_request["state"] == "open")
            closed_count = sum(
                1 for pull_request in data if pull_request["state"] == "closed")
            merged_count = sum(
                1 for pull_request in data if pull_request["merged_at"] is not None)

            self.logger.info(
                f"Pull request counts: open - {open_count},"
                f"closed - {closed_count}, merged - {merged_count}"
            )

            return {
                "open": open_count,
                "closed": closed_count,
                "merged": merged_count}

        return None

    def _tags(self) -> Optional[List[str]]:
        """Fetches tags list for a specific repository."""

        tags_url = f"{self.base_url}/tags"
        data = self._get(tags_url)

        if data:
            tags = [tag["name"] for tag in data]
            self.logger.info(f"Tags: {tags}")

            return tags

        return None

    def _dependencies(self) -> Optional[List[str]]:
        """ Fetches dependency information using the GitHub dependency graph API """

        dependencies_url = f"{self.base_url}/dependency-graph/sbom"
        data = self._get(dependencies_url)

        if data:

            packages = [package["name"]
                        for package in data["sbom"]["packages"]]
            packages_names = [pkg.split(':')[-1] for pkg in packages]

            self.logger.info(f"Packages: {packages_names}")

            if len(packages_names) > 1:
                return packages_names[1:]

        return None

    def _ci_cd_tool(self) -> Optional[str]:
        """ Extracts information about CI/CD pipelines by checking for configuration files. """

        for filename in self.row["filenames"]:

            if filename.lower() == ".travis.yml":
                return "Travis CI"
            elif filename.lower() == ".gitlab-ci.yml":
                return "GitLab CI"
            elif filename.lower() == ".drone.yml":
                return "Drone CI"
            elif filename.lower() == ".circleci/config.yml":
                return "CircleCI"
            elif filename.lower() == ".github/workflows":
                return "GitHub Actions"
            elif filename.lower() == "Jenkinsfile":
                return "Jenkins"
            else:
                return None

    def extract_repo_details(self, row, output_path, mins_limit = 0.5) -> None:
        """Process a single repo (single row) from the dataframe"""
        self.row = row[['owner', 'repo_name']]
        repo_owner = self.row['owner']
        repo_name = self.row['repo_name']
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"

        with open(output_path, 'a', newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=REPO_COLS)

            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()

            # Set a 3-minute timeout for processing the row
            signal.signal(signal.SIGALRM, self.timeout_handler) 
            signal.alarm(int(mins_limit*60))  # Set alarm for 3 minutes (180 seconds)
            
            try:    
                self.row['commits_count'] = self._commits_count()
                self.row['filenames'] = json.dumps(self._filenames())
                self.row['tags'] = self._tags()
                self.row['dependencies'] = json.dumps(self._dependencies())
                self.row['issues'] = json.dumps(self._issues_count())
                self.row['pull_requests'] = json.dumps(self._pull_requests_count())
                self.row['ci_cd_tool'] = self._ci_cd_tool()

                # Write the row using the dictionary format
                row_json = {
                    k: v for k,
                    v in self.row.items() if k in writer.fieldnames}
                writer.writerow(row_json)

                self.logger.info(f"\n{self.row}")

            except Exception as e:
                self.logger.error(f"Processing row for {repo_owner} exceeded the time {e}")
                # Return the skipped rows list after processing is complete
                return repo_owner

            finally:
                signal.alarm(0)  # Reset the alarm
            

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
