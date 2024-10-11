
import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dotenv import load_dotenv

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# List of columns to retrieve from the GitHub API when scraping users
USERS_COLS  = ["login", "url"]
REPO_COLS= [
    'owner', 'repo_name', 'repo_html_url', 'language', 'topics',
    'repo_description', 'open_issues_count', 'forks_count',
    'stargazers_count', 'last_repo_commit_date', 'license']
PROFILE_KEYS = [
    "login", "name", "location", "email", "bio", "public_repos", 
    "public_gists", "followers", "following", "created_at", "updated_at"]

# List of database, documentation, and ci/cd files to retrieve from the GitHub API when scraping repositories
DB_FILES = [
    "requirements.txt", "requirement.txt","schema.sql", "pom.xml", "Pipfile", 
    "database.yml", ".env", ".env.example", "database.config", "config.yml", 
    "pyproject.toml", "package.json", "docker-compose.yml", "Gemfile", "go.mod", 
    "build.gradle", "settings.py", "init.sql", "db.js", "database.js", "db_config.php", 
    "database.ini", "db.properties", "hibernate.cfg.xml", "connection.js", "knexfile.js", 
    "application.properties", "alembic.ini", "flyway.conf", "v1__init.sql", "pg_hba.conf", 
    "postgresql.conf", "my.ini", "my.cnf", "postgresql.conf" ]
DOC_FILES = [
    "doc", "docs", "documentation", "documentations", "readme",
    "readme.md","contributing.md","code_of_conduct.md","changelog.md",
    "install.md","license","api.md","security.md","support.md","governance.md",
    "faq.md","styleguide.md","todo.md","authors","credits.md", "dco.md", 
    "changelog","pull_request_template.md"]
CI_CD = {
    ".github/workflows/": "GitHub Actions",
    "circle.yml": "CircleCI",
    "travis.yml": "Travis CI",
    "jenkinsfile": "Jenkins",
    "gitlab-ci.yml": "GitLab CI",
    "azure-pipelines.yml": "Azure Pipelines"
}

# Error messages for common error codes
ERROR_MESSAGES = {
    404: "[404]: Resource not found - This means a repository was deleted or does not exist.",
    451: "[451]: Unavailable For Legal Reasons - This means the repository contains illegal content.",
    401: "[401]: Unauthorized user - Check GitHub token. This means the token is invalid or has been revoked.",
    204: "[204]: No Content - This means a resource exists but there is no content to return.",
    409: "[409]: Conflict - This means a resource exists but should not or already has an operation running on it.",
    422: "[422]: Unprocessable Entity - This means a resource exists but it does not meet the requirements for the request.",
    429: "[429]: Too Many Requests - This means the request was rate limited. The limit is 5000 requests per hour.",
    500: "[500]: Internal Server Error - This means the server encountered an unexpected condition that prevented it from fulfilling the request.",
    502: "[502]: Bad Gateway - This means the server received an invalid response from the upstream server.",
    503: "[503]: Service Unavailable - This means the server is currently unable to handle the request due to a temporary overloading or maintenance of the server."
}

