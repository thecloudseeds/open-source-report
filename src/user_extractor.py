"""
This module used to extracts information about user profiles from a GitHub user's URL.
It utilizes the GitHub API to fetch detailed information about individual GitHub users based on their user URL.
It leverages the base `GitHubAPI` class for API interactions and error handling.

Uses the GitHub API to retrieve user profile data and extracts key
    - username, name, company, location, bio, email.
    - Repositories, followers, following, and account update dates (last commit date).
"""
import os
import signal
from typing import Optional, Dict

from src.github_api import GitHubAPI


class GitHubUserExtractor(GitHubAPI):
    """Extracts information about a GitHub user based on a repository URL."""

    def __init__(self, row: Dict):
        super().__init__()
        repo_owner = row['repo_html_url'].split("/")[-2]
        self.user_url = f"https://api.github.com/users/{repo_owner}"

    def get_user_profile(self) -> Optional[Dict]:
        """Fetches the user profile information from the specified URL."""
        try:
            data = self._get(self.user_url)

            if data:
                profile = {
                    "name": data.get("name"),
                    "company": data.get("company"),
                    "location": data.get("location"),
                    "bio": data.get("bio"),
                    "repos_num": data.get("public_repos"),
                    "gists_num": data.get("public_gists"),
                    "followers": data.get("followers"),
                    "following": data.get("following"),
                    "public_repos": data.get("public_repos"),
                    "last_user_commit": data.get("updated_at"),
                }
                self.logger.info(f"User profile: {profile}")

                return profile

            else:
                self.logger.warning(
                    f"Failed to retrieve user profile for: {self.user_url}")
        except Exception as e:
            self.logger.error(f"Processing row for {self.user_ur} exceeded the time {e}")
            self.skipped_rows.append(repo_owner)

        finally:
            signal.alarm(0)  # Reset the alarm
    
        return self.skipped_rows
# if __name__ == '__main__':

#     import pandas as pd
#     from tqdm import tqdm
#     df = pd.read_csv("./data/repos.csv").sample(10)
#     user_profiles = []

#     for index, row in tqdm(df.iterrows(), total=len(df), desc=f"Extracting Contributors Details"):
#         extractor = GitHubUserExtractor(row)
#         profile = extractor.get_user_profile()
#         if profile:
#             user_profiles.append(profile)

#     profile_df = pd.DataFrame(user_profiles)
#     profile_df.to_csv("./data/users_out.csv", index=False)
