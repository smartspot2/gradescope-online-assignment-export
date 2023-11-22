import base64
import json
import os
from getpass import getpass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from rich.prompt import Prompt
from rich.status import Status
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.print_page_options import PrintOptions

BASE_URL = "https://www.gradescope.com"


class GradescopeWebDriver:
    """
    Gradescope access through a selenium chrome webdriver.
    """

    def __init__(self, cookie_file=None):
        # load environment variables
        load_dotenv()

        options = ChromeOptions()
        options.add_argument("--headless=new")
        self.driver = webdriver.Chrome(options=options)

        self.cookie_file = cookie_file

        # login user
        self.login(
            email=os.environ.get("GRADESCOPE_EMAIL", None),
            password=os.environ.get("GRADESCOPE_PASSWORD", None),
        )

    def login(self, email: str, password: str):
        """
        Logs in a user with the given email and password.

        For ease and speed, this method uses the requests library for the login request,
        and transfers the resulting cookies to the selenium webdriver.
        This allows for the webdriver to be used in future actions,
        without needing to login through the frontend form.
        """
        login_url = urljoin(BASE_URL, "/login")

        if os.path.isfile(self.cookie_file):
            status = Status(f"Restoring cookies from [green]{self.cookie_file}[/green]")
            status.start()

            # load cookies
            with open(self.cookie_file, "r", encoding="utf-8") as in_file:
                cookies = json.load(in_file)

            # visit base url to set cookies
            self.visit(BASE_URL)
            for name, value in cookies.items():
                self.driver.add_cookie({"name": name, "value": value})

            # ensure that the user is actually logged in
            status.update("Ensuring user is logged in")
            session = requests.Session()
            session.cookies.update(cookies)

            response = session.get(login_url, timeout=20)
            status.stop()
            try:
                json_response = json.loads(response.content)
                # should give {"warning":"You must be logged out to access this page."}
                if (
                    json_response["warning"]
                    == "You must be logged out to access this page."
                ):
                    # all good to go
                    return True
            except json.JSONDecodeError:
                # invalid json, so use html
                pass

            soup = BeautifulSoup(response.content, "html.parser")
            login_btn = soup.find("input", {"value": "Log In", "type": "submit"})

            if login_btn is None:
                # form does not show, so stop and return
                return True

        if email is None:
            # ask for email
            email = Prompt.ask("Gradescope email")
        if password is None:
            # ask for password, hiding input
            password = getpass("Gradescope password: ")

        status = Status("Logging in")
        status.start()

        # visit login page
        session = requests.Session()
        response = session.get(login_url, timeout=20)

        soup = BeautifulSoup(response.content, "html.parser")

        # get authenticity token from form
        form = soup.find("form")
        token_input = form.find("input", {"name": "authenticity_token"})
        token = token_input.get("value")

        # prepare payload and headers
        payload = {
            "utf8": "✓",
            "authenticity_token": token,
            "session[email]": email,
            "session[password]": password,
            "session[remember_me]": 1,
            "commit": "Log In",
            "session[remember_me_sso]": 0,
        }
        headers = {
            "Host": "www.gradescope.com",
            "Origin": "https://www.gradescope.com",
            "Referer": login_url,
        }
        # login
        response = session.post(login_url, data=payload, headers=headers, timeout=20)
        if not response.ok:
            raise RuntimeError(
                f"Failed to log in; (status {response.status_code})\nReponse: {response.content}"
            )
        # also check content
        page = BeautifulSoup(response.content, "html.parser")
        spans = page.select(".alert-error span")
        if any("Invalid email/password combination" in span.text for span in spans):
            raise RuntimeError("Failed to log in; invalid email/password combination.")

        # let driver go to base url to assign cookies
        self.visit(BASE_URL)

        # copy over all cookies to the chrome webdriver
        for name, value in session.cookies.items():
            self.driver.add_cookie({"name": name, "value": value})

        if self.cookie_file is not None:
            # save cookies as json
            with open(self.cookie_file, "w", encoding="utf-8") as out_file:
                json.dump(session.cookies.get_dict(), out_file)

        status.stop()
        return True

    def visit(self, url: str):
        """Visit a URL."""
        self.driver.get(url)

    def print(self, output_file=None) -> bytes:
        """
        Print the current page to a PDF.

        @param output_file - the file to save the PDF into; None if no output file.
        """
        print_options = PrintOptions()
        print_options.background = True
        pdf = base64.b64decode(self.driver.print_page(print_options=print_options))

        # write to file if specified
        if output_file is not None:
            with open(output_file, "wb") as out:
                out.write(pdf)
        return pdf

    def execute_script(self, script):
        """
        Execute javascript on the current page.
        """
        self.driver.execute_script(script)

    def get_content(self):
        """
        Retrieve raw HTML content from the page.
        """
        return self.driver.page_source
