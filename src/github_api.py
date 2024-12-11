import os
import time
import yaml
import json
import logging

from datetime import datetime
from typing import Dict, Optional, List
from dotenv import load_dotenv

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 5000 requests per hour = 1.38 seconds per request
throttle_delay = 5000 / 60 / 60

class GitHubAPI:
    """
    Base class for interacting with the GitHub API.

    This class provides methods for making requests to the GitHub API and handling
    common API errors.
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        Initializes the GitHubAPI class and sets up necessary configurations.
        """
        if config is None:
            # Load Configuration fileif exist
            config_path = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), '..', 'config.yaml')
            if not os.path.exists(config_path):
                raise FileNotFoundError(
                    f"Configuration file not found: {config_path}")
            with open(config_path, "r") as file:
                self.config = yaml.safe_load(file)

            if not self.config:
                raise RuntimeError("Failed to load the configuration file")
        else:
            self.config = config

        self.tokens = self.load_tokens()
        self.json_dir, self.raw_dir, self.draft_dir = self.create_directories()
        self.logger = self.setup_logger()
        self.current_token_index = 0
        self.headers = self.setup_headers()
        self.error_messages = self.load_error_messages()  # Load error messages from JSON
        self.missed_rows: List[str] = []  # Initialize the missed_rows list

    def load_tokens(self) -> List[str]:
        """
        Loads the GitHub tokens from environment variables.
        """
        os.environ["DOTENV_PATH"] = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '.env')
        load_dotenv(os.environ["DOTENV_PATH"])

        tokens = [
            os.getenv('GITHUB_ACCESS_TOKEN1'),
            os.getenv('GITHUB_ACCESS_TOKEN2'),
            os.getenv('GITHUB_ACCESS_TOKEN3'),
            os.getenv('GITHUB_ACCESS_TOKEN4')
        ]

        # Ensure at least one valid token is loaded
        if not any(tokens):
            raise RuntimeError("GitHub tokens not found")

        return tokens

    def create_directories(self) -> tuple:
        """
        Creates necessary directories for storing data.
        """
        os.makedirs(self.config.get("DATA_DIR", "data"), exist_ok=True)
        os.makedirs(self.config.get("LOG_DIR", "logs"), exist_ok=True)

        json_dir = os.path.join(self.config.get(
            "DATA_DIR", "data"), "json_files")
        raw_dir = os.path.join(self.config.get("DATA_DIR", "data"), "raw")
        draft_dir = os.path.join(self.config.get("DATA_DIR", "data"), "draft")

        os.makedirs(json_dir, exist_ok=True)
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(draft_dir, exist_ok=True)

        return json_dir, raw_dir, draft_dir

    def setup_logger(self) -> logging.Logger:
        """
        Sets up the logger for the GitHub API.
        """
        if not self.config["LOG_DIR"]:
            raise ValueError("LOGS_DIR is not set")

        log_file_path = os.path.join(
            os.getcwd(), self.config["LOG_DIR"],
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        )

        # Configure basic logging setup
        logging.basicConfig(
            filename=log_file_path,
            format="%(asctime)s - %(levelname)s - %(lineno)d - %(message)s",
            level=logging.INFO  # Set level to DEBUG for detailed logging
        )

        return logging.getLogger(__name__)

    def setup_headers(self) -> Dict[str, str]:
        """
        Sets up the headers for API requests.
        """
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {self.tokens[self.current_token_index]}",
        }

    def load_error_messages(self) -> Dict:
        """
        Loads the error messages from a JSON file.
        """
        error_messages_path = os.path.join(
            self.json_dir, "error_messages.json")

        # Load the error messages from the JSON file
        if os.path.exists(error_messages_path):
            with open(error_messages_path, "r") as json_file:
                return json.load(json_file)
        else:
            raise FileNotFoundError(
                f"Error messages file not found: {error_messages_path}")

    def create_retry_session(self) -> requests.Session:
        """
        Creates a requests session with retry capabilities.
        """
        retry_config = Retry(
            total=self.config["RETRY_NUM"],
            backoff_factor=self.config["RETRY_FACTOR"],
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
        """
        # Use modulo operation to cycle through tokens
        if len(self.tokens) > 1:
            self.current_token_index = (
                self.current_token_index + 1) % len(self.tokens)
            self.headers["Authorization"] = f"token {self.tokens[self.current_token_index]}"
            self.logger.info("Switched to token %s",
                             self.tokens[self.current_token_index])
        else:
            self.logger.warning("No additional tokens to switch to.")

    def handle_api_errors(self, response: requests.Response) -> Optional[Dict]:
        """
        Handles common API errors, returns data if successful.
        """
        if response.status_code == 200:
            return response.json()

        if response.status_code in [403, 429]:
            reset_time = int(response.headers.get(
                "X-RateLimit-Reset", 0)) - int(time.time())
            if reset_time > 0:
                self.logger.warning(
                    "Error 403: Rate limit exceeded! We need to slow down. "
                    "Please wait for %s seconds until the rate limit resets.",
                    reset_time
                )
                self.switch_token()
                return None

        msg = self.error_messages.get(
            response.status_code, f"Error fetching data: {response.status_code}")
        self.logger.error(msg)
        return None

    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Makes a GET request to the GitHub API.
        """
        time.sleep(throttle_delay)
        session = self.create_retry_session()
        response = session.get(url, headers=self.headers, params=params)

        if response is None:
            self.logger.error("Failed to make request to %s", url)
            return None

        result = self.handle_api_errors(response)
        if result is None:
            self.logger.error("Request to %s failed", url)

        return result

    def get_profile(self, username: str, location: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieves a GitHub user's profile information.
        """
        contrib_url = f"{self.config['API_BASE_URL']}/users/{username}"
        params = {"location": location} if location else None
        user_data = self._get(contrib_url, params)

        if user_data:
            self.logger.info(
                "Retrieved user profile for %s: %s", username, user_data)
            return user_data

        return None

    def get_repo_details(self, repo: Dict) -> Optional[Dict]:
        """
        Retrieves details of a specific GitHub repository.
        """
        try:
            repo_url = repo['url']
            repo_details = {
                "repo_name": repo['name'],
                "owner": repo['owner']['login'],
                "url": repo_url,
                "description": repo.get('description', ''),
                "language": repo.get('language', ''),
                "stars": repo.get('stargazers_count', -1),
                "forks": repo.get('forks_count', -1),
                "issues": repo.get('open_issues_count', -1),
                "created_at": repo.get('created_at', ''),
                "updated_at": repo.get('updated_at', '')
            }

            self.logger.info("Retrieved repository details for %s/%s: \n%s",
                             repo_details["owner"], repo_details["repo_name"], repo_details)
            return repo_details

        except KeyError as e:
            self.logger.error("Missing key in repository details: %s", e)
        except Exception as e:
            self.logger.error(
                "An error occurred while retrieving repository details: %s", e)
