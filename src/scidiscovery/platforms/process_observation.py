"""Sample the owned local process tree; native detached daemons remain unknown."""
import os
from pathlib import Path
import signal


def process_record(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')')+2:].split()
        return dict(pid=pid, parent=int(fields[1]), start=fields[19],
            rss=int(fields[21])*os.sysconf('SC_PAGE_SIZE'))
    except (OSError, ValueError, IndexError):
        return None


class OwnedProcessTree:
    def __init__(self, pid):
        record = process_record(pid)
        self.owned = {pid: record['start']} if record else {}
        self.high_water = 0

    def sample(self):
        records = {}
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                record = process_record(int(entry.name))
                if record:
                    records[record['pid']] = record
        current = {pid for pid, start in self.owned.items() if pid in records and records[pid]['start'] == start}
        while True:
            children = {pid for pid, value in records.items() if value['parent'] in current} - current
            if not children:
                break
            current.update(children)
        for pid in current:
            self.owned[pid] = records[pid]['start']
        rss = sum(records[pid]['rss'] for pid in current)
        self.high_water = max(self.high_water, rss)
        daemon = process_record(os.getpid())
        return dict(owned_tree_rss_bytes=rss, owned_tree_peak_bytes=self.high_water,
            control_daemon_rss_bytes=daemon['rss'] if daemon else None,
            observed_processes=len(current), coverage='sampled_owned_tree',
            limitations=['Detached native daemons not observed in this tree have unknown resource coverage.',
                'Sampling is an emergency stop, not an OS aggregate memory guarantee.'])

    def terminate(self):
        """Only observed owned identities, checking PID reuse before every signal."""
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid, start in reversed(tuple(self.owned.items())):
                current = process_record(pid)
                if current and current['start'] == start:
                    try:
                        os.kill(pid, sig)
                    except ProcessLookupError:
                        pass
