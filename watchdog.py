#!/usr/bin/env python3
import json
import logging
import time
from glob import glob
from os import getenv

from fetch.node_fetcher import crawl_tunnel
from utils.batctl import call_batctl
from utils.gitter import Gitter
from utils.mover import write_moves

logger = logging.getLogger(__name__)

CLONE_URL = getenv("CLONE_URL", "https://github.com/ffac/peers-wg")
REPOSITORY: str = getenv("REPOSITORY", "/etc/wireguard/peers-wg")
LOGLEVEL: str = getenv("LOGLEVEL", "INFO")
CONFIG_FILE: str = "watchdog_config.json"
NODES_URL: str = getenv(
    "HTTP_NODE_URL", "https://map.aachen.freifunk.net/data/nodes.json"
)


def get_moves():
    with open(CONFIG_FILE, "r") as config_file:
        payload = json.load(config_file)
    segments = payload["segments"]
    fallback_wg_iface = payload["fallback"]

    def find_segment_of_gateway(mac):
        for iface, segment in segments.items():
            if mac in segment["allowed_gateways"]:
                return iface
        return None

    needed_moves: dict[str, str] = {}
    for wg_dev, segment in segments.items():
        iface_suffix = wg_dev.split("-")[1]
        batadv_dev = "bat" + iface_suffix
        gateways = call_batctl(batadv_dev, ["gwl", "-nH"])
        prefix_lower = "/sys/class/net/{}/lower_".format(batadv_dev)
        for dev in glob(prefix_lower + "*"):
            ifname = dev[len(prefix_lower) :]
            logger.debug(f"current interface: {ifname}")

            with open(dev + "/address", "r") as address:
                mac = address.read().strip()

            for line in gateways:
                for s in ["(", ")", "[", "]:", "]", "*"]:
                    line = line.replace(s, "")
                fields = line.split()
                mac = fields[0]
                # throughput = fields[1]
                next_node = fields[2]

                if mac in segment["allowed_gateways"]:
                    # mac of a wanted batman gateway
                    continue

                other_seg = find_segment_of_gateway(mac)
                if other_seg:
                    if segment["priority"] < segments[other_seg]["priority"]:
                        # move current node to other_seg
                        logger.info(f"move {next_node} to {other_seg}")
                        needed_moves[next_node] = other_seg
                    elif segments[other_seg]["priority"] == segment["priority"]:
                        # move node to fallback segment
                        needed_moves[next_node] = fallback_wg_iface
                        logger.info(f"move {next_node} to fallback {fallback_wg_iface}")
                else:
                    logger.warning(f"unknown batman gateway found: {mac}")
    return needed_moves


def main() -> None:
    gitter = Gitter(REPOSITORY)
    logger.info("watchdog started")
    while True:
        try:
            try:
                tunnel_key_map = crawl_tunnel(NODES_URL)
            except Exception as e:
                logger.error(f"could not query {NODES_URL}: {e}")
                continue
            gitter.pull()
            moves = get_moves()
            print("moves", moves)
            try:
                public_key_to_interface = {
                    tunnel_key_map[mac]: intf for mac, intf in moves.items()
                }
                print("pubkey_to_if", public_key_to_interface)
                committed = write_moves(public_key_to_interface, REPOSITORY)
                print("committed", committed)
                if len(committed) > 0:
                    gitter.bulk_commit(committed, f"watchdog update {moves}")
                    gitter.push()
            except Exception as e:
                logger.error(f"could not write - restoring {e}")
                gitter.restore()
        finally:
            # also executed on continue
            time.sleep(60)
    logger.info("watchdog stopped")


if __name__ == "__main__":
    logging.basicConfig(level=LOGLEVEL)
    main()
