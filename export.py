"""
Export Gradescope online assignments to a PDF file.
"""

import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich import print as pprint
from rich.console import Console
from rich.progress import (
    BarColumn,
    Column,
    Progress,
    SpinnerColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt
from rich.status import Status

from api.client import BASE_URL, GradescopeWebDriver

CONSOLE = Console(highlight=False)
CSS_UPDATE = """
document.body.innerHTML = document.getElementsByClassName("onlineAssignment")[0].parentElement.innerHTML;
for (const link of document.head.getElementsByTagName("link")) {link.removeAttribute("media");}
""".strip()


def custom_progress_context() -> Progress:
    """
    Retrieve a new custom progress context for live display.

    Modifies the default context by adding a spinner and making the description full width.
    """
    return Progress(
        SpinnerColumn(),
        # update to full width (very high ratio)
        TextColumn(
            "[progress.description]{task.description}", table_column=Column(ratio=10)
        ),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        expand=True,
        transient=True,
        console=CONSOLE,
    )


def is_online_assignment(content: str):
    """
    Check whether the given page content is for an online assignment.
    """
    outline_soup = BeautifulSoup(content, "html.parser")
    assignment_div = outline_soup.find("div", {"class": "onlineAssignment"})
    return assignment_div is not None


def export_current_page(
    driver: GradescopeWebDriver,
    folder: str,
    assignment: {"url": str, "name": str},
    progress: Progress = None,
    task: Task = None,
):
    """
    Export the current page to a PDF.
    """
    update_progress = progress is not None and task is not None
    if is_online_assignment(driver.get_content()):
        # update CSS
        if update_progress:
            progress.update(task, description="Updating page CSS")
        driver.execute_script(CSS_UPDATE)
        pdf_file = os.path.join(folder, assignment["name"] + ".pdf")

        # save file
        if update_progress:
            progress.update(
                task,
                description=f"Printing to [green]{pdf_file}[/green]",
            )
        driver.print(pdf_file)
        CONSOLE.print(f"Saved to [green]{pdf_file}[/green]")


def crawl_assignments(driver: GradescopeWebDriver, folder: str):
    """
    Crawl through all assignments in a gradescope course,
    checking whether the assignment is an online assignment, and exporting it to a PDF.
    """
    course_url: str = Prompt.ask("Gradescope course URL", console=CONSOLE)

    # normalize to ensure the URL ends in /assignments
    while "assignments" not in course_url:
        course_id_match = re.match(r".*/courses/(\d+)", course_url)
        if not course_id_match:
            pprint("[red]Invalid course URL[/red]")
            course_url: str = Prompt.ask("Gradescope course URL", console=CONSOLE)
        else:
            # extract course id
            course_id = course_id_match.group(1)
            if not course_id:
                pprint("[red]Invalid course URL[/red]")
                course_url: str = Prompt.ask("Gradescope course URL", console=CONSOLE)
            else:
                course_url = urljoin(BASE_URL, f"courses/{course_id}/assignments")
                break

    status = Status(f"Visiting [blue]{course_url}[/blue]", console=CONSOLE)
    status.start()
    driver.visit(course_url)
    content = driver.get_content()
    status.stop()

    assignments_soup = BeautifulSoup(content, "html.parser")
    links = assignments_soup.select("div.table--primaryLink a")
    assignments = [{"url": link["href"], "name": link.get_text()} for link in links]
    progress_context = custom_progress_context()
    with progress_context as progress:
        task = progress.add_task("Crawling assignments", total=len(assignments))
        for assignment in assignments:
            progress.update(
                task,
                advance=1,
                description=f"Crawling assignments ({assignment['name']})",
            )

            assignment_url = urljoin(BASE_URL, assignment["url"])
            outline_url = urljoin(assignment_url + "/", "outline/edit")
            pretty_url = urljoin(assignment["url"] + "/", "outline/edit")
            assignment_task = progress.add_task(
                f"Visiting [blue]{pretty_url}[/blue]", total=None
            )

            driver.visit(outline_url)
            # export the page
            export_current_page(driver, folder, assignment, progress, assignment_task)

            # done with the task, remove it
            progress.remove_task(assignment_task)


def main(export_all=False, folder="pdf", cookie_file="cookies.json"):
    """
    Main method. Calls various other functions depending on the arguments to the export script.
    """
    driver = GradescopeWebDriver(cookie_file=cookie_file)

    if export_all:
        crawl_assignments(driver, folder=folder)
    else:
        while True:
            url = Prompt.ask("Gradescope online assignment URL")
            status = Status(f"Visiting [blue]{url}[/blue]", console=CONSOLE)
            status.start()
            driver.visit(url)
            status.update("Checking whether this is an online assignment")
            if is_online_assignment(driver.get_content()):
                break
            CONSOLE.print(
                "[red]Not an online assignment link[/red]; "
                "make sure you give a link to the outline page "
                "(ending in [blue]/outline/edit[/blue])."
            )
        status.update("Updating page CSS")
        driver.execute_script(CSS_UPDATE)
        status.stop()

        input_pdf_file = Prompt.ask("Output PDF filename", console=CONSOLE)
        if os.path.splitext(input_pdf_file)[1] != '.pdf':
            input_pdf_file += '.pdf'

        pdf_file = os.path.join(folder, input_pdf_file)
        status.update(status=f"Printing to [green]{pdf_file}[/green]")
        status.start()
        driver.print(pdf_file)
        status.stop()
        CONSOLE.print(f"Saved to [green]{pdf_file}[/green]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser("export.py")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Crawl course assignment page to print all online assignments",
    )
    parser.add_argument(
        "--folder", action="store", default="pdf", help="Output folder for pdf files"
    )
    parser.add_argument(
        "--cookies",
        action="store",
        default="cookies.json",
        help="Output folder for saved cookies",
    )
    args = parser.parse_args()
    assert os.path.isdir(args.folder), "Invalid output folder"
    main(export_all=args.all, folder=args.folder, cookie_file=args.cookies)
