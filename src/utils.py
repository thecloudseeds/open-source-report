
import re
import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Any


def bar_plot(
        df: pd.DataFrame, feature: str,
        figsize: tuple = (12, 5),
        rotation: int = 90,
        fontsize: int = 14,
        y: str = 'count') -> None:
    """
    Plots a bar chart of the counts of repositories per feature. This is useful for visualizing the
    distribution of repository counts for any given feature (e.g. programming language, country, etc.).

    Args:
        - df (pd.DataFrame): DataFrame containing the feature and count columns.
        - feature (str): Name of the feature to plot.
        - rotation (int): Rotation angle for the x-axis labels.
        - fontsize (int): Font size for the title and labels.
    """

    if df is None:
        raise ValueError("Input DataFrame is null")

    if feature not in df.columns:
        raise KeyError(f"Column '{feature}' not found in DataFrame")

    # Create a color palette for the bar chart
    palette_color = sns.color_palette('RdBu', len(df))

    # Create the figure and set its size
    plt.figure(figsize=figsize)

    # Create the bar plot
    bar_plot = sns.barplot(x=feature, y=y,
                           data=df, palette=palette_color)

    # Set the x-axis labels and title
    plt.xticks(rotation=rotation, fontsize=fontsize-2)

    plt.title(
        f'Counts of Repositories per {feature}'.title(),
        fontsize=fontsize + 2, y=1.1
    )

    plt.xlabel(feature.title(), fontsize=fontsize, labelpad=12)
    plt.ylabel('Number of Repos', fontsize=fontsize, labelpad=12)

    # Get the total count of repositories
    total_count = df['count'].sum()

    # Add percentage labels to each bar
    for patch in bar_plot.patches:
        # If the patch has a height and total count is non-zero, calculate the percentage
        if patch.get_height() is not None and total_count != 0:
            percentage = f'{(patch.get_height() / total_count) * 100:.1f}%'
            # Add the percentage label to the bar
            bar_plot.annotate(
                percentage,
                (patch.get_x() + patch.get_width() / 2., patch.get_height()),
                ha='center', va='bottom', fontsize=fontsize-4,
                bbox=dict(facecolor='white', alpha=0.5,
                          boxstyle='round,pad=0.4')
            )

    # Make sure the plot looks nice and isn't too squished
    plt.tight_layout()
    plt.show()


def top_ranked_repos(df, feature, figsize=(15, 6), n=20, rotation=45):

    palette_color = sns.color_palette('RdBu', 10)
    plt.figure(figsize=figsize)

    top_repos = df.sort_values(by=feature, ascending=False).head(n)
    sns.barplot(x=top_repos['repo_name'],
                y=top_repos[feature], palette=palette_color)

    plt.title(
        f"Top {n} Repositories in Egyptian Open Source Projects According to the Number {feature}", fontsize=16)

    plt.xlabel("Repository Name", fontsize=16)
    plt.ylabel(f"{feature}", fontsize=16)
    plt.xticks(rotation=rotation, ha="right", fontsize=12)
    plt.tight_layout()
    plt.show()

    return top_repos


def extract_city(location):
    """
    Extracts the city from a location string.

    Handles cases where the location is empty, contains irrelevant information (like "Egypt"), 
    or contains special characters.
    """
    if not isinstance(location, str):
        return None
    location = location.strip().lower()

    # Remove contry name
    exclude_egypt = r'\b(egypt)\b'
    location = re.sub(exclude_egypt, '', location)

    if location == '':
        # If location is empty after removing "egypt". so, there is no info about city
        return 'Egypt'

    # Remove characters other than letters and spaces
    only_chars = r'[^a-zA-Z\s]'
    city = re.sub(only_chars, '', location)
    parts = city.split()

    if len(parts) > 0:
        city = ' '.join(parts).title()
        return city


def detect_language(repo: Dict[str, Any]) -> Optional[str]:
    """Detect the programming language used in a GitHub repository based on its description, topics, and filenames.
    Args:
        repo (Dict[str, Any]): A dictionary containing the repository information.
    Returns:
        Optional[str]: The detected programming language or None if not detected.
    """
    # Check if the necessary fields are present and of correct types
    if not (isinstance(repo.get('repo_description'), str) and
            isinstance(repo.get('topics'), str) and
            isinstance(repo.get('filenames'), list)):
        # If any of the fields are not present or of incorrect type, return None
        return None

    with open("./data/json_files/languages_keywords.json", "r", encoding='utf-8') as file:
        # Load the json file containing the language keywords
        languages_keywords = json.load(file)

    # Combine the text and convert to lower case
    # Split the text into individual words and convert to lower case to ignore case differences
    text_words = set(
        repo['repo_description'].lower().split() +
        repo['topics'].lower().split(",")
    )

    # Check against known languages
    for lang, identifiers in languages_keywords.items():
        # Iterate over the language keywords
        for word in identifiers:
            # If any of the keywords match words in the text, then the language is detected
            if word in text_words:
                return lang

        for file in repo['filenames']:
            # If any of the keywords match the file extensions in the repository, then the language is detected
            if file.endswith(tuple(identifiers)):
                return lang

    # If no language is detected, return None
    return None
