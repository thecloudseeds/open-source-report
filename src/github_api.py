"""
This module is a base class for interacting with the GitHub API.

    - It provides methods for making requests to the GitHub API
    - Use rate limiting, retry logic, and error handling.
    - It utilizes a provided GitHub token for authorization and logging to track API activity.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dotenv import load_dotenv

import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

USERS_COLS = ["login", "url"]
REPO_COLS = ['owner', 'repo_name', 'repo_html_url', 'language', 'topics',
             'repo_description', 'open_issues_count', 'forks_count',
             'stargazers_count', 'last_repo_commit_date', 'license']
PROFILE_KEYS = ["login", "name", "location", "email", "bio", "public_repos", 
                "public_gists", "followers", "following", "created_at", "updated_at"]

DB_FILES = [
            "requirements.txt", "schema.sql", "pom.xml",
            "Pipfile", "database.yml",".env", ".env.example",
            "database.config", "config.yml", "pyproject.toml",
            "package.json", "docker-compose.yml",  "Gemfile", 
            "go.mod", "build.gradle",  "settings.py","init.sql", 
            ]
class GitHubAPI:
    """
    Base class for interacting with the GitHub API.
    This class provides methods for making requests to the GitHub API and handling common
    API errors. It also sets up a logger for logging API activity.
    Attributes:
        output_dir (str): The directory for storing data
        json_dir (str): The directory for storing JSON files
        raw_dir (str): The directory for storing raw data
        draft_dir (str): The directory for storing draft data
        headers (dict): A dictionary with headers for API requests
        logger (logging.Logger): A logger for logging all activities
        skipped_rows (List[str]): A list to store skipped rows
    """

    def __init__(self) -> None:
        """
        Creates necessary directories for storing data, sets up the logger, and
        loads the GitHub token from the environment variable or a file.
        """
        # Create directories for storing data
        self.output_dir = "data"
        self.json_dir = os.path.join(self.output_dir, "json_files")
        self.raw_dir = os.path.join(self.output_dir, "raw")
        self.draft_dir = os.path.join(self.output_dir, "draft")
        self.logs_dir = os.path.join(os.getcwd(), 'logs')

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.draft_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        # Set up headers for API requests
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {os.getenv('YOUR_GITHUB_TOKEN')}",
        }

        # Set up logger
        self.logger = self._setup_logger()

        self.skipped_rows: List[str] = []
        self.repos_cols = REPO_COLS
        self.users_cols = USERS_COLS
        self.profile_keys = PROFILE_KEYS
        self.db_files = DB_FILES
        
    def _setup_logger(self) -> logging.Logger:
        """
        Sets up the logger for the GitHub API.

        This method creates a log file in the `logs` directory with the current
        date and time as the filename. It configures the logging level to `INFO`
        and sets up the logging format to include the timestamp, log level,
        line number, and log message.
        """
        log_file_path = os.path.join(
            os.getcwd(), 'logs',
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        )

        # Configure basic logging setup
        logging.basicConfig(
            filename=log_file_path,
            format='[%(asctime)s] - %(levelname)s - %(lineno)d - %(message)s',
            level=logging.INFO
        )

        return logging.getLogger(__name__)

    def _create_retry_session(self) -> requests.Session:
        """
        Creates a requests session with retry capabilities.

        This method sets up a `requests.Session` with a retry configuration.
        It is used to handle temporary errors such as rate limiting and
        unavailable resources.

        The retry configuration is as follows:
            - Maximum total retries: 5
            - Status codes that trigger a retry: 429, 500, 502, 503, 504
            - Backoff factor: 0.1 (wait exponentially longer)
            - Respect retry-after header: True
            - Raise on status: False (don't raise an exception on failed requests)

        Returns:
            A `requests.Session` with retry capabilities
        """
        retry_config = Retry(
            total=5, backoff_factor=0.1,
            status_forcelist={429, 500, 502, 503, 504},
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_config)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _handle_api_errors(self, response: requests.Response ) -> Optional[Dict]:
        """
        Handles common API errors, returns data if successful.
        This method checks the status code of a request and performs different
        actions based on the code. 
        
            - In case of a successful request (200), the JSON response is returned.
            - If the status code is 403 (rate limit exceeded), the program waits for
              the rate limit to reset and then retries the request.
            - Other error codes are handled by logging an error message and returning None.
        """
        if response.status_code == 200:
            return response.json()

        elif response.status_code == 403:
            # Wait until the rate limit resets
            wait_time = int(response.headers["X-RateLimit-Reset"]) - time.time()
            if wait_time > 0:
                self.logger.warning(
                    "Error 403: Rate limit exceeded! Please wait :%s minutes.",
                    int(wait_time/60)
                )
                time.sleep(wait_time)
            return None

        elif response.status_code == 404:
            self.logger.error("Error 404: Resource not found.")
            return None

        elif response.status_code == 451:
            self.logger.error("Error 451: Unavailable For Legal Reasons.")
            return None

        elif response.status_code == 401:
            self.logger.error("Error 401: Unauthorized user. Check GitHub token.")
            return None

        elif response.status_code == 204:
            self.logger.info("Error 204: No Content.")
            return None

        elif response.status_code == 409:
            self.logger.error(
                "HTTP 409 - Conflict. This often means a resource exists but "
                "should not or already has an operation running on it."
            )
            return None

        else:
            self.logger.error("Error fetching data: %s", response.status_code)
            return None

    @staticmethod
    def raise_timeout_exception():
        """Function to raise the TimeoutException."""
        raise Exception("Operation timed out")

    @staticmethod
    def timeout_handler(signum, frame):
        """Handle timeout events by raising a custom exception."""
        raise TimeoutException
    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Makes a GET request to the GitHub API."""

        session = self._create_retry_session()
        response = session.get(url, headers=self.headers, params=params)

        return self._handle_api_errors(response)
    
    def get_profile(self, username: str, location: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieves a GitHub user's profile information.

        Args:
            username (str): The username of the GitHub user.
            location (Optional[str], optional): The country or region to filter by. Defaults to None.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the profile information if the user exists,
                otherwise None.
        """
        contrib_url = f"https://api.github.com/users/{username}"
        response = self._get(contrib_url)

        # Check for None responses and handle accordingly
        if response is None:
            return None

        # Check if the user has a location and return user profile
        if location is None:
            profile = {key: response[key] for key in self.profile_keys if key in response}
            self.logger.info(f"Retrieved profile information for {username}: {profile}")
            return profile

        else:
            if 'location' not in response:
                return None
            if response['location'] is not None:
                if response['location'].lower() == location.lower():
                    profile = {key: response[key] for key in self.profile_keys if key in response}
                    self.logger.info(f"Retrieved profile information for {username}: {profile}")
                    return profile
            return None
           
    def get_repo_details(self, repo: Dict) -> Dict:
        """
        Retrieves detailed information about a given repository.
        Args:
            repo (Dict): A dictionary containing the repository information.
        Returns:
            Dict: A dictionary containing the detailed repository information.
        """
        try:
            repo_details = {
                "owner": repo["owner"]["login"],
                "repo_name": repo["name"],
                "repo_html_url": repo["html_url"],
                "repo_description": repo.get("description"),
                "language": (
                    # Handle Jupyter Notebooks as Python language
                    "Python"
                    if repo.get("language") == "Jupyter Notebook"
                    else repo.get("language")
                ),
                
                "topics": ", ".join(repo.get("topics", [])),
                # Join the topics with commas
                "stargazers_count": repo.get("stargazers_count", 0),
                "forks_count": repo.get("forks_count", 0),
                "open_issues_count": repo.get("open_issues_count", 0),
                "last_repo_commit_date": repo.get("updated_at"),
                # Get the last updated dat
                "license": (
                    # Get the license name
                    repo["license"]["name"]
                    if "license" in repo and repo["license"]
                    else None
                ),
            }
            # Log the retrieved repository details
            self.logger.info(
                "Retrieved repository details for %s/%s: \n%s",
                repo_details["owner"],
                repo_details["repo_name"],
                repo_details,
            )
            return repo_details
        except Exception as e:
            self.logger.error("Error while processing repository details: %s", e)
            return None