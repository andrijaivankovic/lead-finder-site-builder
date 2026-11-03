import re
import threading
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}")
FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".css", ".js")
CLOUDFLARE_PATH = "/cdn-cgi/l/email-protection"
MX_RECORD = 15
NO_SUCH_DOMAIN = 3

_answers = {}
_answers_lock = threading.Lock()


def domain_of(address):
    return address.rsplit("@", 1)[-1].lower() if "@" in (address or "") else ""


def _host(url):
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def cloudflare_decode(encoded):
    try:
        data = bytes.fromhex(encoded)
    except ValueError:
        return ""
    if len(data) < 2:
        return ""
    return "".join(chr(byte ^ data[0]) for byte in data[1:])


def _plausible(address, options):
    lowered = address.lower().strip(".")
    name, _, domain = lowered.partition("@")
    if not name or not domain or lowered.endswith(FILE_SUFFIXES):
        return ""
    if any(domain == ignored or domain.endswith("." + ignored) for ignored in options["ignored_domains"]):
        return ""
    if any(name.startswith(ignored) for ignored in options["ignored_names"]):
        return ""
    return lowered


def found_on(soup, options):
    seen = []

    def keep(text):
        for match in ADDRESS.findall(text or ""):
            address = _plausible(match, options)
            if address and address not in seen:
                seen.append(address)

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.lower().startswith("mailto:"):
            keep(unquote(href[7:].split("?")[0]))
        elif CLOUDFLARE_PATH in href and "#" in href:
            keep(cloudflare_decode(href.rsplit("#", 1)[1]))
    for tagged in soup.find_all(attrs={"data-cfemail": True}):
        keep(cloudflare_decode(tagged["data-cfemail"]))
    keep(soup.get_text(" "))
    return seen


def contact_pages(soup, base_url, options):
    home = _host(base_url)
    words = options["contact_words"]
    found = {}
    for link in soup.find_all("a", href=True):
        target = urljoin(base_url, link["href"].strip()).split("#")[0]
        if urlparse(target).scheme not in ("http", "https") or _host(target) != home or target in found:
            continue
        if target.rstrip("/") == base_url.rstrip("/"):
            continue
        label = "{} {}".format(link.get_text(" "), urlparse(target).path).lower()
        matched = [rank for rank, word in enumerate(words) if word in label]
        if matched:
            found[target] = (matched[0], len(found))
    return sorted(found, key=found.get)[:options["contact_pages"]]


def ranked(addresses, site_url, options):
    home = _host(site_url)

    def order(address):
        name, _, domain = address.partition("@")
        same_site = domain == home or home.endswith("." + domain) or domain.endswith("." + home)
        preferred = any(name == word or name.startswith(word) for word in options["preferred_names"])
        return (not same_site, not preferred, addresses.index(address))

    return sorted(addresses, key=order)


def accepts_mail(domain, options):
    domain = (domain or "").lower().strip(".")
    if not domain:
        return False
    with _answers_lock:
        if domain in _answers:
            return _answers[domain]
    try:
        response = requests.get(
            options["dns_url"],
            params={"name": domain, "type": "MX"},
            headers={"Accept": "application/dns-json"},
            timeout=options["dns_timeout_seconds"],
        )
        payload = response.json() if response.status_code == 200 else None
    except (requests.RequestException, ValueError):
        payload = None
    if payload is None:
        return None
    if payload.get("Status") == NO_SUCH_DOMAIN:
        answer = False
    else:
        hosts = [
            item.get("data", "").split()[-1].strip(".")
            for item in payload.get("Answer") or []
            if item.get("type") == MX_RECORD and item.get("data", "").split()
        ]
        answer = any(hosts)
    with _answers_lock:
        _answers[domain] = answer
    return answer


def first_deliverable(addresses, options):
    for address in addresses:
        if accepts_mail(domain_of(address), options) is not False:
            return address
    return ""


def from_site(response, soup, settings, fetch):
    options = settings["site_emails"]
    if not options["enabled"]:
        return ""
    addresses = found_on(soup, options)
    if not addresses:
        for page in contact_pages(soup, response.url, options):
            reply = fetch(page)
            if reply is None or "html" not in reply.headers.get("Content-Type", "html"):
                continue
            addresses = found_on(BeautifulSoup(reply.text, "html.parser"), options)
            if addresses:
                break
    return first_deliverable(ranked(addresses, response.url, options), options)


def drop_undeliverable(leads, settings):
    options = settings["site_emails"]
    dropped = 0
    for lead in leads:
        address = (lead.get("email") or "").strip()
        if address and accepts_mail(domain_of(address), options) is False:
            lead["email"] = ""
            dropped += 1
    return dropped
