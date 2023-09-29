import re
import unicodedata

from requests import get

# https://gist.github.com/berlotto/6295018
_slugify_strip_re = re.compile(r"[^\w\s-]")
_slugify_hyphenate_re = re.compile(r"[-\s]+")


def slugify(value: str):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.

    From Django's "django/template/defaultfilters.py".
    """
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = _slugify_strip_re.sub("", value).strip().lower()
    return _slugify_hyphenate_re.sub("-", value)


def extract_node_geo_info(node: dict) -> tuple[tuple[float, float], str]:
    """
    extracts ((lat, lon), public_key) from the given node dict
    """
    try:
        nodeinfo = node["nodeinfo"]

        location = nodeinfo["location"]
        lat_long: tuple[float, float] = (location["latitude"], location["longitude"])

        public_key: str = nodeinfo["software"]["wireguard"]["public_key"]

        return (lat_long, public_key)
    except KeyError:
        return None


def extract_node_tunnel_info(node) -> tuple[tuple[float, float], str]:
    try:
        nodeinfo = node["nodeinfo"]
        intf = nodeinfo["network"]["mesh"]["bat0"]["interfaces"]
        tunnel_macs: str = intf.get("tunnel", intf["other"])
        try:
            public_key: str = nodeinfo["software"]["wireguard"]["public_key"]
        except KeyError:
            public_key = slugify(nodeinfo["hostname"])

        return [(tunnel_mac, public_key) for tunnel_mac in tunnel_macs]
    except KeyError:
        return []


def crawl_geo(nodes_url):
    nodes = get(nodes_url).json()["nodes"]

    key_location_map: dict[str, tuple[float, float]] = {}

    for node in nodes:
        node_info = extract_node_geo_info(node)

        if not node_info:
            continue

        lat_long, public_key = node_info

        key_location_map[public_key] = lat_long

    return key_location_map


def crawl_tunnel(nodes_url):
    nodes = get(nodes_url).json()["nodes"]

    tunnel_key_map: dict[str, str] = {}

    for node in nodes:
        node_infos = extract_node_tunnel_info(node)
        for node_info in node_infos:
            tunnel_mac, public_key = node_info
            # tunnel_mac can also be the slugified node name
            tunnel_key_map[tunnel_mac] = public_key

    return tunnel_key_map
