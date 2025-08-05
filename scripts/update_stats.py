#!/usr/bin/env python3
"""
GitHub Stats Updater

This script fetches GitHub statistics using GraphQL v4 and REST v3 APIs,
then updates the README.md file with the latest stats.

Required environment variable:
- GH_TOKEN: GitHub personal access token with appropriate permissions

Features:
- Fetches current year contributions via GraphQL
- Fetches total commits across all repositories
- Fetches merged PR count
- Fetches total stars from owned repositories via REST API
- Respects GitHub rate limits
- Updates README.md between <!--STATS_START--> and <!--STATS_END--> markers
- Always exits with code 0 for CI/CD compatibility
"""

import os
import requests
import time
import sys
from datetime import datetime

# Constants
GITHUB_API_URL_GRAPHQL = "https://api.github.com/graphql"
GITHUB_API_URL_REPOS = "https://api.github.com/user/repos"
GITHUB_TOKEN = os.getenv('GH_TOKEN')

if not GITHUB_TOKEN:
    print("Error: GH_TOKEN environment variable not set")
    print("Please set the GH_TOKEN environment variable with your GitHub personal access token")
    sys.exit(0)

HEADERS = {'Authorization': f'bearer {GITHUB_TOKEN}'}

# Functions
def call_github_graphql(query):
    response = requests.post(GITHUB_API_URL_GRAPHQL, json={'query': query}, headers=HEADERS)
    check_rate_limit(response)
    response.raise_for_status()
    result = response.json()
    if 'errors' in result:
        print(f"GraphQL errors: {result['errors']}")
        raise Exception(f"GraphQL query failed: {result['errors']}")
    return result

def call_github_rest(url):
    response = requests.get(url, headers=HEADERS)
    check_rate_limit(response)
    response.raise_for_status()
    return response

def get_contributions_and_commits():
    current_year = datetime.now().year
    from_date = f"{current_year}-01-01T00:00:00Z"
    to_date = f"{current_year}-12-31T23:59:59Z"
    
    query = f'''
    query {{
      viewer {{
        contributionsCollection(from: "{from_date}", to: "{to_date}") {{
          contributionCalendar {{
            totalContributions
          }}
          commitContributionsByRepository(maxRepositories: 100) {{
            contributions {{
              totalCount
            }}
          }}
        }}
        pullRequests(first: 100, states: MERGED) {{
          totalCount
        }}
      }}
    }}
    '''
    result = call_github_graphql(query)
    viewer = result['data']['viewer']
    total_contributions = viewer['contributionsCollection']['contributionCalendar']['totalContributions']
    total_commits = sum(repo['contributions']['totalCount'] for repo in viewer['contributionsCollection']['commitContributionsByRepository'])
    merged_pr_count = viewer['pullRequests']['totalCount']
    return total_contributions, total_commits, merged_pr_count

def get_total_stars():
    stars = 0
    url = GITHUB_API_URL_REPOS + '?type=owner&per_page=100'
    while url:
        response = call_github_rest(url)
        repos = response.json()
        stars += sum(repo['stargazers_count'] for repo in repos)
        
        # Handle pagination using Link header
        link_header = response.headers.get('Link', '')
        next_url = None
        if 'rel="next"' in link_header:
            parts = link_header.split(',')
            for part in parts:
                if 'rel="next"' in part:
                    next_url = part.split(';')[0].strip('<> ')
                    break
        url = next_url
    return stars

def check_rate_limit(response):
    remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
    reset = int(response.headers.get('X-RateLimit-Reset', time.time()))
    if remaining < 50:
        sleep_time = reset - time.time() + 1  # Add 1 second buffer
        if sleep_time > 0:
            print(f"Rate limit approaching, sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)

def update_readme(contributions, commits, stars, prs):
    with open('README.md', 'r') as file:
        readme_contents = file.read()

    start_marker = '<!--STATS_START-->'
    end_marker = '<!--STATS_END-->'
    start_idx = readme_contents.find(start_marker) + len(start_marker)
    end_idx = readme_contents.find(end_marker)

    new_stats = f'''
![GitHub Stats](https://github-readme-stats.vercel.app/api?username=phoneminthu&show_icons=true)
🏆 **Contributions:** {contributions}
📦 **Total commits:** {commits}
✨ **Stars received:** {stars}
🔀 **PRs merged:** {prs}
    '''

    updated_readme = ''.join([readme_contents[:start_idx], new_stats, readme_contents[end_idx:]])

    with open('README.md', 'w') as file:
        file.write(updated_readme)

def main():
    try:
        contributions, commits, merged_prs = get_contributions_and_commits()
        total_stars = get_total_stars()
        update_readme(contributions, commits, total_stars, merged_prs)
        print("GitHub stats updated successfully!")
    except Exception as e:
        print(f"Error updating stats: {e}")
        # Exit with code 0 even on error so workflow passes
    sys.exit(0)

if __name__ == "__main__":
    main()