class GitHubAPI:
    """
    Base class for interacting with the GitHub API.

    This class provides methods for making requests to the GitHub API and handling
    common API errors. the following is its functionality:
        - Creates necessary directories for storing data.
        - Sets up the logger to track API activity.
        - Implement status code handlers for API errors.
        - Implement the retry logic for API requests.
        - Implement the token switch logic in case of rate limit exceeded. 
        - Implement the scraping logic of end points of the GitHub API.
        - Implement the scraping logic for user profile details.
        - Implement the scraping logic for repositories details.
    """
    def __init__(self) -> None:
        """
        Initializes the GitHubAPI class.
            - Creates necessary directories for storing data.
            - Sets up the logger for logging all activities.
            - Loads project environment from a file (.env).
            - Sets up the headers for API requests.
            - Sets up the list of skipped rows.
            - Sets up the list of columns to retrieve from the GitHub API.
            - Sets up the list of database, documentation, and ci/cd files to retrieve 
              from the GitHub API when scraping repositories.
        """
        # Create directories for storing data
        self.data_dir = "data"
        self.logs_dir = "logs"
        self.json_dir = os.path.join(self.data_dir, "json_files")
        self.raw_dir = os.path.join(self.data_dir, "raw")
        self.draft_dir = os.path.join(self.data_dir, "draft")
        
        # Make sure the directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.draft_dir, exist_ok=True)

        # Set up the logger
        self.logger = self.setup_logger()

        # Load the GitHub token from the environment variable or a file
        os.environ["DOTENV_PATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
        load_dotenv(os.environ["DOTENV_PATH"])
        self.tokens = [
            os.getenv('GITHUB_ACCESS_TOKEN1'),
            os.getenv('GITHUB_ACCESS_TOKEN2'),
            os.getenv('GITHUB_ACCESS_TOKEN3'),
            os.getenv('GITHUB_ACCESS_TOKEN4')
        ]
        self.current_token_index = 0
        if not self.tokens[self.current_token_index]:
            raise RuntimeError("GitHub token not found")
        self.logger.info("Token: %s", self.tokens[self.current_token_index])

        # Set up headers for API requests
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {self.tokens[self.current_token_index]}",
        }

        # Initialize the list of skipped rows
        self.missed_rows: List[str] = []

        # Initialize the list of columns to retrieve from the GitHub API
        self.repos_cols   = REPO_COLS
        self.users_cols   = USERS_COLS
        self.profile_keys = PROFILE_KEYS
        self.db_files  = DB_FILES
        self.doc_files = DOC_FILES
        self.ci_cd     = CI_CD
    def setup_logger(self) -> logging.Logger:
        """
        Sets up the logger for the GitHub API.

        This method creates a log file in the `logs` directory with the current
        date and time as the filename. It configures the logging level to `INFO`
        and sets up the logging format to include the timestamp, log level,
        line number, and log message.
        """
        log_file_path = os.path.join(
            os.getcwd(), self.logs_dir,
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        )

        # Configure basic logging setup
        logging.basicConfig(
            filename=log_file_path,
            format='[%(asctime)s] - %(levelname)s - %(lineno)d - %(message)s',
            level=logging.INFO
        )

        return logging.getLogger(__name__)

    def create_retry_session(self) -> requests.Session:
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
            total=5,
            # delay between retries. backoff_factor * (2 ** (retry_attempt - 1)). 
            # The delay between retries will grow exponentially 
            # with retry_attempt number (0.2, 0.4, 0.8, etc.).
            backoff_factor=0.2,
            status_forcelist={429, 500, 502, 503, 504},
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_config)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def switch_token(self):
        """
        Switches to the next token in the list of GitHub tokens.

        This method is used to handle the rate limit exceeded error. It
        switches to the next available token and updates the headers for
        API requests.
        """
        # Switch to the next available token.
        # you should save one or more token in (.env) file.
        self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
        # Update the headers for API requests
        self.headers["Authorization"] = f"token {self.tokens[self.current_token_index]}"
        self.logger.info("Switched to token %s", self.tokens[self.current_token_index])
        
    def handle_api_errors(self, response: requests.Response ) -> Optional[Dict]:
        """
        Handles common API errors, returns data if successful.
        This method checks the status code of a request and performs different
        actions based on the code. 
        
        The handler senarios is as follows:
        
            - In case of a successful request (200), the JSON response is returned.
            - If the status code is 403 (rate limit exceeded), the program switches
               the token and then retries the request.
            - Other error codes are handled by raising and logging an error message and returning None.
        """

        if response.status_code == 200:
            return response.json()

        if response.status_code in [403, 429]:
            reset_time = int(response.headers["X-RateLimit-Reset"]) - int(time.time())
            if reset_time > 0: 
                
                self.logger.warning(
                    "Error 403: Rate limit exceeded! We need to slow down. "\
                    "Please wait for %s seconds until the rate limit resets.",
                    reset_time
                )
                self.switch_token()
                # time.sleep(reset_time)
            return None

        msg = ERROR_MESSAGES.get(response.status_code, f"Error fetching data: {response.status_code}")
        self.logger.error(msg)
        # raise Exception(msg)
        return None       

    # @staticmethod
    # def raise_timeout_exception():
    #     """Function to raise the TimeoutException."""
    #     raise Exception("Operation timed out")

    # @staticmethod
    # def timeout_handler(signum, frame):
    #     """Handle timeout events by raising a custom exception."""
    #     raise TimeoutException

    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Makes a GET request to the GitHub API.

        This method creates a retry session with a custom retry policy 
        and then makes a GET request to the specified URL using the retry session.

        The method then handles errors and retries the request if necessary. If the request
        is successful, the JSON response is returned.

        Args:
            url (str): The URL to query.
            params (Optional[Dict], optional): A dictionary of parameters to be passed to the GitHub API. Defaults to None.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the response data if the request is successful,
                otherwise None.
        """

        # Create a retry session with a custom retry policy
        session = self.create_retry_session()

        # Make a GET request to the specified URL using the retry session
        response = session.get(url, headers=self.headers, params=params)

        # Handle errors and retry the request if necessary
        result = self.handle_api_errors(response)

        # If the request was not successful and needs to be retried, retry the request
        if result is None:
            self.logger.info("Retrying request...")
            response = session.get(url, headers=self.headers, params=params)
            result = self.handle_api_errors(response)

        # Return the JSON response if the request was successful
        return result    

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
            self.logger.info("Retrieved profile information for %s: \n%s", username, profile)
            return profile

        else:
            if 'location' not in response:
                return None
            if response['location'] is not None:
                if response['location'].lower() == location.lower():
                    profile = {key: response[key] for key in self.profile_keys if key in response}
                    self.logger.info("Retrieved profile information for %s: \n%s", username, profile)
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
                # Get the last updated date
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
            raise Error("Error while processing repository details: %s", e)
            return None