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
import json
import signal
import platform
import pandas as pd
from datetime import datetime
from tqdm import tqdm
from typing import Optional, List, Dict
from src.github_api import GitHubAPI

class GitHubDataCollector(GitHubAPI):
    """Class for scraping contributors and their repositories from GitHub."""
    def __init__(self):

        super().__init__()

    def scrap_egy_users(
        self, params: Dict, endpoint: str, date: str, 
        output_filename: str = None
        ) -> List[Dict]:
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
        output_filename = output_filename or "egy_users.csv"
        output_file_path = os.path.join(os.getcwd(), self.draft_dir, output_filename)
        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(f"File created at {output_file_path} to store all Egyption users urls")

        # Initialize an empty list to store scraped user data
        scrapped_users = []

        # Send the first request to get total_count and set up the progress bars
        response = self._get(url=endpoint, params=params)
        
        if response is not None:
            # Get the total number of users and pages from the response
            total_count = response["total_count"]
            max_page = total_count // params["per_page"] + 1
            self.logger.info(f"Total contributors Found: {total_count}")

            # Outer progress bar for total pages
            pbar = tqdm(
                total=max_page, desc="Scraping pages", unit=" pages", colour='green', 
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]",
            )

            page = 1

            while True:
                # Update the progress bar description for the current page
                pbar.set_description(f"Scraping {total_count:03} users [{date}] Page {page:02}/{max_page:02}")

                users_on_page = len(response["items"])
                # Iterate over the users on the current page
                for item in response["items"]:
                    user_data = {
                        "login": item["login"],
                        "url": item["url"],
                    }
                    scrapped_users.append(user_data)

                self.logger.info(f"Finished scraping page {page}")
                pbar.update(1)  # Update the outer progress bar (pages)

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
            writer = csv.DictWriter(file, fieldnames=self.users_cols)
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()

            writer.writerows(scrapped_users)

        return scrapped_users
 
    def scrap_egy_repos(
        self, users_limit: int = 50_000,
        input_filename: str = None, output_filename: str = None, 
        skip_rows: int = 0, mins_limit: float = 0.5) -> List[str]:
        """
        Scrape repositories from Egyptian users.

        Args:
            users_limit (int): The number of users to process.
            input_filename (str): The file path of the input csv file containing the users.
            output_filename (str): The file path of the output csv file containing the scraped repositories.
            skip_rows (int): The number of rows to skip at the beginning of the input file.
            mins_limit (float): The time limit for scraping each user in minutes.

        Returns:
            List[str]: A list of usernames of the users whose repositories were scraped.
        """
        input_filename = input_filename or "egy_users.csv"
        output_filename = output_filename or f"egy_all_repos.csv"
        
        input_file_path = os.path.join(os.getcwd(), self.draft_dir, input_filename)
        output_file_path = os.path.join(os.getcwd(), self.draft_dir, output_filename)

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(f"File created at {output_file_path} to store all Egyption repositories")

        # Read the input csv file containing the users
        users_data = pd.read_csv(
            input_file_path, skiprows=skip_rows, 
            nrows=users_limit, names=self.users_cols
        )

        with open(output_file_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.repos_cols)
            
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
                writer.writeheader()

            # Iterate over the users
            user_repos = []
            for _, user in tqdm(users_data.iterrows(), unit="user",
                                total=len(users_data), colour='green',
                                desc=f"Scraping {len(users_data)} Users"):
                try:
                    response = self._get(f"{user['url']}/repos")

                    # Iterate over the user's repositories
                    for user_repo in response:
                        repo_details = self.get_repo_details(user_repo)
                        user_repos.append(repo_details)

                    # Write the user's repositories to the output csv file
                    if user_repos:
                        writer.writerows(user_repos)

                except Exception as e:
                    self.logger.error(f"Scrapping user {user['login']} exceeded the time {e}")
                    self.skipped_rows.append(user['login'])
                    continue
                            
        # Return the skipped rows list after processing is complete
        return self.skipped_rows


    def scrap_non_egy_repos(
        self, endpoint: str = "https://api.github.com/search/repositories",
        params: Dict[str, str] = {
            "q": "stars:>1000 sort:stars",
            "order": "desc",
            "per_page": 100,
            "page": 1,
        },
        output_filename: str = None,
        total_count: int = 1000) -> None:
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
        output_filename = output_filename or "non_egy_repos.csv"
        output_file_path = os.path.join(os.getcwd(), self.draft_dir, output_filename)

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(f"File created at {output_file_path} to store non-egyption repositories")

        with open(output_file_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.repos_cols)
            
            # Write the header only once at the beginning of the file
            if file.tell() == 0:  # Check if the file is empty
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
                    pbar.set_description("Scrapping Non Egyption Repos: "\
                                        f"Page[{params['page']:01}/{int(total_count/100)}]")
                    self.logger.info(f"Scraping page number {params['page']}")
                    
                    params["page"] += 1    
    def extract_egy_contribs(self, input_filename: str = None, output_filename: str = None) -> None:
        """
        Filter repositories to find Egyptian contributors.

        This function extracts the contributors from the top repositories
        (excluding Egypt) and checks if they have an Egyptian location.
        If so, it appends the contributor to a new row and writes it to the output file.
        """
        input_filename = input_filename or "non_egy_repos.csv"
        output_filename = output_filename or "egy_contribs.csv"
        
        input_file_path = os.path.join(os.getcwd(), self.draft_dir, input_filename)
        output_file_path = os.path.join(os.getcwd(), self.draft_dir, output_filename)

        if not os.path.exists(output_file_path):
            open(output_file_path, 'w').close()
            self.logger.info(f"File created at {output_file_path} for store all Egyption repositories")

        try:
            repos_df = pd.read_csv(input_file_path, usecols=['owner', 'repo_name'])
            # Get the contributors for each repository
            fieldnames=["repo_owner", "repo_name"] + self.profile_keys
            with open(output_file_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                # Write the header only once at the beginning of the file
                if file.tell() == 0:  # Check if the file is empty
                    writer.writeheader()

                pbar = tqdm(total=len(repos_df), desc="Processing Repos Contributors", unit="repos")

                for index, repo in repos_df.iterrows():
                    repo_name = repo['repo_name']
                    repo_owner = repo['owner']
                    if repo_name is None or repo_owner is None:
                        self.logger.warning(f"Skipping row {index} due to missing repo_name or repo_owner")
                        continue
                    
                    contribs_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contributors"

                    contribs = self._get(contribs_url)
                    if contribs is None:
                        self.logger.warning(f"Skipping row {index} due to missing contributors")
                        pbar.update(1)
                        continue

                    # Update the progress bar with the number of contributors
                    pbar.set_postfix({'num_contribs': len(contribs)})
                    pbar.total += len(contribs)

                    # Iterate over the contributors
                    for contrib in contribs:

                        pbar.total += len(contribs)
                        egy_contrib = self.get_profile(username=contrib['login'], location='egypt')
                        if egy_contrib is not None:
                            egy_contrib["repo_owner"] = repo_owner
                            egy_contrib["repo_name"] = repo_name
                            writer.writerow(egy_contrib)
                        pbar.update(1)

                pbar.close()
                
        except pd.errors.EmptyDataError:
            self.logger.error("Skiprows exceeded file size")
            
"""
This block serves as the entry point for the script.
The script performs the following tasks:
    - Scrape Egyptian users.
    - Scrape repositories from those users.
    - Scrape top global repositories (excluding Egypt).
    - Extract Egyptian contributors from the top repositories.
"""

if __name__ == '__main__':

    collector = GittHubDataCollector()

    # Scrape Egypt users
    params = {"q": "location:egypt repos:>0 created:2013-10", "per_page": 100}
    collector.scrap_egy_users(params=params, date='2023-10')

    # Scrape Egyption Repositories
    collector.scrap_egy_repos("./data/raw/egy_users.csv",
                              './data/all_egy_repos.csv',
                               skip_rows=10,
                               limit=5)

    # scrape top global repositories (excluding Egypt)
    collector.scrap_non_egy_repos("./data/draft/non_egy_repos.csv",
                                  total_count=1000)

    # Example to extract Egyptian contributors from top repositories
    collector.extract_egy_contribs( "./data/draft/non_egy_repos.csv",
                                    "./data/raw/top_egy_contribs.csv")
