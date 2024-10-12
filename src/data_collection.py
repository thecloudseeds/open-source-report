"""
This module provides functions to scrape GitHub data, specifically focusing on
contributors from a specified location (Egypt) and their associated repositories.

The script showcases an example workflow. It illustrates:
  - Collect a dataset of contributors from Egypt (`scrap_egy_contributors`)
  - Collect Egyptiopn users (owners) repositories.
  - Collect top worldwide repos and display the Egyption contributors of these repositories.
"""
import os
import csv
import pandas as pd
from tqdm import tqdm
from typing import Optional, List, Dict
from src.github_api import GitHubAPI


class GitHubDataCollector(GitHubAPI):
    """Class for scraping contributors and their repositories from GitHub."""

    def __init__(self):
        super().__init__()

    def scrap_egy_users(
            self, params: Dict, endpoint: str, date: str,
            output_filename: str = None) -> List[Dict]:
        """
        Scrape Egyptian users.

        Args:
            params: A dictionary of parameters to be passed to the GitHub API.
            endpoint: The GitHub API endpoint to query.
            date: The current date to be used as a filename.
            output_filename: The path to save the scraped data to.

        Returns:
            A list of dictionaries containing the scraped user data.
        """
        if not endpoint:
            raise ValueError("Endpoint is a required parameter")

        if not params:
            raise ValueError("Params is a required parameter")

        output_filename = output_filename or self.config["EGY_USERS_FILENAME"]
        output_file_path = os.path.join(
            os.getcwd(), self.raw_dir, output_filename)

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(
                "File created at %s to store all Egyption users urls", output_file_path
            )

        # Initialize an empty list to store scraped user data
        scrapped_users = []
        # Send the first request to get total_count and set up the progress bars
        response = self._get(url=endpoint, params=params)

        if response is None:
            raise RuntimeError("Failed to get response from GitHub API")

        if 'items' not in response:
            raise ValueError("Response does not contain 'item' key")

        # Get the total number of users and pages from the response
        total_count = response["total_count"]
        max_page = total_count // params["per_page"] + 1
        self.logger.info("Total GithHub users found: %s for date [%s]",
                         total_count, date)

        # Outer progress bar for total pages
        pbar = tqdm(
            total=max_page, desc="Scraping pages", unit=" pages", colour='green',
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]",
        )
        page = 1

        while True:
            pbar.set_description(
                f"Scraping {total_count:03} users [{date}] Page {page:02}/{max_page:02}")
            # Iterate over the users on the current page
            for item in response.get("items", []):
                if item is None:
                    raise ValueError("Response contains a null user")

                user_data = {
                    "login": item.get("login"),
                    "url": item.get("url"),
                }
                if user_data is None or user_data["login"] is None or user_data["url"] is None:
                    raise ValueError("User data is missing a login or url")
                scrapped_users.append(user_data)

            self.logger.info("Finished scraping page %s", page)
            pbar.update(1)

            # Break the loop if all pages are processed
            page += 1
            if page > max_page:
                break

            # Get the next page of users (update params if needed)
            params["page"] = page
            response = self._get(url=endpoint, params=params)

        pbar.close()

        # Write the scraped data to the output file
        with open(output_file_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.config["USER_COLS"])
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()

            writer.writerows(scrapped_users)

        return scrapped_users

    def scrap_egy_repos(
            self, input_file_path: str, users_limit: int = 50_000,
            skip_rows: int = 0, output_file_path: str = None) -> List[Dict]:
        """
        Scrape repositories from Egyptian users.

        Args:
            users_limit (int): The number of users to process.
            input_filename (str): The file path of the input csv file containing the users.
            output_filename (str): The file path of the output csv file containing the scraped repositories.
            skip_rows (int): The number of rows to skip at the beginning of the input file.

        Returns:
            List[str]: A list of usernames of the users whose repositories were scraped.
        """
        if output_file_path is None:
            output_file_path = os.path.join(
                os.getcwd(), self.raw_dir, self.config["EGY_USERS_REPOS_FILENAME"])

        if not os.path.exists(output_file_path):

            open(output_file_path, 'w').close()
            self.logger.info(
                "File created at %s to store all Egyption repositories", output_file_path
            )

        till_rows = skip_rows + users_limit
        users_data = pd.read_csv(input_file_path, nrows=till_rows)
        users_data = users_data[skip_rows: till_rows]

        with open(output_file_path, "a", newline="", encoding=self.config["DEFAULT_ENCODING"]) as file:
            writer = csv.DictWriter(file, fieldnames=self.config["REPO_COLS"])
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()

            # Iterate over the users
            user_repos = []
            for _, user in tqdm(users_data.iterrows(), unit="user",
                                total=len(users_data), colour='magenta',
                                desc=f"Scraping Repositores for {len(users_data)} Users: "):
                response = self._get(f"{user['url']}/repos")

                # Iterate over the user's repositories
                for user_repo in response:
                    repo_details = self.get_repo_details(user_repo)
                    user_repos.append(repo_details)

                # Write the user's repositories to the output csv file
                if user_repos:
                    writer.writerows(user_repos)
            return user_repos

    def scrap_non_egy_repos(
        self, endpoint: str = "https://api.github.com/search/repositories",
        params=lambda: {
            "q": "stars:>1000 sort:stars",
            "order": "desc",
            "per_page": 100,
            "page": 1
        },
            total_count: int = 1000, output_file_path: str) -> None:
        """Scrape the top GitHub repositories, excluding those in Egypt.
        This method makes a GET request to the GitHub API to search for
        repositories with more than 1000 stars, sorted in descending order.
        It then writes the repository details to a CSV file.

        Args:
            endpoint (str): The GitHub API endpoint to query.
            params (Dict[str, str]): A dictionary of parameters to be passed to the GitHub API.
            output_path (str): The path to the CSV file to write to.
            total_count (int): The total number of repositories to scrape.
        """

        if output_file_path is None:
            output_file_path = os.path.join(
                os.getcwd(), self.draft_dir, self.config["NON_EGY_REPOS_FILENAME"])

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(
                "File created at %s to store non-egyption repositories", output_file_path
            )

        with open(output_file_path, "a", newline="", encoding="utf-8") as file:
            self.logger.info("File created at %s to store non-egyption repositories",
                             output_file_path)
            writer = csv.DictWriter(file, fieldnames=self.config["REPO_COLS"])
            writer.writeheader()

            pbar = tqdm(total=total_count, colour='cyan',
                        desc="Scrapping Non Egyption Repos",
                        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{percentage:.0f}%] {elapsed}<{remaining}')

            repos_scraped = 0
            while repos_scraped < total_count:
                response = self._get(url=endpoint, params=params)

                if response is not None:
                    self.logger.info("Total repositories Found: %s",
                                     response.get('total_count', 0))

                    repos = []
                    for repo in response['items']:
                        repo_json = self.get_repo_details(repo)
                        if repo_json is not None:
                            repos.append(repo_json)
                            repos_scraped += 1
                            if repos_scraped >= total_count:
                                break

                    writer.writerows(repos)
                    pbar.update(len(repos))
                    pbar.set_description("Scrapping Non Egyption Repos: "
                                         f"Page[{params['page']:01}/{int(total_count/100)}]")
                    self.logger.info(f"Scraping page number {params['page']}")

                    params["page"] += 1

    def extract_egy_contribs(
            self, input_file_path: str, skip_rows: int = 0,
            output_file_path: str = None) -> None:
        """
        Filter repositories to find Egyptian contributors.

        This function extracts the contributors from the top repositories
        (excluding Egypt) and checks if they have an Egyptian location.
        If so, it appends the contributor to a new row and writes it to the output file.
        """
        if output_file_path is None:
            output_file_path = os.path.join(
                os.getcwd(), self.raw_dir, self.config["EGY_CONTRIBS_FILENAME"]
            )

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(
                f"File created at {output_file_path} for store all Egyption repositories")

        try:
            repos_df = pd.read_csv(input_file_path)
            repos_df = repos_df.dropna(subset=['owner', 'repo_name'])
            repos_df = repos_df.drop_duplicates(
                subset=['owner', 'repo_name'], keep='first')
            repos_df = repos_df.loc[skip_rows:, ['owner', 'repo_name']]

            # Get the contributors for each repository
            fieldnames = ["repo_owner", "repo_name"] + \
                self.config["PROFILE_KEYS"]
            with open(output_file_path, 'a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                # Write the header only once at the beginning of the file
                if file.tell() == 0:  # Check if the file is empty
                    writer.writeheader()

                pbar = tqdm(total=len(repos_df), colour='cyan',
                            desc=f"Checking n Contributors for repo n", unit="repo")

                for index, repo in repos_df.iterrows():
                    repo_name = repo.get('repo_name')
                    repo_owner = repo.get('owner')
                    if repo_name is None or repo_owner is None:
                        self.logger.warning("Skipping row %s due to missing"
                                            "repo_name or repo_owner", index)
                        continue

                    contribs_url = f"{self.config['API_BASE_URL']}/repos/{repo_owner}/{repo_name}/contributors"
                    contribs = self._get(contribs_url)

                    if contribs is None:
                        self.logger.warning(
                            "Skipping row %s due to missing contributors", index)
                        pbar.update(1)
                        continue

                    # Update the progress bar with the number of contributors
                    pbar.set_description(
                        f"Checking {len(contribs)} Contributors for repo [{index+1}/{len(repos_df)+(skip_rows or 0)}]")

                    # Iterate over the contributors
                    for contrib in contribs:
                        egy_contrib = self.get_profile(
                            username=contrib.get('login'), location='egypt')

                        if egy_contrib is not None:
                            egy_contrib["repo_owner"] = repo_owner
                            egy_contrib["repo_name"] = repo_name
                            writer.writerow(egy_contrib)

                    pbar.update(1)

                pbar.close()

        except pd.errors.EmptyDataError:
            self.logger.error("Skiprows exceeded file size")

        except Exception as e:
            self.logger.error("Error while extracting contributors: %s", e)
            raise
