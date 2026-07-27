from bs4 import BeautifulSoup


def determine_status(html, selector, mode):
    soup = BeautifulSoup(html, "html.parser")
    found = soup.select_one(selector) is not None

    if mode == "found_means_available":
        return "available" if found else "unavailable"
    if mode == "found_means_unavailable":
        return "unavailable" if found else "available"

    raise ValueError(f"Unknown mode: {mode!r}")
