"""Log ip accounting data for bitcoind."""

import asyncio
import csv
import datetime
import logging as log
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import psutil
from bcc import BPF, USDT


class Message:
    """A P2P network message."""

    msg_type = ""
    size = 0
    data = bytes()
    inbound = False

    def __init__(self, msg_type, size, inbound):
        self.msg_type = msg_type
        self.size = size
        self.inbound = inbound


class Peer:
    """A P2P network peer."""

    id = 0
    address = ""
    connection_type = ""
    last_messages = list()

    total_inbound_msgs = 0
    total_inbound_bytes = 0
    total_outbound_msgs = 0
    total_outbound_bytes = 0

    def __init__(self, id, address, connection_type):
        self.id = id
        self.address = address
        self.connection_type = connection_type
        self.last_messages = list()

    def add_message(self, message):
        self.last_messages.append(message)
        if len(self.last_messages) > 25:
            self.last_messages.pop(0)
        if message.inbound:
            self.total_inbound_bytes += message.size
            self.total_inbound_msgs += 1
        else:
            self.total_outbound_bytes += message.size
            self.total_outbound_msgs += 1


PROGRAM = """
#include <uapi/linux/ptrace.h>

// Tor v3 addresses are 62 chars + 6 chars for the port (':12345').
// I2P addresses are 60 chars + 6 chars for the port (':12345').
#define MAX_PEER_ADDR_LENGTH 62 + 6
#define MAX_PEER_CONN_TYPE_LENGTH 20
#define MAX_MSG_TYPE_LENGTH 20

struct p2p_message
{
    u64     peer_id;
    char    peer_addr[MAX_PEER_ADDR_LENGTH];
    char    peer_conn_type[MAX_PEER_CONN_TYPE_LENGTH];
    char    msg_type[MAX_MSG_TYPE_LENGTH];
    u64     msg_size;
};


// Two BPF perf buffers for pushing data (here P2P messages) to user space.
BPF_PERF_OUTPUT(inbound_messages);
BPF_PERF_OUTPUT(outbound_messages);

int trace_inbound_message(struct pt_regs *ctx) {
    struct p2p_message msg = {};

    bpf_usdt_readarg(1, ctx, &msg.peer_id);
    bpf_usdt_readarg_p(2, ctx, &msg.peer_addr, MAX_PEER_ADDR_LENGTH);
    bpf_usdt_readarg_p(3, ctx, &msg.peer_conn_type, MAX_PEER_CONN_TYPE_LENGTH);
    bpf_usdt_readarg_p(4, ctx, &msg.msg_type, MAX_MSG_TYPE_LENGTH);
    bpf_usdt_readarg(5, ctx, &msg.msg_size);

    inbound_messages.perf_submit(ctx, &msg, sizeof(msg));
    return 0;
};

int trace_outbound_message(struct pt_regs *ctx) {
    struct p2p_message msg = {};

    bpf_usdt_readarg(1, ctx, &msg.peer_id);
    bpf_usdt_readarg_p(2, ctx, &msg.peer_addr, MAX_PEER_ADDR_LENGTH);
    bpf_usdt_readarg_p(3, ctx, &msg.peer_conn_type, MAX_PEER_CONN_TYPE_LENGTH);
    bpf_usdt_readarg_p(4, ctx, &msg.msg_type, MAX_MSG_TYPE_LENGTH);
    bpf_usdt_readarg(5, ctx, &msg.msg_size);

    outbound_messages.perf_submit(ctx, &msg, sizeof(msg));
    return 0;
};
"""


# TODO: This is taken from ../rpc/base.py; at some point, extract this
# functionality to avoid duplication
def human_readable_size(size_bytes: int) -> str:
    """Convert size in bytes to a human-readable string."""
    if size_bytes < 1000:
        return f"{size_bytes}B"
    if (size_kbytes := size_bytes / 1000) < 1000:
        return f"{size_kbytes:.1f}kB"
    return f"{(size_kbytes/1000):.1f}MB"


# TODO: This is taken from ../rpc/base.py; at some point, extract this
# functionality to avoid duplication
def human_readable_time(sec: float) -> str:
    """Convert seconds to a human-readable string."""
    if (msec := int(sec * 1000)) < 1000:
        return f"{msec}ms"
    if sec < 60:
        return f"{sec:.1f}s"
    if (min_ := sec / 60) < 60:
        return f"{min_:.1f}m"
    return f"{(min_/60):.1f}h"


