"""Log ip accounting data for bitcoind."""

import asyncio
import csv
import datetime
import logging as log
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar

import psutil
from bcc import BPF, USDT, re


@dataclass
class Message:
    """A P2P network message."""

    peer_id: int
    peer_conn_type: str
    peer_addr: str
    flow: str
    msg_type: str
    size: int


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
    messages = []
    FREQUENCY: ClassVar[int] = 5  # 5 seconds
    CALL_NAME: ClassVar[str] = "net"
    # TODO: not used here, probably should be. need to figure out field names
    CSV_FIELDS: ClassVar[list[str]] = [
        "peer_id",
        "peer_conn_type",
        "peer_addr",
        "flow",
        "msg_type",
        "size",
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
        log.info("tracepoints.net:run(): Waking up")

    async def run(self):
        """Code to fetch data from systemd."""

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() started")

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() enabling probes...")

        bitcoind_with_usdts = USDT(pid=await self.get_pid())
        # attaching the trace functions defined in the BPF program to the tracepoints
        bitcoind_with_usdts.enable_probe(
            probe="net:inbound_message", fn_name="trace_inbound_message"
        )
        bitcoind_with_usdts.enable_probe(
            probe="net:outbound_message", fn_name="trace_outbound_message"
        )

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() compiling program...")
        bpf = BPF(text=PROGRAM, usdt_contexts=[bitcoind_with_usdts])

        # def handle_message(direction, data, size):
        #     event = bpf["

        # BCC: perf buffer handle function for inbound_messages
        #
        def handle_message(event, flow: str) -> None:
            """Handle in- and outbound messages."""
            message = Message(
                peer_id=event.peer_id,
                peer_conn_type=event.peer_conn_type.decode("utf-8"),
                peer_addr=event.peer_addr.decode("utf-8"),
                flow=flow,
                msg_type=event.msg_type.decode("utf-8"),
                size=event.msg_size,
            )
            self.messages.append(message)

        def handle_inbound(_, data, size):
            """Inbound message handler."""
            event = bpf["inbound_messages"].event(data)
            handle_message(event, flow="in")

        def handle_outbound(_, data, size):
            """Outbound message handler."""
            event = bpf["outbound_messages"].event(data)
            handle_message(event, flow="out")

        # TODO: replace with self.log (look at ../rpc/base.py)
        log.info("tracepoints.net:run() adding handlers...")

        # BCC: add handlers to the inbound and outbound perf buffers
        bpf["inbound_messages"].open_perf_buffer(handle_inbound)
        bpf["outbound_messages"].open_perf_buffer(handle_outbound)

        tz = datetime.timezone.utc
        while True:
            call_time = datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                call_result = await self.tracepoint_poll(bpf)
                data = self.format_results(call_time, call_result)
                # if not data:
                #     # TODO: replace with self.log (look at ../rpc/base.py)
                #     break
                if data:
                    self.write_result(data)
                else:
                    log.warning("no data returned by format_results")
            except ConnectionError as e:
                # TODO: replace with self.log (look at ../rpc/base.py)
                log.error(e)
            await self.reschedule()

    async def tracepoint_poll(self, bpf) -> list[dict]:
        """Tracepoint call."""
        log.info("tracepoints.net:run() polling buffers...")
        bpf.perf_buffer_poll(timeout=50)

        log.info("tracepoints.net:run() printing results...")
        num_msgs = len(self.messages)
        log.info("tracepoints.net:run() received %d new messages...", num_msgs)
        results = []
        for i, msg in enumerate(self.messages):
            log.info("tracepoints.net:run() message %d: %s", i, msg)
            results.append(asdict(msg))
        self.messages.clear()
        return results

    def format_results(self, timestamp, data) -> list[dict]:
        """Format list of results: add timestamp to each."""
        results = []
        for msg in data:
            result = {"timestamp": timestamp}
            result.update({key: msg[key] for key in self.CSV_FIELDS if key in msg})
            results.append(result)
        return results

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
