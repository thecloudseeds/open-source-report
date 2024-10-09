"""
This class is designed to detect database types used in GitHub repositories.
It analyzes various repository aspects like files, topics, descriptions,
and language to determine potential database usage.

The analysis involves searching for database-related keywords within these elements:
    - Repository Files: Common database configuration and schema files
    - Topics: Tags associated with the repository, indicating technology use
    - Description: The repository's brief description
    - Language: The language used for the majority of the code
"""
import re
import ast
import json
import base64
from tqdm import tqdm

from typing import Optional, Dict
from src.github_api import GitHubAPI


class GitHubDatabaseExtractor(GitHubAPI):
    """
    This class is designed to detect database types used in GitHub repositories.
    It analyzes various repository aspects like files, topics, descriptions,
    and language to determine potential database usage.
    """

    def __init__(self, row: Dict):

        super().__init__()
        self.row = row
        owner_username = self.row["owner"]
        repo_name = self.row["repo_name"]
        self.base_url = f"https://api.github.com/repos/{owner_username}/{repo_name}"
        

        self.db_languages = [
            "SQL", "TSQL", "PLSQL", "PL/pgSQL",
            "MongoDB", "Cypher", "CQL", "NoSQL", "DynamoDB",
        ]

        # Load database keywords from JSON file
        with open("./data/database_keywords.json", "r", encoding="utf-8") as file:
            self.db_keywords = json.load(file)
            self.logger.info("Loaded database keywords successfully! ")

    def _search_in_content(
            self, content: str, key: str = '') -> Dict[str, str]:
        """Helper function to search for database keywords within text content."""
        db_type = {}
        if isinstance(content, str):
            for db, keywords in self.db_keywords.items():
                if any(
                    re.search(
                        r"\b" + re.escape(keyword) + r"\b",
                        content, re.IGNORECASE,
                    )
                    for keyword in keywords
                ):
                    db_type[db] = key
                    return db_type

        return db_type

    def _search_in_topics(self) -> Dict[str, str]:
        """Search for database types within repository topics."""

        db_type = {}
        if isinstance(self.row["topics"], list):

            for topic in self.row["topics"]:
                db_type.update(self._search_in_content(topic), 'repo_topics')

        return db_type

    def _search_in_description(self) -> Dict[str, str]:
        """Search for database types within repository descriptions."""
        db_type = {}
        if isinstance(self.row["repo_description"], str):
            db_type.update(
                self._search_in_content(
                    self.row["repo_description"], 'repo_description')
            )
        return db_type

    def _search_in_language(self) -> Dict[str, str]:
        """Search for database languages within the primary repository language."""
        db_type = {}

        if isinstance(
                self.row["language"],
                str) and self.row["language"] in self.db_languages:

            db_type[self.row["language"]] = self.row["language"]

        return db_type

    def _search_in_files(self) -> Dict[str, str]:
        """Search for database types in the list of files within a repository."""
        db_type = {}

        filenames = ast.literal_eval(self.row["filenames"]) if isinstance(
            self.row["filenames"], str) else self.row["filenames"]

        for file_name in self.db_files:
            # Check if the file exists in the repository
            if file_name.lower() in [filename.lower()
                                     for filename in filenames]:

                download_url = f"{self.base_url}/contents/{file_name}"
                self.logger.info(download_url)

                data = self._get(download_url)

                if data:
                    # Check if the content is base64 encoded and decode it
                    if "content" in data and data["encoding"] == "base64":
                        file_content = base64.b64decode(
                            data["content"]).decode("utf-8")
                        db_type.update(self._search_in_content(
                            file_content, file_name))
                        self.logger.info(db_type)
                    else:
                        self.logger.info(
                            "File content not available or not base64 encoded for %s in %s",
                            file_name,
                            self.row['repo_name'])
        return db_type

    def extract_database_type(self) -> Dict[str, str]:
        """Main function to check all database types used within a repository."""

        db_type = {}

        # Call the individual functions to analyze different aspects
        db_type.update(self._search_in_files())
        db_type.update(self._search_in_topics())
        db_type.update(self._search_in_description())
        db_type.update(self._search_in_language())

        return db_type


# if __name__ == '__main__':

#     import pandas as pd
#     from tqdm import tqdm

#     df = pd.read_csv("./data/extractor_out.csv").sample(10)
#     df['filenames'] = df['filenames'].fillna('[]')

#     for index, row in tqdm(df.iterrows(), total=len(df),
#                            desc="Detecting Databases"):
#         detector = GitHubDatabaseDetector(row)
#         new_row = detector.detect_database_type()
#         df.loc[index, 'database_type'] = json.dumps(new_row)

#     df.to_csv("./data/dbs.csv", index=False)