@dataclass
class Net:
    """
    Class implementing the collection of IP accounting statistics for the
    bitcoind service via systemd.
    """

    results_path: Path
    peers = {}
    FREQUENCY: ClassVar[int] = 5  # 5 seconds
    CALL_NAME: ClassVar[str] = "net"
    CSV_FIELDS: ClassVar[list[str]] = [
        "direction",  # in, out
        "connection_type",
        "msg_type",
        "msg_size",
    ]

    async def get_pid(self, binary_name="bitcoind") -> int:
        """Get the PID of the bitcoind process."""
        pids = []
        for process in psutil.process_iter(["name", "pid"]):
            if process.info["name"] == binary_name:
                pids.append(process.info["pid"])
        if len(pids) != 1:
            raise RuntimeError(
                f"get_pid: found {len(pids)} processes with name {binary_name}"
            )
        return pids[0]

    # TODO: This is taken from ../rpc/base.py; at some point, extract this
    # functionality to avoid duplication
    async def reschedule(self):
        """Reschedule the task by sleeping until the next multiple of FREQUENCY."""
        now = time.time() + 1  # avoid race condition where now % FREQUENCY == 0
        last_scheduled = now - now % self.FREQUENCY
        next_scheduled = last_scheduled + self.FREQUENCY
        wake_time = datetime.datetime.utcfromtimestamp(next_scheduled)
        sleep_time = next_scheduled - now
        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info(
            "Scheduling next run at %s (sleeping for %s)",
            wake_time.isoformat() + "Z",
            human_readable_time(sleep_time),
        )
        await asyncio.sleep(sleep_time)
        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("Waking up")

    async def run(self):
        """Code to fetch data from systemd."""

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() started")

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() enabling probes...")

        bitcoind_with_usdts = USDT(pid=await self.get_pid())
        # attaching the trace functions defined in the BPF program to the tracepoints
        bitcoind_with_usdts.enable_probe(
            probe="inbound_message", fn_name="trace_inbound_message"
        )
        bitcoind_with_usdts.enable_probe(
            probe="outbound_message", fn_name="trace_outbound_message"
        )

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() compiling program...")
        bpf = BPF(text=PROGRAM, usdt_contexts=[bitcoind_with_usdts])

        def handle_message(_, direction, data, size):
            pass

        # BCC: perf buffer handle function for inbound_messages
        def handle_inbound(_, data, size):
            """Inbound message handler.
            # handle_message("in", data, size)

            Called each time a message is submitted to the inbound_messages BPF table.
            """
            event = bpf["inbound_messages"].event(data)
            if event.peer_id not in self.peers:
                peer = Peer(
                    event.peer_id,
                    event.peer_addr.decode("utf-8"),
                    event.peer_conn_type.decode("utf-8"),
                )
                self.peers[peer.id] = peer
            self.peers[event.peer_id].add_message(
                Message(event.msg_type.decode("utf-8"), event.msg_size, True)
            )

        # BCC: perf buffer handle function for outbound_messages
        def handle_outbound(_, data, size):
            """Outbound message handler.

            Called each time a message is submitted to the outbound_messages BPF table.
            """
            # handle_message("out", data, size)
            event = bpf["outbound_messages"].event(data)
            if event.peer_id not in self.peers:
                peer = Peer(
                    event.peer_id,
                    event.peer_addr.decode("utf-8"),
                    event.peer_conn_type.decode("utf-8"),
                )
                self.peers[peer.id] = peer
            self.peers[event.peer_id].add_message(
                Message(event.msg_type.decode("utf-8"), event.msg_size, False)
            )

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() adding handlers...")

        # BCC: add handlers to the inbound and outbound perf buffers
        bpf["inbound_messages"].open_perf_buffer(handle_inbound)
        bpf["outbound_messages"].open_perf_buffer(handle_outbound)

        log.info("tracepoints.net:run() polling buffers...")
        bpf.perf_buffer_poll(timeout=50)

        log.info("tracepoints.net:run() printing results...")
        print(self.peers)

        # tz = datetime.timezone.utc
        # while True:
        #     call_time = datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%SZ")
        #     try:
        #         call_result = await self.tracepoint_call()
        #         data = self.format_results(call_time, call_result)
        #         if not data:
        #             # TODO: replace with self.log (look at ../rpc/base.py)
        #             log.warning("no data returned by format_results")
        #             break
        #         self.write_result(data)
        #     except ConnectionError as e:
        #         # TODO: replace with self.log (look at ../rpc/base.py)
        #         log.error(e)
        #     await self.reschedule()

    # async def tracepoint_call(self) -> None:
    #     bpf.perf_buffer_poll(timeout=50)
    #
    #     print(self.peers)
    #
    # return data

    def format_results(self, timestamp, data) -> list[dict]:
        """
        Format call results: just add timestamp.
        """
        return [
            {"timestamp": timestamp}
            | {k: v for k, v in data.items() if k in self.CSV_FIELDS}
        ]

    def write_result(self, data):
        """Write CSV call results to CSV file.

        :param list data: a list of dicts containing data to be written
        """

        file = Path(f"{self.results_path}/{self.CALL_NAME}.csv")
        file_exists = file.exists()
        with open(file, "a", newline="", encoding="UTF-8") as f:
            csv_writer = csv.DictWriter(f, fieldnames=["timestamp"] + self.CSV_FIELDS)
            if not file_exists:
                csv_writer.writeheader()
            csv_writer.writerows(data)
