"""Log Bitcoin Core's TCP/IP traffic for bitcoind."""

import asyncio
import csv
import ctypes
import datetime
import logging as log
import time
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar

import psutil
from bcc import BPF, USDT

CGROUP_PATH = Path("/sys/fs/cgroup/system.slice/bitcoind.service")


PROGRAM = """
#include <uapi/linux/ptrace.h>
#include <uapi/linux/if_ether.h>

struct traffic_stats {
    u64 packets;
    u64 bytes;
};

#define LOOPBACK_INTERFACE_IDX 1
#define INGRESS_KEY 0
#define EGRESS_KEY 1

BPF_ARRAY(traffic_map, struct traffic_stats, 2);


static __inline bool is_loopback(struct __sk_buff *skb) {
    if (skb->ifindex == LOOPBACK_INTERFACE_IDX) {
        return true;
    }
    return false;
}

int count_ingress(struct __sk_buff *skb)
{
    if (is_loopback(skb)) {
        return 1;
    }

    u32 key = INGRESS_KEY;
    struct traffic_stats *val = ingress_map.lookup(&key);
    if (val) {
        __sync_fetch_and_add(&val->packets, 1);
        __sync_fetch_and_add(&val->bytes, skb->len);
    }
    return 1;
}

int count_egress(struct __sk_buff *skb)
{
    if (is_loopback(skb)) {
        return 1;
    }

    u32 key = EGRESS_KEY;
    struct traffic_stats *val = egress_map.lookup(&key);
    if (val) {
        __sync_fetch_and_add(&val->packets, 1);
        __sync_fetch_and_add(&val->bytes, skb->len);
    }
    return 1;
}
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
class Traffic:
    """
    Class implementing the collection of IP accounting statistics for the
    bitcoind service via systemd.
    """

    results_path: Path
    peers = {}
    messages = []
    FREQUENCY: ClassVar[int] = 5  # 5 seconds
    CALL_NAME: ClassVar[str] = "traffic"
    # TODO: not used here, probably should be. need to figure out field names
    CSV_FIELDS: ClassVar[list[str]] = [
        "peer_id",
        "peer_conn_type",
        "peer_addr",
        "flow",
        "msg_type",
        "size",
    ]

    # TODO: This is taken from ../rpc/base.py; at some point, extract this
    # functionality to avoid duplication
    @cached_property
    def log(self):
        """Custom logger."""
        return log.getLogger(self.__class__.__name__)

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
        self.log.info(
            "Scheduling next run at %s (sleeping for %s)",
            wake_time.isoformat() + "Z",
            human_readable_time(sleep_time),
        )
        await asyncio.sleep(sleep_time)
        self.log.info("tracepoints.tcpip_traffic:run(): Waking up")

    async def run(self):
        """Code to fetch data from systemd."""

        self.log.info("tracepoints.tcpip_traffic:run() started")
        self.log.info(
            "tracepoints.tcpip_traffic:run() looking for Bitcoin Core's cgroup path (%s)...",
            CGROUP_PATH,
        )
        if not CGROUP_PATH.exists():
            self.log.error(
                "tracepoints.tcpip_traffic:run() Bitcoin Core cgroup path (%s) does not exist...",
                str(CGROUP_PATH),
            )
            return

        self.log.info("tracepoints.tcpip_traffic:run() compiling BPF program...")
        bpf = BPF(text=PROGRAM)
        self.log.info("tracepoints.tcpip_traffic:run() loading functions...")
        fn_ingress = bpf.load_func("count_ingress", BPF.CGROUP_SKB)
        fn_egress = bpf.load_func("count_egress", BPF.CGROUP_SKB)
        self.log.info("tracepoints.tcpip_traffic:run() attaching functions...")
        bpf.attach_cgroup(fn_ingress, CGROUP_PATH, BPF.CGROUP_INET_INGRESS)
        bpf.attach_cgroup(fn_egress, CGROUP_PATH, BPF.CGROUP_INET_EGRESS)

        # bitcoind_with_usdts = USDT(pid=await self.get_pid())
        # # attaching the trace functions defined in the BPF program to the tracepoints
        # bitcoind_with_usdts.enable_probe(
        #     probe="net:inbound_message", fn_name="trace_inbound_message"
        # )
        # bitcoind_with_usdts.enable_probe(
        #     probe="net:outbound_message", fn_name="trace_outbound_message"
        # )

        tz = datetime.timezone.utc
        while True:
            call_time = datetime.datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                call_result = await self.tracepoint_poll(bpf)
                data = self.format_results(call_time, call_result)
                if data:
                    self.write_result(data)
                else:
                    self.log.warning("no data returned by format_results")
            except ConnectionError as e:
                self.log.error(e)
            await self.reschedule()

    async def tracepoint_poll(self, bpf) -> list[dict]:
        """Tracepoint call."""

        traffic_map = bpf.get_table("traffic_map")

        val_ingress = traffic_map[ctypes.c_int(0)]
        val_egress = traffic_map[ctypes.c_int(1)]

        log.info(
            "Ingress: %d packets, %s bytes",
            val_ingress.packets,
            human_readable_size(val_ingress.bytes),
        )

        bpf.perf_buffer_poll(timeout=50)
        num_msgs = len(self.messages)
        self.log.info(
            "tracepoints.tcpip_traffic:run() received %d new messages...", num_msgs
        )
        results = [asdict(msg) for msg in self.messages]
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

        date = data[0]["timestamp"].split("T")[0]
        file = Path(f"{self.results_path}/tracepoints/{self.CALL_NAME}/{date}.csv")

        file_exists = file.exists()
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "a", newline="", encoding="UTF-8") as f:
            csv_writer = csv.DictWriter(f, fieldnames=["timestamp"] + self.CSV_FIELDS)
            if not file_exists:
                csv_writer.writeheader()
            csv_writer.writerows(data)
