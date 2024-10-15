
# Egyptian Open Source Contribution Analysis

This repository contains the code and analysis for the Awesome-Egypt-Opensource initiative. The goal is to analyze the open source contributions from Egyptian developers, uncovering insights about their activity and trends. 

## Project Goals

* **Encourage Open Source:**  Promote open source participation by Egyptian companies and independent engineers.
* **Support New Developers:** Provide young developers with a path to contributing to their first open source project, offering guidance in their native language.

## Project Objectives

This project leverages GitHub data to extract valuable insights about Egyptian open source projects:

* **Top Contributing Cities:** Identify the cities with the highest concentration of open source developers.
* **Dominant Programming Languages:** Discover the most popular programming languages used in Egyptian open source projects.
* **Popular Projects:** Rank the top 20 Egyptian open source projects based on stars, forks, contributors, and commits.
* **Non-Egyptian Projects with Egyptian Contributors:** Analyze the top 20 non-Egyptian projects with significant contributions from Egyptian developers.
* **Industry Focus:** Determine the most common industry or topic areas targeted by Egyptian open source projects.
* **Top Frameworks & Libraries:** Identify the leading frameworks and libraries employed in Egyptian open source projects.
* **Database Usage:** Investigate the prevalence of different database engines, including both relational and NoSQL databases.
* **Documentation Quality:** Assess the extent to which projects prioritize documentation and provide useful resources for contributors.
* **Pull Request & Issue Activity:** Examine the distribution of open versus merged pull requests and open versus closed issues.
* **Licensing Practices:** Analyze the top 10 licenses used in Egyptian open source projects.
* **CI/CD Integration:** Determine the adoption rate of CI/CD tools among the projects.

## Structure

The repository is organized as follows:

* **`src`:** Contains the source code modules:
    * `github_api.py`: Provides a class for interacting with the GitHub API. It is the base class for the upcomming classes.
    * `data_collection.py`: Contains functions for scraping GitHub users and repositories.
    * `repo_extractor.py`: Extracts repository details including files, CI/CD tools, dependencies, and database usage.
    * `doc_assessor.py`:  Assesses the documentation quality of repositories.
    * `utils.py`: General utility functions for the analysis notebook.

* **`data`:** Stores raw and processed data files:
    * `json_files`: Contains configuration files in JSON format.
    * `raw`:  Holds scrapped data files.
    * `processed`:  Holds processed data files that will be used in analysis.

* **`results`:** Contains visualization outputs.
* **`config.yaml`:** Stores project configuration settings.
* **`Analyse_Egyption_OpenSource_contribution.ipynb`:**  A Jupyter notebook containing the analysis code and visualizations.
* **`.env`:** Stores GitHub API token environment variables.

## Getting Started

This repository uses DVC (Data Version Control) to track data files. To get started, follow these steps:

## Getting Started

