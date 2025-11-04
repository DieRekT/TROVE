from bs4 import BeautifulSoup


def html_to_text(article_html: str) -> str:
    if not article_html:
        return ""
    soup = BeautifulSoup(article_html, "html.parser")
    parts = []
    for node in soup.find_all(["p","div","br"]):
        if node.name == "br":
            parts.append("\n")
        else:
            t = node.get_text(" ", strip=True)
            if t: parts.append(t + "\n")
    raw = "".join(parts).strip()
    return raw or soup.get_text("\n", strip=True)

