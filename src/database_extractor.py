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
import os
import ast
import json
import base64
import binascii

from typing import Optional, Dict, List
from src.github_api import GitHubAPI


class GitHubDatabaseExtractor(GitHubAPI):
    """
    This class is designed to detect database types used in GitHub repositories.
    It analyzes various repository aspects like files, topics, descriptions,
    and language to determine potential database usage.
    """

    def __init__(self) -> None:
        """
        Initializes the DatabaseExtractor with a row from the repository DataFrame.
        """
        super().__init__()
        
        file_path = os.path.join(self.json_dir, "database_keywords.json")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"{file_path} does not exist")
        
        with open(file_path, "r", encoding="utf-8") as file:
            self.db_keywords = json.load(file)
            self.logger.info("Loaded database keywords successfully! ")

    def search_in_content(self, content: str) -> Dict[str, str]:
        """
        Optimized helper function to search for database keywords within text content.
        """
        if not isinstance(content, str):
            self.logger.warning("Content must be a string. Received type: %s" % type(content) )
            return None
        
        db_type = []
        # Compute set of keywords for faster intersection.
        content_set = set(content.lower().split())
        
        # Use set intersection to check if any keyword is present.
        for db, keywords in self.db_keywords.items():
            if content_set.intersection(keywords):
                self.logger.info("Find Database type %s", db)
                db_type.append(db)
            else:
                continue

        return db_type

    def search_in_language(self, language: str) -> str:
        """Search for database languages within the primary repository language."""
        # Define language keywords related to databases
        db_languages = ["SQL", "TSQL", "PLSQL", "PL/pgSQL", 
                        "MongoDB", "Cypher", "CQL", "NoSQL", "DynamoDB"]
        
        if not isinstance(language, str):
            return None
        
        if language in db_languages:
            self.logger.info("Find Database type %s", language)
            return language

        return None
    def search_in_files(self, row) -> Dict[str, str]:
        """
        Search for database types in the list of files within a repository.
        Args:
            row (Dict): A row from the DataFrame containing the repository details.
        Returns:
            Dict[str, str]: A dictionary with the detected database types.
        """
        if not isinstance(row['filenames'], str):
            return None
        try:
            filenames = set(ast.literal_eval(row['filenames']))
        except (ValueError, SyntaxError) as e:
            self.logger.error("Invalid format for filenames in row: %s", e)
            return None

        if not filenames: # check empty set
            return None

        db_type = []

        # Search for files that are in our list of database files
        files_to_search = filenames.intersection(set(self.db_files))

        # Iterate over the files and search for database types
        for file_name in files_to_search:
            # Check if the file exists in the repository
            if file_name not in filenames:
                continue

            self.logger.info("Found Database File: %s in %s",
                            file_name, row["repo_html_url"])

            # Get the file content from GitHub API
            download_url = f"https://api.github.com/repos/"\
                            f"{row['owner']}/{row['repo_name']}/contents/{file_name}"
            response = self._get(download_url)

            if response is None:
                self.logger.warning("No response from GitHub API for %s", download_url)
                continue

            if "content" not in response:
                self.logger.warning("No file content found in response for %s", download_url)
                continue

            # Decode content based on encoding type
            try:
                encoding = response.get("encoding", "utf-8")
                if encoding == "base64":
                    file_content = base64.b64decode(response["content"]).decode("utf-8")
                elif encoding == "hex":
                    file_content = bytes.fromhex(response["content"]).decode("utf-8")
                else:  
                    file_content = response["content"].encode(encoding).decode("utf-8")

                # Search for database types in the file content
                db_type.extend(self.search_in_content(file_content))

            except (binascii.Error, UnicodeDecodeError, OSError) as e:
                self.logger.error("Error while decoding file content: %s", e)

        return db_type

    def extract_database_type(self, row) -> Dict[str, str]:
        """
        Main function to check all database types used within a repository.
        Args:
            row (Dict): A row from the DataFrame containing the repository details.
        Returns:
            Dict[str, str]: A dictionary with the detected database types.
        """
        
        # Initialize the dictionary to store the detected database types
        db_types = {'files': None,'topics': None,
                   'description': None, 'language': None}
        
        # Call the individual functions to analyze different aspects
        # 1. Check the topics (if any) for database keywords
        db_types["topics"] = self.search_in_content(row['topics'])
        
        # 2. Check the repository description for database keywords
        db_types["description"] = self.search_in_content(row['repo_description'])
        
        # 3. Check the language of the repository if it is a database language
        db_types["language"] = self.search_in_language(row['language'])
        
        # 4. Check the files in the repository for database-related files
        db_types["files"] = self.search_in_files(row[['owner','repo_name','filenames','repo_html_url']])
        
        return db_types
