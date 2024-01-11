#!/usr/bin/env python3
import logging
import os

from fetch import node_fetcher
from segment.geo_importer import get_interface_by_location, import_segments
from utils.gitter import Gitter
from utils.mover import write_moves

CLONE_URL = os.getenv("CLONE_URL", "https://github.com/ffac/peers-wg")
REPOSITORY: str = os.getenv("REPOSITORY", "/etc/wireguard/peers-wg")
NODES_URL: str = os.getenv(
    "HTTP_NODE_URL", "https://map.aachen.freifunk.net/data/nodes.json"
)

logger = logging.getLogger(__name__)


def main() -> None:
    gitter = Gitter(REPOSITORY, CLONE_URL)
    public_key_to_location = node_fetcher.crawl_geo(NODES_URL)
    import_segments()
    public_key_to_interface = {
        public_key: get_interface_by_location(location)
        for public_key, location in public_key_to_location.items()
    }
    #gitter.pull()
    try:
        committed = write_moves(public_key_to_interface, REPOSITORY)
        #if len(committed) > 0:
        #    gitter.bulk_commit(committed, "update geosegmenter")
            #gitter.push()
    except Exception as e:
        logger.error(f"could not write - restoring {e}")
        #gitter.restore()


if __name__ == "__main__":
    logging.basicConfig()
    main()