This repository uses DVC (Data Version Control) to track data files. To get started, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Egyptian-Open-Source-Contribution-Analysis.git
   ```

2. **Create a virtual environment (optional, but recommended):**
   * **Using `venv` (Python's built-in virtual environment):**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate  # Linux/macOS
     .venv\Scripts\activate     # Windows
     ```
   * **Using `conda` (if you have Anaconda or Miniconda installed):**
     ```bash
     conda create -n egyptian_opensource python=3.9 # Adjust the Python version if needed
     conda activate egyptian_opensource
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables:**
   * Create a `.env` file in the root directory and add your GitHub Personal Access Token (PAT). 
   * Example:
      ```
      PROJECT_NAME=GitHub-OpenSource-Analysis
      GITHUB_ACCESS_TOKEN1=your_github_access_token_1
      GITHUB_ACCESS_TOKEN2=your_github_access_token_2
      GITHUB_ACCESS_TOKEN3=your_github_access_token_3
      GITHUB_ACCESS_TOKEN4=your_github_access_token_4
      ```
5. **Initialize DVC:**
   ```bash
   dvc init
   ```
6. **Pull data files:**
   ```bash
   dvc pull
   ```
7. **Run the analysis:**
   ```bash
   jupyter notebook Analyse_Egyption_OpenSource_contribution.ipynb
   ```

**Note:** If you make changes to the data files, remember to use `dvc add` and `dvc commit` to track your changes.

## Tools Used

This analysis utilizes various tools and libraries:

* **Core Libraries:**
    * **Python:** Primary programming language.
    * **Jupyter Notebook:** Used for data analysis, visualization, and report generation.
    * **Pandas:** Library for data manipulation and analysis.
    * **NumPy:** Library for numerical computation.
    * **Requests:** Python library for making HTTP requests. 
    * **BeautifulSoup4:** Python library for parsing HTML and XML data.
* **Visualization Libraries:**
    * **Matplotlib and Seaborn:** Libraries for creating static visualizations.
    * **WordCloud:** Library for generating word clouds. 
* **Text Processing & Topic Modeling Libraries:**
    * **NLTK (Natural Language Toolkit):**  Used for natural language processing tasks like tokenization and stemming.
    * **BERTopic (BERT-based Topic Modeling):**  For discovering topics within text data, particularly helpful for analyzing project descriptions
* **Version Controlling Tools:**
    * **Git and GitHub:**  For version control the code files and collaborative development.
    * **DVC (Data Version Control):** Used to track data files and ensure reproducibility of analysis.
    * **dvc-gdrive:** Python package for interacting with Google Drive as a remote storage for DVC.

## Challenges Faced & Solutions

This project encountered several challenges while scraping and analyzing GitHub data related to Egyptian open source projects. Here are some of the challenges and the solutions implemented:

**1. GitHub API Rate Limits:**

* **Challenge:**  GitHub API has rate limits, preventing excessive requests and protecting their infrastructure. This limited the speed at which we could scrape data.
* **Solution:**  
    * **Multiple Tokens:** We used multiple GitHub Personal Access Tokens (PATs) to increase the number of requests allowed.
    * **Rate Limiting Logic:** Implemented logic to handle rate limiting responses (429), including waiting periods and switching tokens when necessary.
    * **Exponential Backoff:**  Used exponential backoff to avoid making repeated requests immediately after hitting rate limits.

**2. Dependency Graph Size:**

* **Challenge:**  Fetching dependency information using the GitHub dependency graph API often resulted in large response per repository, mae it difficult to store and process efficiently.

* **Solution:** 
    * **Json Serialization**: Store dependencies for each repo in a seperate Json file that will be used in analysis. 
    * **Limit Dependencies:** Limited the number of dependencies stored in the CSV file to a reasonable number (e.g., 20) to prevent excessive data storage.

**3. Large Number of Repository Filenames:**

* **Challenge**: Retrieving filenames from repositories with numerous files presented a significant challenge. Storing this extensive list of filenames within a single cell of a CSV file proved impractical due to potential data storage limitations and inefficient analysis.

* **Solution:** We have implemented a strategy focused on **selective filename extraction**.  Instead of storing all filenames, we prioritized only those relevant to our specific analysis objectives. This involved filtering files based on their purpose, such as:
    * Files relevant to identifying database types (e.g., `schema.sql`, `database.yml`, `knexfile.js`, etc.).
    * Files indicating the use of CI/CD tools (e.g., `.github/workflows`, `bitbucket-pipelines.yml`, `circleci.yml`, etc.).
    * Files that contribute to assessing documentation quality (e.g., `README.md`, `CONTRIBUTING.md`, `docs/`, etc.).


**4. Handling Errors:**

* **Challenge:** Errors can occur during the scraping process (e.g., network issues, API errors, data format inconsistencies). 
* **Solution:** 
    * **Error Handling:** Implemented comprehensive error handling mechanisms to capture and log errors gracefully. 
    * **Retry Logic:**  Implemented retry logic to handle temporary errors, allowing the scraper to attempt requests again after a delay. 
    * **Error Logging:**  Thorough logging of errors helped in debugging and identifying patterns in potential issues. 

**By addressing these challenges, we were able to successfully gather and analyze the necessary GitHub data for the Egyptian open source contribution analysis.**

## Contributions

Contributions are welcome! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines. 

## Acknowledgments

This project is inspired by the following resources:

* [GitHub Innovation Graph](https://github.com/github/innovationgraph)
* [Top GitHub Users Action](https://github.com/gayanvoice/top-github-users-action)
* [Committers.top - Egypt](https://committers.top/egypt)
* [xkcd 2347](https://github.com/edsu/xkcd2347) 
