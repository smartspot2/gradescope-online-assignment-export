# Gradescope Online Assignment Export

There is currently no good way to export solutions to online assignments on Gradescope. This script is meant to be an alternative, essentially just printing out the webpage into a PDF.

## Setup

To setup the script, run `pip3 install -r requirements.txt` (either in a virtual environment or in your system installation). This will install all the python dependencies.

This script requires Selenium to run (installed via the `requirements.txt` file), and specifically requires a Chrome web driver. (If demand is high, this could be reworked later to be browser agnostic.)

To install the Chrome web driver, go to [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads) and follow the instructions there.

After doing so, you will need to provide a reference to the Chrome webdriver install path. You can do this by specifying an environment variable `CHROME_DRIVER='/path/to/chromedriver'` in a `.env` file at the root of the repository, or manually when your run the script.

## Usage

To run the script, simply run `python3 export.py`. Optionally, you can specify `python3 export.py --all` to export all online assignments for a course.

This will prompt you to log in to Gradescope via your email and password (if you typically log in through SSO, you'll need to create a password on Gradescope). Upon successfully logging in, the browser cookies will automatically be saved (default in `cookies.json`), so you won't have to log in again in successive runs of the script.

When running `python3 export.py` without the `--all` flag, you'll also be prompted to give a link to the online assignment. Make sure you give the link to the outline page; the URL should end in `/outline/edit`. If the given URL is validated to be an online assignment, you'll be prompted for a file name to save the PDF into. By default, this file will be put into a `pdf/` folder in the repository root.

When running `python3 export.py --all`, you'll be prompted to give a link to the course assignments page. (If you just give the course homepage, the script will append `/assignments` to the URL.) At this point, it will scrape the assignments page for a list of all assignments, and save every single online assignment in the course into the output folder.

Note that page requests tend to be slow, and the script may take a while to load certain web pages. Selenium has a default of a 300 second timeout for page loads, which is quite a while---feel free to interrupt the script if it's taking too long, especially when crawling through all assignments, though this isn't usually an issue.

### Options

There are a few command line options that can be passed in to configure the behavior of the script.

- `--all`: Export all online assignments for a given course.

- `--folder [path]`: Specify the output folder for the pdfs. This folder must exist prior to running the sript, otherwise an error will be thrown.

- `--cookies [path]`: Specify the location to save the browser cookies for future loading (a JSON file). If this does not exist, you will be prompted to enter your credentials, and upon successful login, the browser cookies will be saved to this file.

## Implementation Details

This script has two components; a Gradescope Selenium web driver client, and the actual export script.

The login process is done through the built-in `requests` module for efficiency, since no UI is necessary. The cookies are transferred between the `requests` session and the Selenium browser, and also saved to the specified file.

The Gradescope pages are loaded through Selenium, with abstractions in `api/client.py`. The print to PDF function is built-in to Selenium, and is done through a simple method call (this is the primary reason why Selenium is used).

Progress bars and live updates are made through the `rich` module, so that the user is able to follow slow page requests and PDF operations.
