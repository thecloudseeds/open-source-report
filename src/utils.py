import re
import os
import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from typing import List, Dict, Optional, Any
from random import uniform

#########################################################################################################
# Handle Dataset
#########################################################################################################


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

    with open("./data/json_files/languages_keywords.json", "r", encoding='utf-8') as file:
        # Load the json file containing the language keywords
        languages_keywords = json.load(file)

    # Combine the text and convert to lower case
    # Split the text into individual words and convert to lower case to ignore case differences
    text_words = set(
        repo['repo_description'].lower().split() +
        repo['topics'].lower().split(","))

    filenames = repo['db_files'] + repo['api_files'] + repo['cicd_files']

    # Check against known languages
    for lang, identifiers in languages_keywords.items():
        # Iterate over the language keywords
        for word in identifiers:
            # If any of the keywords match words in the text, then the language is detected
            if word in text_words:
                return lang

        for file in filenames:
            # If any of the keywords match the file extensions in the repository, then the language is detected
            if file.endswith(tuple(identifiers)):
                return lang

    # If no language is detected, return None
    return ''

#########################################################################################################
# Visualization
#########################################################################################################


def pct_func(pct: float) -> str:
    """Return formatted percentage or empty string for percentages below 4%."""
    return f'{pct:.1f}%' if pct >= 4 else ''


def create_palette(n_colors: int) -> List[str]:
    """Create a color palette for the plots."""
    # If palette_color is None or has fewer colors, generate the required number of colors
    palette_color = sns.color_palette('RdBu', n_colors)

    # Adjust colors to ensure they are not overly bright
    palette_color = [
        (uniform(0.5, 0.75), uniform(0.5, 0.75), uniform(0.5, 0.75))
        if all(c >= 0.8 for c in color) else color
        for color in palette_color
    ]
    return palette_color


def plot_bar_chart(ax: plt.Axes,
                   df: pd.DataFrame,
                   feature: str,
                   y: str,
                   fontsize: int = 14,
                   palette_color: List[str] = None,
                   rotation: int = 90) -> None:
    """Plot the bar chart on the given axes with error handling."""

    # Calculate the total count only once
    # Prevent division by zero
    total_count = df[y].sum() if df[y].sum() != 0 else 1

    # Plot the bar chart
    sns.barplot(x=feature, y=y, data=df, hue=feature,
                palette=palette_color, ax=ax)

    # Annotate each bar with its percentage
    for patch in ax.patches:
        if patch.get_height() is not None:
            percentage = (patch.get_height() / total_count) * 100
            ax.annotate(f"{percentage:.1f}%", (patch.get_x() + patch.get_width() / 2., patch.get_height()),
                        ha="center", va="bottom", fontsize=fontsize - 3,
                        bbox=dict(facecolor="white", alpha=0.5, boxstyle="round,pad=0.4"))

    # Set x-axis tick locations and labels with rotation
    ax.set_xticks(range(len(df[feature])))
    ax.set_xticklabels(df[feature], rotation=rotation, fontsize=fontsize - 2)

    # Set the title, x-axis and y-axis labels and rotation
    feature = feature.replace("_", " ").title()
    y = y.replace("_", " ").title()

    ax.set_title(f"Repositories per {feature}", fontsize=fontsize + 2, y=1.1)
    ax.set_xlabel(feature, fontsize=fontsize, labelpad=12)
    ax.set_ylabel(y, fontsize=fontsize, labelpad=12)


def plot_pie_chart(ax: plt.Axes,
                   df: pd.DataFrame,
                   feature: str,
                   y: str,
                   fontsize: int = 14,
                   palette_color: List[str] = None) -> None:
    """Plot the pie chart on the given axes."""
    df_pie = df.set_index(feature)

    # Add condition to display or hide labels
    percentages = (df_pie[y] / df_pie[y].sum()) * 100
    labels = df_pie.index.where(percentages >= 4, '')

    ax.pie(df_pie[y],
           labels=labels,
           autopct=pct_func,
           colors=palette_color,
           textprops={'fontsize': fontsize-2},
           )

    title = f'{feature} Distribution'.title()
    ax.set_title(title, fontsize=14)


def plot_categories(
        df: pd.DataFrame,
        extra_pie: bool = False,
        figsize: tuple = (15, 5),
        rotation: int = 90,
        fontsize: int = 14,
        palette_color: Optional[List[str]] = None) -> None:
    """
    Plots a bar chart of the counts of repositories per feature.
    Adds a pie chart if the number of categories is less than 10.
    """
    feature, y = df.columns[:2]

    if palette_color is None:
        palette_color = create_palette(len(df))

    # Plot the bar chart
    if not extra_pie:
        fig, ax = plt.subplots(figsize=figsize)
        plot_bar_chart(ax, df, feature, y, fontsize, palette_color, rotation)
    # Add a pie chart beside the bar plot if extra_pie is True and number of categories < 10
    else:
        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(figsize[0] * 2, figsize[1]))
        plot_bar_chart(ax1, df, feature, y, fontsize, palette_color, rotation)
        plot_pie_chart(ax2, df, feature, y, fontsize, palette_color)

    plt.tight_layout()

    # Save the figure
    title_safe = feature.lower().replace(" ", "_")
    os.makedirs("./results", exist_ok=True)
    plt.savefig(f"./results/{title_safe}.png", bbox_inches='tight')

    plt.show()


def histogram_chart(ax, data, fontsize: int, color: str, column: str) -> None:
    """Plot a single histogram on the provided axes."""
    ax.hist(data, color=color, alpha=0.9)

    column = column.replace("_", " ")
    ax.set_title(f"Distribution of {column}".title(),
                 fontsize=fontsize + 2, y=1.1)
    ax.set_xlabel(f"Number of {column}".title(),
                  fontsize=fontsize, labelpad=12)
    ax.set_ylabel("Frequency", fontsize=fontsize, labelpad=12)


def plot_histograms(
        df: pd.DataFrame,
        palette_color: Optional[List[str]] = None,
        fontsize: int = 10,
        figsize: tuple = (12, 3.5)) -> None:
    """Plot histograms for the given columns in the data using subplots."""

    columns = df.columns
    ncols = len(list(columns))

    if palette_color is None:
        palette_color = create_palette(ncols)

    # Calculate the number of rows needed based on the number of columns
    nrows = (ncols + 2) // 3  # 3 plots per row

    # Create subplots with dynamic rows and columns
    fig, axes = plt.subplots(nrows, 3, figsize=figsize, squeeze=False)
    axes = axes.flatten()  # Flatten the axes array for easy indexing

    # Iterate over the columns and plot the histogram for each one
    for i, column in enumerate(columns):
        histogram_chart(axes[i], df[column], fontsize,
                        palette_color[i], column)

    # Hide any unused subplots if columns < 3 * nrows
    for j in range(i + 1, len(axes)):
        axes[j].axis('off')  # Hide axes for empty plots

    # Create a title for the entire figure
    # figure_title = "Histograms of Numerical Features"
    # fig.suptitle(figure_title, fontsize=fontsize + 3)
    plt.tight_layout()
    # Save the figure with a title based on the first column
    os.makedirs("./results", exist_ok=True)  # Ensure the directory exists
    plt.savefig(f"./results/numerical_features_distribution.png",
                bbox_inches='tight')

    plt.show()
